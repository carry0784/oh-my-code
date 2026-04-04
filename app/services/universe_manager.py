"""Universe Manager — eligible symbol set computation.

Phase 6A of CR-048.  Computes the set of symbols eligible for
strategy execution at a given point in time.

Universe selection contract (all must hold):
  1. Symbol.status == CORE
  2. Symbol.qualification_status == "pass"
  3. Symbol.promotion_eligibility_status in {eligible_for_paper, paper_pass}
  4. Symbol.paper_evaluation_status == "pass"
  5. Symbol.candidate_expire_at > now  (TTL not expired)
  6. System not in safe mode
  7. No unprocessed drift

Each selection produces a selection_reason_snapshot for audit.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


# ── Selection Result ──────────────────────────────────────────────────


class SelectionOutcome(str, Enum):
    SELECTED = "selected"
    EXCLUDED_STATUS = "excluded_status"
    EXCLUDED_QUALIFICATION = "excluded_qualification"
    EXCLUDED_PROMOTION = "excluded_promotion"
    EXCLUDED_PAPER_EVAL = "excluded_paper_eval"
    EXCLUDED_TTL_EXPIRED = "excluded_ttl_expired"
    EXCLUDED_SAFE_MODE = "excluded_safe_mode"
    EXCLUDED_DRIFT = "excluded_drift"


ELIGIBLE_PROMOTION_STATUSES = frozenset(
    {
        "eligible_for_paper",
        "paper_pass",
    }
)


@dataclass
class SymbolSelectionResult:
    """Result of evaluating one symbol for universe inclusion."""

    symbol_id: str
    symbol: str
    outcome: SelectionOutcome
    reason_snapshot: dict = field(default_factory=dict)


@dataclass
class UniverseSnapshot:
    """Result of a full universe selection cycle."""

    selected: list[SymbolSelectionResult] = field(default_factory=list)
    excluded: list[SymbolSelectionResult] = field(default_factory=list)
    total_evaluated: int = 0
    safe_mode_active: bool = False
    drift_active: bool = False
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def selected_symbols(self) -> list[str]:
        return [r.symbol for r in self.selected]

    @property
    def selected_symbol_ids(self) -> list[str]:
        return [r.symbol_id for r in self.selected]


# ── Universe Manager (stateless engine) ───────────────────────────────


class UniverseManager:
    """Stateless universe selection engine.

    Evaluates all candidate symbols against the selection contract.
    No short-circuit: all symbols evaluated, all reasons recorded.
    """

    def select(
        self,
        symbols: list[dict],
        *,
        safe_mode_active: bool = False,
        drift_active: bool = False,
        now: datetime | None = None,
    ) -> UniverseSnapshot:
        """Evaluate symbols and return universe snapshot.

        Args:
            symbols: list of dicts with keys:
                symbol_id, symbol, status, qualification_status,
                promotion_eligibility_status, paper_evaluation_status,
                candidate_expire_at (datetime | None)
            safe_mode_active: system safe mode state
            drift_active: unprocessed drift state
            now: current time (default: utcnow)

        Returns:
            UniverseSnapshot with selected/excluded symbols and reasons.
        """
        now = now or datetime.now(timezone.utc)
        selected = []
        excluded = []

        for sym in symbols:
            result = self._evaluate_symbol(
                sym,
                safe_mode_active=safe_mode_active,
                drift_active=drift_active,
                now=now,
            )
            if result.outcome == SelectionOutcome.SELECTED:
                selected.append(result)
            else:
                excluded.append(result)

        return UniverseSnapshot(
            selected=selected,
            excluded=excluded,
            total_evaluated=len(symbols),
            safe_mode_active=safe_mode_active,
            drift_active=drift_active,
            computed_at=now,
        )

    def _evaluate_symbol(
        self,
        sym: dict,
        *,
        safe_mode_active: bool,
        drift_active: bool,
        now: datetime,
    ) -> SymbolSelectionResult:
        """Evaluate a single symbol against all selection criteria."""
        sid = sym["symbol_id"]
        name = sym["symbol"]

        snapshot = {
            "status": sym.get("status"),
            "qualification_status": sym.get("qualification_status"),
            "promotion_eligibility_status": sym.get("promotion_eligibility_status"),
            "paper_evaluation_status": sym.get("paper_evaluation_status"),
            "candidate_expire_at": (
                sym["candidate_expire_at"].isoformat() if sym.get("candidate_expire_at") else None
            ),
            "safe_mode_active": safe_mode_active,
            "drift_active": drift_active,
        }

        # Check 1: safe mode
        if safe_mode_active:
            return SymbolSelectionResult(sid, name, SelectionOutcome.EXCLUDED_SAFE_MODE, snapshot)

        # Check 2: drift
        if drift_active:
            return SymbolSelectionResult(sid, name, SelectionOutcome.EXCLUDED_DRIFT, snapshot)

        # Check 3: status == CORE
        if sym.get("status") != "core":
            return SymbolSelectionResult(sid, name, SelectionOutcome.EXCLUDED_STATUS, snapshot)

        # Check 4: qualification_status == pass
        if sym.get("qualification_status") != "pass":
            return SymbolSelectionResult(
                sid, name, SelectionOutcome.EXCLUDED_QUALIFICATION, snapshot
            )

        # Check 5: promotion_eligibility_status in eligible set
        if sym.get("promotion_eligibility_status") not in ELIGIBLE_PROMOTION_STATUSES:
            return SymbolSelectionResult(sid, name, SelectionOutcome.EXCLUDED_PROMOTION, snapshot)

        # Check 6: paper_evaluation_status == pass
        if sym.get("paper_evaluation_status") != "pass":
            return SymbolSelectionResult(sid, name, SelectionOutcome.EXCLUDED_PAPER_EVAL, snapshot)

        # Check 7: TTL not expired
        expire_at = sym.get("candidate_expire_at")
        if expire_at is not None:
            if expire_at.tzinfo is None:
                expire_at = expire_at.replace(tzinfo=timezone.utc)
            if now >= expire_at:
                return SymbolSelectionResult(
                    sid, name, SelectionOutcome.EXCLUDED_TTL_EXPIRED, snapshot
                )

        # All checks passed
        return SymbolSelectionResult(sid, name, SelectionOutcome.SELECTED, snapshot)
