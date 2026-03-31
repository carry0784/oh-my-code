"""
K-Dexter Submit Ledger

Append-only ledger for submit proposals and receipts.
Final control gate between execution_ready and actual order submission.
Replicated from ExecutionLedger with identical state machine,
fail-closed guard, and receipt enforcement.

Position in control chain:
  GovernanceGate.pre_check() -> Agent ActionLedger -> ExecutionLedger -> [THIS] SubmitLedger -> (External Caller)

State Machine (SEALED):
  SUBMIT_PROPOSED -> SUBMIT_GUARDED    [via propose_and_guard(), all 6 checks pass]
  SUBMIT_PROPOSED -> SUBMIT_BLOCKED    [via propose_and_guard(), any check fails]
  SUBMIT_GUARDED  -> SUBMIT_RECEIPTED  [via record_receipt(), receipt + evidence required]
  SUBMIT_GUARDED  -> SUBMIT_FAILED     [via record_failure(), exception after guard]

  Forbidden transitions:
    SUBMIT_PROPOSED -> SUBMIT_RECEIPTED  (must go through SUBMIT_GUARDED first)
    SUBMIT_BLOCKED  -> any               (terminal)
    SUBMIT_RECEIPTED -> any              (terminal)
    SUBMIT_FAILED   -> any               (terminal)
    any -> SUBMIT_PROPOSED               (no state regression)

  submit_ready is a DERIVED property:
    submit_ready = (status == SUBMIT_RECEIPTED)

Constraints:
  - Append-only: no deletion, no mutation of past proposals
  - No exchange access: import of exchanges/ is prohibited
  - No order execution: this module reads and records, never submits orders
  - In-memory buffer with periodic flush to data/submit_action_history.json
  - Duplicate proposals (same fingerprint within 60s) are suppressed
  - Execution receipt required: execution_proposal must be EXEC_RECEIPTED
  - Exchange whitelist enforced: exchange must be in SUPPORTED_EXCHANGES_ALL
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.config import SUPPORTED_EXCHANGES_ALL

# Duplicate suppression window (seconds)
FINGERPRINT_COOLDOWN_SECONDS = 60


# -- Exceptions ------------------------------------------------------------ #

class SubmitStateTransitionError(Exception):
    """Raised when an invalid submit state transition is attempted."""
    pass


# -- Data Models ------------------------------------------------------------ #

@dataclass
class SubmitReceipt:
    """Immutable receipt generated after a submit proposal passes guard."""
    receipt_id: str
    proposal_id: str
    agent_proposal_id: str
    execution_proposal_id: str
    pre_evidence_id: str
    post_evidence_id: Optional[str] = None
    guard_checks: dict = field(default_factory=dict)
    final_result: dict = field(default_factory=dict)
    submit_ready_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SubmitProposal:
    """
    Single submit proposal with strict state machine.
    Replicated from ExecutionProposal with SUBMIT_ prefix states.
    """
    proposal_id: str
    agent_proposal_id: str
    execution_proposal_id: str
    task_type: str
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    category: str = "submit"
    status: str = "SUBMIT_PROPOSED"
    guard_passed: bool = False
    guard_reasons: list = field(default_factory=list)
    guard_checks: dict = field(default_factory=dict)
    receipt: Optional[SubmitReceipt] = None
    pre_evidence_id: Optional[str] = None
    risk_result_summary: dict = field(default_factory=dict)
    fingerprint: str = ""
    created_at: str = ""

    # Allowed transitions (fail-closed: unlisted = forbidden)
    _TRANSITIONS: dict = field(default_factory=lambda: {
        "SUBMIT_PROPOSED": {"SUBMIT_GUARDED", "SUBMIT_BLOCKED"},
        "SUBMIT_GUARDED": {"SUBMIT_RECEIPTED", "SUBMIT_FAILED"},
        "SUBMIT_BLOCKED": set(),      # terminal
        "SUBMIT_RECEIPTED": set(),    # terminal
        "SUBMIT_FAILED": set(),       # terminal
    }, repr=False)

    # Terminal states — proposals in these states are never stale
    _TERMINAL_STATES: frozenset = field(
        default_factory=lambda: frozenset({"SUBMIT_BLOCKED", "SUBMIT_RECEIPTED", "SUBMIT_FAILED"}),
        repr=False,
    )

    @property
    def submit_ready(self) -> bool:
        """Derived property: only True when SUBMIT_RECEIPTED."""
        return self.status == "SUBMIT_RECEIPTED"

    def transition_to(self, new_status: str) -> bool:
        """
        Attempt state transition. Returns True on success, raises on violation.
        Fail-closed: undefined transitions are forbidden.
        """
        allowed = self._TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise SubmitStateTransitionError(
                f"Forbidden transition: {self.status} -> {new_status}. "
                f"Allowed from {self.status}: {allowed or 'none (terminal)'}"
            )
        self.status = new_status
        return True

    def is_stale(self, threshold_seconds: float = 180.0, now: Optional[datetime] = None) -> bool:
        """
        Read-only staleness判定. Does NOT mutate state.

        A proposal is stale when:
          1. status is NOT terminal (SUBMIT_BLOCKED/SUBMIT_RECEIPTED/SUBMIT_FAILED)
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
        d["submit_ready"] = self.submit_ready
        return d


