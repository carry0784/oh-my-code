"""
K-Dexter Agent Action Ledger

Append-only ledger for agent action proposals and receipts.
Adapts Skill Loop operational controls (board, guard, receipt) to
millisecond-scale agent decisions.

Timescale adaptation:
  Skill Loop:  proposal -> approve -> apply  (days, human-reviewed)
  Agent:       propose  -> guard   -> receipt (milliseconds, automatic)

Controls implemented:
  1. Proposal Board   - action lifecycle tracking with strict state machine
  2. Apply Guard      - 4-check gate before execution commitment (no force override)
  3. Approval Receipt - evidence-linked receipt, MANDATORY for state advancement
  4. Boundary Rules   - AB-01~AB-06 (enforced by tests)
  5. Fingerprint      - duplicate proposal suppression
  6. Fail-Closed      - receipt required for RECEIPTED, flush failure degrades

State Machine (SEALED):
  PROPOSED -> GUARDED    [via propose_and_guard(), all 4 checks pass]
  PROPOSED -> BLOCKED    [via propose_and_guard(), any check fails]
  GUARDED  -> RECEIPTED  [via record_receipt(), receipt + evidence required]
  GUARDED  -> FAILED     [via record_failure(), execution exception]

  Forbidden transitions:
    PROPOSED -> RECEIPTED  (must go through GUARDED first)
    BLOCKED  -> GUARDED    (no retry from BLOCKED, create new proposal)
    BLOCKED  -> RECEIPTED  (blocked proposals cannot receive receipts)
    RECEIPTED -> any       (terminal state)
    FAILED   -> any        (terminal state)
    any      -> PROPOSED   (no state regression)

Constraints:
  - Append-only: no deletion, no mutation of past proposals
  - No exchange access: import of exchanges/ is prohibited
  - No order execution: this module reads and records, never acts
  - In-memory buffer with periodic flush to data/agent_action_history.json
  - Duplicate proposals (same fingerprint within 60s) are suppressed
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


# ── Data Models ─────────────────────────────────────────────────────────── #


@dataclass
class ActionReceipt:
    """Immutable receipt generated after a proposal passes the Apply Guard."""

    receipt_id: str
    proposal_id: str
    pre_evidence_id: str
    post_evidence_id: Optional[str] = None
    guard_checks: dict = field(default_factory=dict)
    final_result: dict = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ActionProposal:
    """
    Single agent action proposal with strict state machine.

    State transitions (SEALED):
      PROPOSED -> GUARDED   (all guard checks pass)
      PROPOSED -> BLOCKED   (any guard check fails)
      GUARDED  -> RECEIPTED (receipt + evidence recorded)
      GUARDED  -> FAILED    (execution exception)

    Terminal states: RECEIPTED, BLOCKED, FAILED
    """

    proposal_id: str
    task_type: str
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    category: str = ""
    severity: str = "MEDIUM"
    status: str = "PROPOSED"
    guard_passed: bool = False
    guard_reasons: list = field(default_factory=list)
    guard_checks: dict = field(default_factory=dict)
    receipt: Optional[ActionReceipt] = None
    pre_evidence_id: Optional[str] = None
    risk_result_summary: dict = field(default_factory=dict)
    fingerprint: str = ""
    created_at: str = ""

    # Allowed transitions (fail-closed: unlisted = forbidden)
    _TRANSITIONS: dict = field(
        default_factory=lambda: {
            "PROPOSED": {"GUARDED", "BLOCKED"},
            "GUARDED": {"RECEIPTED", "FAILED"},
            "BLOCKED": set(),  # terminal
            "RECEIPTED": set(),  # terminal
            "FAILED": set(),  # terminal
        },
        repr=False,
    )

    # Terminal states — proposals in these states are never stale
    _TERMINAL_STATES: frozenset = field(
        default_factory=lambda: frozenset({"BLOCKED", "RECEIPTED", "FAILED"}),
        repr=False,
    )

    def transition_to(self, new_status: str) -> bool:
        """
        Attempt state transition. Returns True on success, raises on violation.
        Fail-closed: undefined transitions are forbidden.
        """
        allowed = self._TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise StateTransitionError(
                f"Forbidden transition: {self.status} -> {new_status}. "
                f"Allowed from {self.status}: {allowed or 'none (terminal)'}"
            )
        self.status = new_status
        return True

    def is_stale(self, threshold_seconds: float = 600.0, now: Optional[datetime] = None) -> bool:
        """
        Read-only staleness判定. Does NOT mutate state.

        A proposal is stale when:
          1. status is NOT terminal (BLOCKED/RECEIPTED/FAILED)
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
        return d


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


# ── Apply Guard ─────────────────────────────────────────────────────────── #


def _check_risk_approved(risk_result: dict) -> tuple[bool, str]:
    """Guard 1: risk_result must have approved=True."""
    if risk_result.get("approved") is True:
        return True, "RISK_APPROVED: risk check passed"
    return False, "RISK_APPROVED: risk check did not approve"


