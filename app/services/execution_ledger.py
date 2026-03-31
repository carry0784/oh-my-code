"""
K-Dexter Execution Ledger

Append-only ledger for execution proposals and receipts.
Replicated from Agent ActionLedger with identical state machine,
fail-closed guard, and receipt enforcement.

Position in control chain:
  GovernanceGate.pre_check() -> Agent ActionLedger -> [THIS] ExecutionLedger -> (future) OrderSubmit

State Machine (SEALED):
  EXEC_PROPOSED -> EXEC_GUARDED    [via propose_and_guard(), all 5 checks pass]
  EXEC_PROPOSED -> EXEC_BLOCKED    [via propose_and_guard(), any check fails]
  EXEC_GUARDED  -> EXEC_RECEIPTED  [via record_receipt(), receipt + evidence required]
  EXEC_GUARDED  -> EXEC_FAILED     [via record_failure(), exception after guard]

  Forbidden transitions:
    EXEC_PROPOSED -> EXEC_RECEIPTED  (must go through EXEC_GUARDED first)
    EXEC_BLOCKED  -> any             (terminal)
    EXEC_RECEIPTED -> any            (terminal)
    EXEC_FAILED   -> any             (terminal)
    any -> EXEC_PROPOSED             (no state regression)

  execution_ready is a DERIVED property:
    execution_ready = (status == EXEC_RECEIPTED)

Constraints:
  - Append-only: no deletion, no mutation of past proposals
  - No exchange access: import of exchanges/ is prohibited
  - No order execution: this module reads and records, never submits orders
  - In-memory buffer with periodic flush to data/execution_action_history.json
  - Duplicate proposals (same fingerprint within 60s) are suppressed
  - Agent receipt required: agent_proposal must be RECEIPTED to enter
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Duplicate suppression window (seconds)
FINGERPRINT_COOLDOWN_SECONDS = 60


# ── Exceptions ──────────────────────────────────────────────────────────── #

class ExecStateTransitionError(Exception):
    """Raised when an invalid execution state transition is attempted."""
    pass


# ── Data Models ─────────────────────────────────────────────────────────── #

@dataclass
class ExecutionReceipt:
    """Immutable receipt generated after an execution proposal passes guard."""
    receipt_id: str
    proposal_id: str
    agent_proposal_id: str
    pre_evidence_id: str
    post_evidence_id: Optional[str] = None
    guard_checks: dict = field(default_factory=dict)
    final_result: dict = field(default_factory=dict)
    execution_ready_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExecutionProposal:
    """
    Single execution proposal with strict state machine.
    Replicated from ActionProposal with EXEC_ prefix states.
    """
    proposal_id: str
    agent_proposal_id: str  # lineage: link to agent ActionProposal
    task_type: str
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    category: str = "execution"
    status: str = "EXEC_PROPOSED"
    guard_passed: bool = False
    guard_reasons: list = field(default_factory=list)
    guard_checks: dict = field(default_factory=dict)
    receipt: Optional[ExecutionReceipt] = None
    pre_evidence_id: Optional[str] = None
    risk_result_summary: dict = field(default_factory=dict)
    fingerprint: str = ""
    created_at: str = ""

    # Allowed transitions (fail-closed: unlisted = forbidden)
    _TRANSITIONS: dict = field(default_factory=lambda: {
        "EXEC_PROPOSED": {"EXEC_GUARDED", "EXEC_BLOCKED"},
        "EXEC_GUARDED": {"EXEC_RECEIPTED", "EXEC_FAILED"},
        "EXEC_BLOCKED": set(),      # terminal
        "EXEC_RECEIPTED": set(),    # terminal
        "EXEC_FAILED": set(),       # terminal
    }, repr=False)

    # Terminal states — proposals in these states are never stale
    _TERMINAL_STATES: frozenset = field(
        default_factory=lambda: frozenset({"EXEC_BLOCKED", "EXEC_RECEIPTED", "EXEC_FAILED"}),
        repr=False,
    )

    @property
    def execution_ready(self) -> bool:
        """Derived property: only True when EXEC_RECEIPTED."""
        return self.status == "EXEC_RECEIPTED"

    def transition_to(self, new_status: str) -> bool:
        """
        Attempt state transition. Returns True on success, raises on violation.
        Fail-closed: undefined transitions are forbidden.
        """
        allowed = self._TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ExecStateTransitionError(
                f"Forbidden transition: {self.status} -> {new_status}. "
                f"Allowed from {self.status}: {allowed or 'none (terminal)'}"
            )
        self.status = new_status
        return True

    def is_stale(self, threshold_seconds: float = 300.0, now: Optional[datetime] = None) -> bool:
        """
        Read-only staleness判定. Does NOT mutate state.

        A proposal is stale when:
          1. status is NOT terminal (EXEC_BLOCKED/EXEC_RECEIPTED/EXEC_FAILED)
          2. no receipt has been recorded
          3. age exceeds threshold_seconds

        Returns False for terminal states regardless of age.
        """
        if self.status in self._TERMINAL_STATES:
            return False
        if self.receipt is not None:
            return False
        if not self.created_at:
            return False
        try:
            created = datetime.fromisoformat(self.created_at)
            current = now or datetime.now(timezone.utc)
            age = (current - created).total_seconds()
            return age > threshold_seconds
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_TRANSITIONS", None)
        d.pop("_TERMINAL_STATES", None)
        d["execution_ready"] = self.execution_ready
        return d


# ── Execution Guard (5 checks) ─────────────────────────────────────────── #

def _check_agent_receipted(agent_proposal_status: Optional[str]) -> tuple[bool, str]:
    """Guard 1: Agent proposal must be RECEIPTED."""
    if agent_proposal_status == "RECEIPTED":
        return True, "AGENT_RECEIPTED: agent proposal is RECEIPTED"
    return False, f"AGENT_RECEIPTED: agent proposal status is {agent_proposal_status} (must be RECEIPTED)"


def _check_governance_clear(pre_evidence_id: Optional[str]) -> tuple[bool, str]:
    """Guard 2: GovernanceGate pre_check evidence must exist."""
    if pre_evidence_id:
        return True, "GOVERNANCE_CLEAR: pre_check evidence exists"
    return False, "GOVERNANCE_CLEAR: no pre_check evidence"


def _check_cost_within_budget(cost_controller: Any = None) -> tuple[bool, str]:
    """Guard 3: CostController budget not exceeded."""
    if cost_controller is None:
        return True, "COST_WITHIN_BUDGET: no controller (skip)"
    try:
        api_budget = cost_controller.get_budget("API_CALLS")
        if api_budget and api_budget.current >= api_budget.limit:
            return False, f"COST_WITHIN_BUDGET: API calls exhausted ({api_budget.current}/{api_budget.limit})"
        token_budget = cost_controller.get_budget("LLM_TOKENS")
        if token_budget and token_budget.current >= token_budget.limit:
            return False, f"COST_WITHIN_BUDGET: tokens exhausted ({token_budget.current}/{token_budget.limit})"
        return True, "COST_WITHIN_BUDGET: within budget"
    except Exception as e:
        return True, f"COST_WITHIN_BUDGET: check error ({e}), allowing"


def _check_lockdown(security_ctx: Any = None) -> tuple[bool, str]:
    """Guard 4: SecurityState not in LOCKDOWN or QUARANTINE."""
    if security_ctx is None:
        return True, "LOCKDOWN_CHECK: no security context (skip)"
    try:
        if hasattr(security_ctx, "is_locked_down") and security_ctx.is_locked_down():
            return False, "LOCKDOWN_CHECK: system is in LOCKDOWN"
        if hasattr(security_ctx, "sandbox_only") and security_ctx.sandbox_only():
            return False, "LOCKDOWN_CHECK: system is in QUARANTINE"
        return True, "LOCKDOWN_CHECK: system is clear"
    except Exception as e:
        return False, f"LOCKDOWN_CHECK: check error ({e}), blocking (fail-closed)"


def _check_size_final(risk_result: dict, max_position_usd: float = 100000.0) -> tuple[bool, str]:
    """Guard 5: Final position size re-check."""
    size = risk_result.get("position_size") or risk_result.get("adjusted_size")
    if size is None:
        return True, "SIZE_FINAL_CHECK: no size specified (skip)"
    if isinstance(size, (int, float)) and size <= max_position_usd:
        return True, f"SIZE_FINAL_CHECK: {size} <= {max_position_usd}"
    return False, f"SIZE_FINAL_CHECK: {size} exceeds limit {max_position_usd}"


# ── Execution Ledger ────────────────────────────────────────────────────── #

class ExecutionLedger:
    """
    Append-only ledger for execution proposals and receipts.
    Replicated from ActionLedger with identical patterns.
    """

    def __init__(self, max_buffer: int = 1000, stale_threshold: float = 300.0):
        self._proposals: list[ExecutionProposal] = []
        self._fingerprints: dict[str, str] = {}  # fingerprint -> last_seen_iso
        self._max_buffer = max_buffer
        self._stale_threshold = stale_threshold  # seconds; default 5 minutes

    # ── Fingerprint ───────────────────────────────────────────────────── #

    @staticmethod
    def _compute_fingerprint(task_type: str, symbol: Optional[str],
                             exchange: Optional[str], position_size: Any) -> str:
        """Compute execution fingerprint for duplicate detection."""
        size_bucket = int((position_size or 0) / 1000) * 1000 if isinstance(position_size, (int, float)) else 0
        raw = f"EXEC|{task_type}|{symbol}|{exchange}|{size_bucket}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _is_duplicate(self, fingerprint: str) -> bool:
        """Check if fingerprint was seen within cooldown window."""
        last_seen = self._fingerprints.get(fingerprint)
        if not last_seen:
            return False
        try:
            last_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            if hasattr(last_dt, "tzinfo") and last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            return elapsed < FINGERPRINT_COOLDOWN_SECONDS
        except (ValueError, TypeError):
            return False

    # ── Core Operations ───────────────────────────────────────────────── #

    def propose_and_guard(
        self,
        task_type: str,
        symbol: Optional[str],
        exchange: Optional[str],
        agent_proposal_id: str,
        agent_proposal_status: str,
        risk_result: dict,
        pre_evidence_id: Optional[str],
        cost_controller: Any = None,
        security_ctx: Any = None,
    ) -> tuple[bool, ExecutionProposal]:
        """
        Atomically: create proposal -> check duplicate -> run 5 guard checks.
        Returns (passed, proposal).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        size = risk_result.get("position_size") or risk_result.get("adjusted_size")
        fp = self._compute_fingerprint(task_type, symbol, exchange, size)

        proposal = ExecutionProposal(
            proposal_id=f"EP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            agent_proposal_id=agent_proposal_id,
            task_type=task_type,
            symbol=symbol,
            exchange=exchange,
            pre_evidence_id=pre_evidence_id,
            fingerprint=fp,
            risk_result_summary={
                "approved": risk_result.get("approved"),
                "position_size": size,
                "risk_score": risk_result.get("risk_score"),
            },
            created_at=now_iso,
        )

        # Duplicate suppression
        if self._is_duplicate(fp):
            proposal.guard_passed = False
            proposal.guard_reasons = [f"DUPLICATE: fingerprint {fp} seen within {FINGERPRINT_COOLDOWN_SECONDS}s"]
            proposal.guard_checks = {"DUPLICATE": {"passed": False, "detail": proposal.guard_reasons[0]}}
            proposal.transition_to("EXEC_BLOCKED")
            self._proposals.append(proposal)
            return False, proposal

        # Run 5 guard checks
        checks = {}
        reasons = []
        all_passed = True

        for name, check_fn in [
            ("AGENT_RECEIPTED", lambda: _check_agent_receipted(agent_proposal_status)),
            ("GOVERNANCE_CLEAR", lambda: _check_governance_clear(pre_evidence_id)),
            ("COST_WITHIN_BUDGET", lambda: _check_cost_within_budget(cost_controller)),
            ("LOCKDOWN_CHECK", lambda: _check_lockdown(security_ctx)),
            ("SIZE_FINAL_CHECK", lambda: _check_size_final(risk_result)),
        ]:
            passed, reason = check_fn()
            checks[name] = {"passed": passed, "detail": reason}
            reasons.append(reason)
            if not passed:
                all_passed = False

        proposal.guard_passed = all_passed
        proposal.guard_checks = checks
        proposal.guard_reasons = reasons

        if all_passed:
            proposal.transition_to("EXEC_GUARDED")
        else:
            proposal.transition_to("EXEC_BLOCKED")

        self._fingerprints[fp] = now_iso
        self._proposals.append(proposal)
        self._enforce_buffer_limit()

        return all_passed, proposal

    def record_receipt(
        self,
        proposal: ExecutionProposal,
        final_result: dict,
        post_evidence_id: Optional[str] = None,
    ) -> ExecutionReceipt:
        """
        Record execution receipt. Fail-closed: requires EXEC_GUARDED + guard_passed.
        """
        if not proposal.guard_passed:
            raise ExecStateTransitionError(
                f"Cannot receipt proposal {proposal.proposal_id}: guard_passed is False. "
                f"Current status: {proposal.status}"
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        receipt = ExecutionReceipt(
            receipt_id=f"ER-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            proposal_id=proposal.proposal_id,
            agent_proposal_id=proposal.agent_proposal_id,
            pre_evidence_id=proposal.pre_evidence_id or "",
            post_evidence_id=post_evidence_id,
            guard_checks=proposal.guard_checks,
            final_result={
                "stage": final_result.get("stage"),
                "adjusted_size": final_result.get("adjusted_size"),
                "execution_ready": True,
            },
            execution_ready_at=now_iso,
            created_at=now_iso,
        )
        proposal.receipt = receipt
        proposal.transition_to("EXEC_RECEIPTED")
        return receipt

    def record_failure(self, proposal: ExecutionProposal, error: str) -> None:
        """Record execution failure. Raises if not EXEC_GUARDED."""
        proposal.transition_to("EXEC_FAILED")
        proposal.guard_reasons.append(f"EXECUTION_FAILED: {error}")

    # ── Board / Query ─────────────────────────────────────────────────── #

    def get_board(self) -> dict:
        """Get execution board grouped by status with orphan detection."""
        board = {
            "exec_proposed": [],
            "exec_guarded": [],
            "exec_receipted": [],
            "exec_blocked": [],
            "exec_failed": [],
        }
        for p in self._proposals:
            key = p.status.lower()
            if key in board:
                board[key].append({
                    "proposal_id": p.proposal_id,
                    "agent_proposal_id": p.agent_proposal_id,
                    "task_type": p.task_type,
                    "symbol": p.symbol,
                    "status": p.status,
                    "execution_ready": p.execution_ready,
                    "fingerprint": p.fingerprint,
                    "created_at": p.created_at,
                })

        orphan_count = len(board["exec_guarded"])

        # Stale detection: non-terminal proposals exceeding age threshold
        stale_count = sum(1 for p in self._proposals if p.is_stale(self._stale_threshold))

        board["total"] = len(self._proposals)
        board["blocked_count"] = len(board["exec_blocked"])
        board["receipted_count"] = len(board["exec_receipted"])
        board["failed_count"] = len(board["exec_failed"])
        board["orphan_count"] = orphan_count
        board["stale_count"] = stale_count
        board["stale_threshold_seconds"] = self._stale_threshold
        board["guard_reason_top"] = self._top_block_reasons()
        return board

    def _top_block_reasons(self, limit: int = 5) -> list[str]:
        """Top N blocking reasons."""
        from collections import Counter
        reasons = Counter()
        for p in self._proposals:
            if p.status == "EXEC_BLOCKED":
                for check_name, check_data in p.guard_checks.items():
                    if not check_data.get("passed"):
                        reasons[check_name] += 1
        return [f"{name}: {count}" for name, count in reasons.most_common(limit)]

    def get_proposals(self) -> list[dict]:
        return [p.to_dict() for p in self._proposals]

    def get_full_lineage(self, execution_proposal_id: str) -> Optional[dict]:
        """Trace lineage from execution proposal back to agent proposal."""
        for p in self._proposals:
            if p.proposal_id == execution_proposal_id:
                return {
                    "execution_proposal_id": p.proposal_id,
                    "agent_proposal_id": p.agent_proposal_id,
                    "status": p.status,
                    "execution_ready": p.execution_ready,
                    "receipt_id": p.receipt.receipt_id if p.receipt else None,
                    "created_at": p.created_at,
                }
        return None

    @property
    def count(self) -> int:
        return len(self._proposals)

    # ── Flush ─────────────────────────────────────────────────────────── #

    def flush_to_file(self, path: str = "data/execution_action_history.json") -> int:
        """Flush buffer to JSON file. Returns count flushed."""
        if not self._proposals:
            return 0

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        existing = []
        if out.exists():
            try:
                existing = json.loads(out.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = []

        new_entries = [p.to_dict() for p in self._proposals]
        combined = existing + new_entries
        if len(combined) > 500:
            combined = combined[-500:]

        out.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
        count = len(new_entries)
        self._proposals.clear()
        return count

    def _enforce_buffer_limit(self) -> None:
        if len(self._proposals) > self._max_buffer:
            self.flush_to_file()
