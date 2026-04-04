"""Runtime Strategy Loader — load eligibility gate for approved strategies.

Phase 5A of CR-048.  This is the execution entry gate: only strategies
that satisfy all 4 status axes + system guards are eligible for runtime load.

Load eligibility policy (all must hold):
  1. Symbol.screening_status == CORE
  2. Symbol.qualification_status == "pass"
  3. Symbol.promotion_eligibility_status in {eligible_for_paper, paper_pass}
  4. Symbol.paper_evaluation_status == "pass"
  5. Strategy.status in {PAPER_PASS, GUARDED_LIVE, LIVE}
  6. Strategy checksum matches (immutability zone)
  7. Safe mode == NORMAL
  8. No unprocessed drift

Each load attempt produces an append-only LoadDecisionReceipt.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


# ── Load Decision ──────────────────────────────────────────────────────


class LoadDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class LoadRejectReason(str, Enum):
    SCREENING_NOT_CORE = "screening_not_core"
    QUALIFICATION_NOT_PASS = "qualification_not_pass"
    PROMOTION_NOT_ELIGIBLE = "promotion_not_eligible"
    PAPER_EVAL_NOT_PASS = "paper_eval_not_pass"
    STRATEGY_STATUS_INELIGIBLE = "strategy_status_ineligible"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    FEATURE_PACK_MISMATCH = "feature_pack_mismatch"
    SAFE_MODE_ACTIVE = "safe_mode_active"
    DRIFT_ACTIVE = "drift_active"
    PAPER_PASS_STALE = "paper_pass_stale"
    SYMBOL_NOT_FOUND = "symbol_not_found"
    STRATEGY_NOT_FOUND = "strategy_not_found"
    FEATURE_PACK_NOT_FOUND = "feature_pack_not_found"


# ── Eligible strategy statuses ─────────────────────────────────────────

LOADABLE_STRATEGY_STATUSES = frozenset(
    {
        "PAPER_PASS",
        "GUARDED_LIVE",
        "LIVE",
    }
)

LOADABLE_PROMOTION_STATUSES = frozenset(
    {
        "eligible_for_paper",
        "paper_pass",
    }
)


# ── Check result ───────────────────────────────────────────────────────


@dataclass
class LoadCheck:
    """Result of a single load eligibility check."""

    check_name: str
    passed: bool
    reason: LoadRejectReason | None = None
    detail: str | None = None


@dataclass
class LoadEligibilityOutput:
    """Aggregate load eligibility result."""

    strategy_id: str = ""
    symbol_id: str = ""
    timeframe: str = ""
    decision: LoadDecision = LoadDecision.REJECTED
    checks: list[LoadCheck] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    primary_reason: LoadRejectReason | None = None
    status_snapshot: dict | None = None


# ── Load Eligibility Engine (stateless) ────────────────────────────────


class LoadEligibilityChecker:
    """Stateless 8-check load eligibility engine.

    All checks run (no short-circuit) to provide full visibility
    into all reasons a load would be rejected.
    """

    def check(
        self,
        *,
        screening_status: str,
        qualification_status: str,
        promotion_eligibility_status: str,
        paper_evaluation_status: str,
        strategy_status: str,
        checksum_expected: str | None,
        checksum_actual: str | None,
        fp_fingerprint_expected: str | None = None,
        fp_fingerprint_actual: str | None = None,
        safe_mode_active: bool,
        drift_active: bool,
        paper_pass_fresh: bool = True,
    ) -> LoadEligibilityOutput:
        checks: list[LoadCheck] = []

        # Check 1: screening_status == CORE
        c1 = screening_status == "core"
        checks.append(
            LoadCheck(
                check_name="screening_status_core",
                passed=c1,
                reason=None if c1 else LoadRejectReason.SCREENING_NOT_CORE,
                detail=f"screening_status={screening_status}",
            )
        )

        # Check 2: qualification_status == pass
        c2 = qualification_status == "pass"
        checks.append(
            LoadCheck(
                check_name="qualification_status_pass",
                passed=c2,
                reason=None if c2 else LoadRejectReason.QUALIFICATION_NOT_PASS,
                detail=f"qualification_status={qualification_status}",
            )
        )

        # Check 3: promotion_eligibility_status in eligible set
        c3 = promotion_eligibility_status in LOADABLE_PROMOTION_STATUSES
        checks.append(
            LoadCheck(
                check_name="promotion_eligible",
                passed=c3,
                reason=None if c3 else LoadRejectReason.PROMOTION_NOT_ELIGIBLE,
                detail=f"promotion_eligibility_status={promotion_eligibility_status}",
            )
        )

        # Check 4: paper_evaluation_status == pass
        c4 = paper_evaluation_status == "pass"
        checks.append(
            LoadCheck(
                check_name="paper_evaluation_pass",
                passed=c4,
                reason=None if c4 else LoadRejectReason.PAPER_EVAL_NOT_PASS,
                detail=f"paper_evaluation_status={paper_evaluation_status}",
            )
        )

        # Check 5: strategy status in loadable set
        c5 = strategy_status in LOADABLE_STRATEGY_STATUSES
        checks.append(
            LoadCheck(
                check_name="strategy_status_loadable",
                passed=c5,
                reason=None if c5 else LoadRejectReason.STRATEGY_STATUS_INELIGIBLE,
                detail=f"strategy_status={strategy_status}",
            )
        )

        # Check 6: strategy checksum match (immutability zone)
        if checksum_expected is not None and checksum_actual is not None:
            c6 = checksum_expected == checksum_actual
        else:
            c6 = True  # no checksum to verify = pass
        checks.append(
            LoadCheck(
                check_name="checksum_match",
                passed=c6,
                reason=None if c6 else LoadRejectReason.CHECKSUM_MISMATCH,
                detail=f"expected={checksum_expected}, actual={checksum_actual}",
            )
        )

        # Check 6b: feature pack fingerprint match
        if fp_fingerprint_expected is not None and fp_fingerprint_actual is not None:
            c6b = fp_fingerprint_expected == fp_fingerprint_actual
        else:
            c6b = True  # no FP fingerprint = pass
        checks.append(
            LoadCheck(
                check_name="feature_pack_match",
                passed=c6b,
                reason=None if c6b else LoadRejectReason.FEATURE_PACK_MISMATCH,
                detail=f"fp_expected={fp_fingerprint_expected}, fp_actual={fp_fingerprint_actual}",
            )
        )

        # Check 7: safe mode not active
        c7 = not safe_mode_active
        checks.append(
            LoadCheck(
                check_name="safe_mode_normal",
                passed=c7,
                reason=None if c7 else LoadRejectReason.SAFE_MODE_ACTIVE,
            )
        )

        # Check 8: no drift
        c8 = not drift_active
        checks.append(
            LoadCheck(
                check_name="no_drift",
                passed=c8,
                reason=None if c8 else LoadRejectReason.DRIFT_ACTIVE,
            )
        )

        # Check 9: paper pass freshness
        c9 = paper_pass_fresh
        checks.append(
            LoadCheck(
                check_name="paper_pass_fresh",
                passed=c9,
                reason=None if c9 else LoadRejectReason.PAPER_PASS_STALE,
            )
        )

        # Aggregate
        failed = [c for c in checks if not c.passed]
        all_passed = len(failed) == 0

        status_snapshot = {
            "screening_status": screening_status,
            "qualification_status": qualification_status,
            "promotion_eligibility_status": promotion_eligibility_status,
            "paper_evaluation_status": paper_evaluation_status,
            "strategy_status": strategy_status,
            "strategy_fingerprint": checksum_actual,
            "fp_fingerprint": fp_fingerprint_actual,
            "safe_mode_active": safe_mode_active,
            "drift_active": drift_active,
            "paper_pass_fresh": paper_pass_fresh,
        }

        return LoadEligibilityOutput(
            decision=LoadDecision.APPROVED if all_passed else LoadDecision.REJECTED,
            checks=checks,
            failed_checks=[c.check_name for c in failed],
            primary_reason=failed[0].reason if failed else None,
            status_snapshot=status_snapshot,
        )