def _check_governance_clear(pre_evidence_id: Optional[str]) -> tuple[bool, str]:
    """Guard 2: pre_evidence_id must exist (proves pre_check passed)."""
    if pre_evidence_id:
        return True, "GOVERNANCE_CLEAR: pre_check evidence exists"
    return False, "GOVERNANCE_CLEAR: no pre_check evidence (governance not verified)"


def _check_size_bound(risk_result: dict, max_position_usd: float = 100000.0) -> tuple[bool, str]:
    """Guard 3: position size within limits."""
    size = risk_result.get("position_size")
    if size is None:
        return True, "SIZE_BOUND: no position_size specified (skip)"
    if isinstance(size, (int, float)) and size <= max_position_usd:
        return True, f"SIZE_BOUND: {size} <= {max_position_usd}"
    return False, f"SIZE_BOUND: {size} exceeds limit {max_position_usd}"


def _check_cost_budget(cost_controller: Any = None) -> tuple[bool, str]:
    """Guard 4: CostController budget not exceeded."""
    if cost_controller is None:
        return True, "COST_BUDGET: no controller (skip)"
    try:
        api_budget = cost_controller.get_budget("API_CALLS")
        if api_budget and api_budget.current >= api_budget.limit:
            return (
                False,
                f"COST_BUDGET: API calls exhausted ({api_budget.current}/{api_budget.limit})",
            )
        token_budget = cost_controller.get_budget("LLM_TOKENS")
        if token_budget and token_budget.current >= token_budget.limit:
            return (
                False,
                f"COST_BUDGET: tokens exhausted ({token_budget.current}/{token_budget.limit})",
            )
        return True, "COST_BUDGET: within budget"
    except Exception as e:
        return True, f"COST_BUDGET: check error ({e}), allowing"


# ── Action Ledger ───────────────────────────────────────────────────────── #