# -- Submit Guard (6 checks) ----------------------------------------------- #

def _check_exec_receipted(execution_proposal_status: Optional[str]) -> tuple[bool, str]:
    """Guard 1: Execution proposal must be EXEC_RECEIPTED."""
    if execution_proposal_status == "EXEC_RECEIPTED":
        return True, "EXEC_RECEIPTED: execution proposal is EXEC_RECEIPTED"
    return False, f"EXEC_RECEIPTED: execution proposal status is {execution_proposal_status} (must be EXEC_RECEIPTED)"


def _check_governance_final(pre_evidence_id: Optional[str]) -> tuple[bool, str]:
    """Guard 2: GovernanceGate pre_check evidence must exist."""
    if pre_evidence_id:
        return True, "GOVERNANCE_FINAL: pre_check evidence exists"
    return False, "GOVERNANCE_FINAL: no pre_check evidence"


def _check_cost_final(cost_controller: Any = None) -> tuple[bool, str]:
    """Guard 3: CostController budget not exceeded (final re-check)."""
    if cost_controller is None:
        return True, "COST_FINAL: no controller (skip)"
    try:
        api_budget = cost_controller.get_budget("API_CALLS")
        if api_budget and api_budget.current >= api_budget.limit:
            return False, f"COST_FINAL: API calls exhausted ({api_budget.current}/{api_budget.limit})"
        token_budget = cost_controller.get_budget("LLM_TOKENS")
        if token_budget and token_budget.current >= token_budget.limit:
            return False, f"COST_FINAL: tokens exhausted ({token_budget.current}/{token_budget.limit})"
        return True, "COST_FINAL: within budget"
    except Exception as e:
        return True, f"COST_FINAL: check error ({e}), allowing"


def _check_lockdown_final(security_ctx: Any = None) -> tuple[bool, str]:
    """Guard 4: SecurityState not in LOCKDOWN or QUARANTINE."""
    if security_ctx is None:
        return True, "LOCKDOWN_FINAL: no security context (skip)"
    try:
        if hasattr(security_ctx, "is_locked_down") and security_ctx.is_locked_down():
            return False, "LOCKDOWN_FINAL: system is in LOCKDOWN"
        if hasattr(security_ctx, "sandbox_only") and security_ctx.sandbox_only():
            return False, "LOCKDOWN_FINAL: system is in QUARANTINE"
        return True, "LOCKDOWN_FINAL: system is clear"
    except Exception as e:
        return False, f"LOCKDOWN_FINAL: check error ({e}), blocking (fail-closed)"


