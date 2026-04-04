"""Promotion Gate — 5-check eligibility evaluator for paper candidacy.

Phase 4B of CR-048.

Evaluates whether a strategy×symbol×timeframe combination is eligible
for paper shadow observation.  All 5 checks must pass:
  1. Screening Status — must be CORE
  2. Qualification Status — must be PASS
  3. Not Excluded — symbol must not be EXCLUDED
  4. Safe Mode — system must not be in safe mode
  5. No Drift — no unprocessed runtime drift events

Stateless — all state is in input/output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.paper_shadow import (
    PromotionEligibility,
    EligibilityBlockReason,
)


# ── Eligibility Input Contract ──────────────────────────────────────


@dataclass
class EligibilityInput:
    """Input contract for the 5-check promotion gate."""

    strategy_id: str = ""
    symbol: str = ""
    timeframe: str = ""

    # From Symbol model
    screening_status: str = ""  # "core" / "watch" / "excluded"
    qualification_status: str = ""  # "unchecked" / "pass" / "fail"
    is_excluded: bool = False  # True if status == EXCLUDED

    # System state
    safe_mode_active: bool = False  # True if not NORMAL
    drift_active: bool = False  # True if unprocessed drift events exist


# ── Check Result ────────────────────────────────────────────────────


@dataclass
class EligibilityCheck:
    """Result of a single eligibility check."""

    check_name: str
    passed: bool
    reason: EligibilityBlockReason | None = None


# ── Eligibility Output ──────────────────────────────────────────────


@dataclass
class EligibilityOutput:
    """Complete eligibility result for one strategy×symbol evaluation."""

    strategy_id: str = ""
    symbol: str = ""
    timeframe: str = ""
    checks: list[EligibilityCheck] = field(default_factory=list)
    all_passed: bool = False
    decision: PromotionEligibility = PromotionEligibility.PAPER_FAIL
    block_reason: EligibilityBlockReason | None = None


# ── Promotion Gate Engine ───────────────────────────────────────────


class PromotionGate:
    """5-check eligibility evaluator.

    Stateless — all state is in input/output.
    Each check is a separate method for testability.
    """

    def evaluate(self, inp: EligibilityInput) -> EligibilityOutput:
        """Run all 5 checks. Return aggregate result."""

        output = EligibilityOutput(
            strategy_id=inp.strategy_id,
            symbol=inp.symbol,
            timeframe=inp.timeframe,
        )

        checks = [
            self._check_screening_status(inp),
            self._check_qualification_status(inp),
            self._check_not_excluded(inp),
            self._check_safe_mode(inp),
            self._check_no_drift(inp),
        ]
        output.checks = checks

        if all(c.passed for c in checks):
            output.all_passed = True
            output.decision = PromotionEligibility.ELIGIBLE_FOR_PAPER
        else:
            first_fail = next(c for c in checks if not c.passed)
            output.block_reason = first_fail.reason

            # Map to appropriate decision based on failure type
            if first_fail.reason == EligibilityBlockReason.RUNTIME_DRIFT_ACTIVE:
                output.decision = PromotionEligibility.QUARANTINE_CANDIDATE
            elif first_fail.reason == EligibilityBlockReason.SAFE_MODE_ACTIVE:
                output.decision = PromotionEligibility.PAPER_HOLD
            else:
                output.decision = PromotionEligibility.PAPER_FAIL

        return output

    # ── Individual Checks ────────────────────────────────────────────

    def _check_screening_status(self, inp: EligibilityInput) -> EligibilityCheck:
        """Check 1: screening_status must be CORE."""
        if inp.screening_status != "core":
            return EligibilityCheck(
                "screening_status",
                False,
                EligibilityBlockReason.SCREENING_NOT_CORE,
            )
        return EligibilityCheck("screening_status", True)

    def _check_qualification_status(self, inp: EligibilityInput) -> EligibilityCheck:
        """Check 2: qualification_status must be PASS."""
        if inp.qualification_status != "pass":
            return EligibilityCheck(
                "qualification_status",
                False,
                EligibilityBlockReason.QUALIFICATION_NOT_PASS,
            )
        return EligibilityCheck("qualification_status", True)

    def _check_not_excluded(self, inp: EligibilityInput) -> EligibilityCheck:
        """Check 3: symbol must not be EXCLUDED."""
        if inp.is_excluded:
            return EligibilityCheck(
                "not_excluded",
                False,
                EligibilityBlockReason.SYMBOL_EXCLUDED,
            )
        return EligibilityCheck("not_excluded", True)

    def _check_safe_mode(self, inp: EligibilityInput) -> EligibilityCheck:
        """Check 4: system must not be in safe mode."""
        if inp.safe_mode_active:
            return EligibilityCheck(
                "safe_mode",
                False,
                EligibilityBlockReason.SAFE_MODE_ACTIVE,
            )
        return EligibilityCheck("safe_mode", True)

    def _check_no_drift(self, inp: EligibilityInput) -> EligibilityCheck:
        """Check 5: no unprocessed runtime drift events."""
        if inp.drift_active:
            return EligibilityCheck(
                "no_drift",
                False,
                EligibilityBlockReason.RUNTIME_DRIFT_ACTIVE,
            )
        return EligibilityCheck("no_drift", True)