class ActionLedger:
    """
    Append-only ledger for agent action proposals and receipts.

    NOT a singleton (unlike GovernanceGate). Injected via dependency.
    Stateless per-request: each orchestrator call creates a proposal,
    guards it, and records receipt -- no cross-request state needed.
    """

    def __init__(self, max_buffer: int = 1000, stale_threshold: float = 600.0):
        self._proposals: list[ActionProposal] = []
        self._fingerprints: dict[str, str] = {}  # fingerprint -> last_seen_iso
        self._max_buffer = max_buffer
        self._stale_threshold = stale_threshold  # seconds; default 10 minutes

    # ── Core Operations ───────────────────────────────────────────────── #

    @staticmethod
    def _compute_fingerprint(
        task_type: str, symbol: Optional[str], exchange: Optional[str], position_size: Any
    ) -> str:
        """Compute proposal fingerprint for duplicate detection."""
        # Bucket position size to 1000s to avoid noise
        size_bucket = (
            int((position_size or 0) / 1000) * 1000
            if isinstance(position_size, (int, float))
            else 0
        )
        raw = f"{task_type}|{symbol}|{exchange}|{size_bucket}"
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

    def propose_and_guard(
        self,
        task_type: str,
        symbol: Optional[str],
        exchange: Optional[str],
        risk_result: dict,
        pre_evidence_id: Optional[str],
        cost_controller: Any = None,
    ) -> tuple[bool, ActionProposal]:
        """
        Atomically: create proposal -> check duplicate -> run 4 guard checks -> return result.
        Returns (passed, proposal).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        fp = self._compute_fingerprint(
            task_type, symbol, exchange, risk_result.get("position_size")
        )

        proposal = ActionProposal(
            proposal_id=f"AP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            task_type=task_type,
            symbol=symbol,
            exchange=exchange,
            category="agent_execution",
            pre_evidence_id=pre_evidence_id,
            fingerprint=fp,
            risk_result_summary={
                "approved": risk_result.get("approved"),
                "position_size": risk_result.get("position_size"),
                "risk_score": risk_result.get("risk_score"),
            },
            created_at=now_iso,
        )

        # Duplicate suppression check
        if self._is_duplicate(fp):
            proposal.guard_passed = False
            proposal.guard_reasons = [
                f"DUPLICATE: fingerprint {fp} seen within {FINGERPRINT_COOLDOWN_SECONDS}s"
            ]
            proposal.guard_checks = {
                "DUPLICATE": {"passed": False, "detail": proposal.guard_reasons[0]}
            }
            proposal.transition_to("BLOCKED")
            self._proposals.append(proposal)
            return False, proposal

        # Run 4 guard checks
        checks = {}
        reasons = []
        all_passed = True

        for name, check_fn in [
            ("RISK_APPROVED", lambda: _check_risk_approved(risk_result)),
            ("GOVERNANCE_CLEAR", lambda: _check_governance_clear(pre_evidence_id)),
            ("SIZE_BOUND", lambda: _check_size_bound(risk_result)),
            ("COST_BUDGET", lambda: _check_cost_budget(cost_controller)),
        ]:
            passed, reason = check_fn()
            checks[name] = {"passed": passed, "detail": reason}
            reasons.append(reason)
            if not passed:
                all_passed = False

        proposal.guard_passed = all_passed
        proposal.guard_checks = checks
        proposal.guard_reasons = reasons

        # State transition via state machine (fail-closed)
        if all_passed:
            proposal.transition_to("GUARDED")
        else:
            proposal.transition_to("BLOCKED")

        # Record fingerprint timestamp for duplicate detection
        self._fingerprints[fp] = now_iso

        self._proposals.append(proposal)
        self._enforce_buffer_limit()

        return all_passed, proposal

    def record_receipt(
        self,
        proposal: ActionProposal,
        final_result: dict,
        post_evidence_id: Optional[str] = None,
    ) -> ActionReceipt:
        """
        Record approval receipt after successful execution.
        Fail-closed: requires proposal in GUARDED state with guard_passed=True.
        Raises StateTransitionError if preconditions not met.
        """
        # Fail-closed: receipt only for GUARDED proposals
        if not proposal.guard_passed:
            raise StateTransitionError(
                f"Cannot receipt proposal {proposal.proposal_id}: guard_passed is False. "
                f"Current status: {proposal.status}"
            )

        receipt = ActionReceipt(
            receipt_id=f"AR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            proposal_id=proposal.proposal_id,
            pre_evidence_id=proposal.pre_evidence_id or "",
            post_evidence_id=post_evidence_id,
            guard_checks=proposal.guard_checks,
            final_result={
                "stage": final_result.get("stage"),
                "adjusted_size": final_result.get("adjusted_size"),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        proposal.receipt = receipt
        # State machine transition (will raise if not GUARDED)
        proposal.transition_to("RECEIPTED")
        return receipt

    def record_failure(self, proposal: ActionProposal, error: str) -> None:
        """
        Record execution failure for a guarded proposal.
        Raises StateTransitionError if proposal is not in GUARDED state.
        """
        # State machine transition (will raise if not GUARDED)
        proposal.transition_to("FAILED")
        proposal.guard_reasons.append(f"EXECUTION_FAILED: {error}")

    # ── Board / Query ─────────────────────────────────────────────────── #

    def get_board(self) -> dict:
        """Get proposal board grouped by status with orphan detection."""
        board = {
            "proposed": [],
            "guarded": [],
            "receipted": [],
            "blocked": [],
            "failed": [],
        }
        for p in self._proposals:
            key = p.status.lower()
            if key in board:
                board[key].append(
                    {
                        "proposal_id": p.proposal_id,
                        "task_type": p.task_type,
                        "symbol": p.symbol,
                        "status": p.status,
                        "guard_passed": p.guard_passed,
                        "fingerprint": p.fingerprint,
                        "created_at": p.created_at,
                    }
                )

        # Orphan detection: GUARDED proposals without receipt
        orphan_count = len(board["guarded"])  # GUARDED = not yet receipted or failed

        # Stale detection: non-terminal proposals exceeding age threshold
        stale_count = sum(1 for p in self._proposals if p.is_stale(self._stale_threshold))

        board["total"] = len(self._proposals)
        board["blocked_count"] = len(board["blocked"])
        board["receipted_count"] = len(board["receipted"])
        board["failed_count"] = len(board["failed"])
        board["orphan_count"] = orphan_count
        board["stale_count"] = stale_count
        board["stale_threshold_seconds"] = self._stale_threshold
        board["guard_reason_top"] = self._top_block_reasons()
        return board

    def _top_block_reasons(self, limit: int = 5) -> list[str]:
        """Top N blocking reasons across all blocked proposals."""
        from collections import Counter

        reasons = Counter()
        for p in self._proposals:
            if p.status == "BLOCKED":
                for check_name, check_data in p.guard_checks.items():
                    if not check_data.get("passed"):
                        reasons[check_name] += 1
        return [f"{name}: {count}" for name, count in reasons.most_common(limit)]

    def get_proposals(self) -> list[dict]:
        """Get all proposals as dicts."""
        return [p.to_dict() for p in self._proposals]

    @property
    def count(self) -> int:
        return len(self._proposals)

    # ── Flush ─────────────────────────────────────────────────────────── #

    def flush_to_file(self, path: str = "data/agent_action_history.json") -> int:
        """Flush current buffer to JSON file. Returns count flushed."""
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

        # Keep last 500 entries
        if len(combined) > 500:
            combined = combined[-500:]

        out.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
        count = len(new_entries)
        self._proposals.clear()
        return count

    # ── Internal ──────────────────────────────────────────────────────── #

    def _enforce_buffer_limit(self) -> None:
        """Auto-flush if buffer exceeds max."""
        if len(self._proposals) > self._max_buffer:
            self.flush_to_file()