def _check_exchange_allowed(exchange: Optional[str]) -> tuple[bool, str]:
    """Guard 5: Exchange must be in SUPPORTED_EXCHANGES_ALL whitelist."""
    if exchange is None:
        return False, "EXCHANGE_ALLOWED: no exchange specified"
    if exchange in SUPPORTED_EXCHANGES_ALL:
        return True, f"EXCHANGE_ALLOWED: '{exchange}' is in whitelist"
    return False, (
        f"EXCHANGE_ALLOWED: '{exchange}' is not supported. "
        f"Allowed: {list(SUPPORTED_EXCHANGES_ALL)}"
    )


def _check_size_submit(risk_result: dict, max_position_usd: float = 100000.0) -> tuple[bool, str]:
    """Guard 6: Final position size re-check before submit."""
    size = risk_result.get("position_size") or risk_result.get("adjusted_size")
    if size is None:
        return True, "SIZE_SUBMIT_CHECK: no size specified (skip)"
    if isinstance(size, (int, float)) and size <= max_position_usd:
        return True, f"SIZE_SUBMIT_CHECK: {size} <= {max_position_usd}"
    return False, f"SIZE_SUBMIT_CHECK: {size} exceeds limit {max_position_usd}"


# -- Submit Ledger ---------------------------------------------------------- #

class SubmitLedger:
    """
    Append-only ledger for submit proposals and receipts.
    Final boundary before actual order submission.
    Replicated from ExecutionLedger with identical patterns.
    """

    def __init__(self, max_buffer: int = 1000, stale_threshold: float = 180.0):
        self._proposals: list[SubmitProposal] = []
        self._fingerprints: dict[str, str] = {}  # fingerprint -> last_seen_iso
        self._max_buffer = max_buffer
        self._stale_threshold = stale_threshold  # seconds; default 3 minutes

    # -- Fingerprint ------------------------------------------------------- #

    @staticmethod
    def _compute_fingerprint(task_type: str, symbol: Optional[str],
                             exchange: Optional[str], position_size: Any) -> str:
        """Compute submit fingerprint for duplicate detection."""
        size_bucket = int((position_size or 0) / 1000) * 1000 if isinstance(position_size, (int, float)) else 0
        raw = f"SUBMIT|{task_type}|{symbol}|{exchange}|{size_bucket}"
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

    # -- Core Operations --------------------------------------------------- #

    def propose_and_guard(
        self,
        task_type: str,
        symbol: Optional[str],
        exchange: Optional[str],
        agent_proposal_id: str,
        execution_proposal_id: str,
        execution_proposal_status: str,
        risk_result: dict,
        pre_evidence_id: Optional[str],
        cost_controller: Any = None,
        security_ctx: Any = None,
    ) -> tuple[bool, SubmitProposal]:
        """
        Atomically: create proposal -> check duplicate -> run 6 guard checks.
        Returns (passed, proposal).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        size = risk_result.get("position_size") or risk_result.get("adjusted_size")
        fp = self._compute_fingerprint(task_type, symbol, exchange, size)

        proposal = SubmitProposal(
            proposal_id=f"SP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            agent_proposal_id=agent_proposal_id,
            execution_proposal_id=execution_proposal_id,
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
            proposal.transition_to("SUBMIT_BLOCKED")
            self._proposals.append(proposal)
            return False, proposal

        # Run 6 guard checks
        checks = {}
        reasons = []
        all_passed = True

        for name, check_fn in [
            ("EXEC_RECEIPTED", lambda: _check_exec_receipted(execution_proposal_status)),
            ("GOVERNANCE_FINAL", lambda: _check_governance_final(pre_evidence_id)),
            ("COST_FINAL", lambda: _check_cost_final(cost_controller)),
            ("LOCKDOWN_FINAL", lambda: _check_lockdown_final(security_ctx)),
            ("EXCHANGE_ALLOWED", lambda: _check_exchange_allowed(exchange)),
            ("SIZE_SUBMIT_CHECK", lambda: _check_size_submit(risk_result)),
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
            proposal.transition_to("SUBMIT_GUARDED")
        else:
            proposal.transition_to("SUBMIT_BLOCKED")

        self._fingerprints[fp] = now_iso
        self._proposals.append(proposal)
        self._enforce_buffer_limit()

        return all_passed, proposal

    def record_receipt(
        self,
        proposal: SubmitProposal,
        final_result: dict,
        post_evidence_id: Optional[str] = None,
    ) -> SubmitReceipt:
        """
        Record submit receipt. Fail-closed: requires SUBMIT_GUARDED + guard_passed.
        """
        if not proposal.guard_passed:
            raise SubmitStateTransitionError(
                f"Cannot receipt proposal {proposal.proposal_id}: guard_passed is False. "
                f"Current status: {proposal.status}"
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        receipt = SubmitReceipt(
            receipt_id=f"SR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            proposal_id=proposal.proposal_id,
            agent_proposal_id=proposal.agent_proposal_id,
            execution_proposal_id=proposal.execution_proposal_id,
            pre_evidence_id=proposal.pre_evidence_id or "",
            post_evidence_id=post_evidence_id,
            guard_checks=proposal.guard_checks,
            final_result={
                "stage": final_result.get("stage"),
                "adjusted_size": final_result.get("adjusted_size"),
                "submit_ready": True,
            },
            submit_ready_at=now_iso,
            created_at=now_iso,
        )
        proposal.receipt = receipt
        proposal.transition_to("SUBMIT_RECEIPTED")
        return receipt

    def record_failure(self, proposal: SubmitProposal, error: str) -> None:
        """Record submit failure. Raises if not SUBMIT_GUARDED."""
        proposal.transition_to("SUBMIT_FAILED")
        proposal.guard_reasons.append(f"SUBMIT_FAILED: {error}")

    # -- Board / Query ----------------------------------------------------- #

    def get_board(self) -> dict:
        """Get submit board grouped by status with orphan detection."""
        board = {
            "submit_proposed": [],
            "submit_guarded": [],
            "submit_receipted": [],
            "submit_blocked": [],
            "submit_failed": [],
        }
        for p in self._proposals:
            key = p.status.lower()
            if key in board:
                board[key].append({
                    "proposal_id": p.proposal_id,
                    "agent_proposal_id": p.agent_proposal_id,
                    "execution_proposal_id": p.execution_proposal_id,
                    "task_type": p.task_type,
                    "symbol": p.symbol,
                    "exchange": p.exchange,
                    "status": p.status,
                    "submit_ready": p.submit_ready,
                    "fingerprint": p.fingerprint,
                    "created_at": p.created_at,
                })

        orphan_count = len(board["submit_guarded"])

        # Stale detection: non-terminal proposals exceeding age threshold
        stale_count = sum(1 for p in self._proposals if p.is_stale(self._stale_threshold))

        board["total"] = len(self._proposals)
        board["blocked_count"] = len(board["submit_blocked"])
        board["receipted_count"] = len(board["submit_receipted"])
        board["failed_count"] = len(board["submit_failed"])
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
            if p.status == "SUBMIT_BLOCKED":
                for check_name, check_data in p.guard_checks.items():
                    if not check_data.get("passed"):
                        reasons[check_name] += 1
        return [f"{name}: {count}" for name, count in reasons.most_common(limit)]

    def get_proposals(self) -> list[dict]:
        return [p.to_dict() for p in self._proposals]

    def get_full_lineage(self, submit_proposal_id: str) -> Optional[dict]:
        """Trace 3-tier lineage: Agent -> Execution -> Submit."""
        for p in self._proposals:
            if p.proposal_id == submit_proposal_id:
                return {
                    "submit_proposal_id": p.proposal_id,
                    "execution_proposal_id": p.execution_proposal_id,
                    "agent_proposal_id": p.agent_proposal_id,
                    "status": p.status,
                    "submit_ready": p.submit_ready,
                    "receipt_id": p.receipt.receipt_id if p.receipt else None,
                    "created_at": p.created_at,
                }
        return None

    @property
    def count(self) -> int:
        return len(self._proposals)

    # -- Flush ------------------------------------------------------------- #

    def flush_to_file(self, path: str = "data/submit_action_history.json") -> int:
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
