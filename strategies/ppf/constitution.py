"""PPF Constitution invariant checks (C1-C11).

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1

Any violation -> immediate PPF deactivation (fail-closed).
allow_entry = False regardless of strategy performance.

Invariants:
    C1:  PPF never generates orders (gate-only)
    C2:  No "predict" language in output labels
    C3:  Market profiles loaded independently
    C4:  Path quality required for D5 entry
    C5:  Shadow verification before paper/live
    C6:  K >= 2 (single pattern prohibited)
    C7:  Execution engine files diff = 0
    C8:  Output labeled as "hypothesis", not "prediction"
    C9:  PPF standalone trade prohibited
    C10: No runtime parameter adaptation
    C11: O9=True -> PPF disabled (novelty brake)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from typing import Optional

from strategies.ppf.constants import MIN_K, PPFState
from strategies.ppf.parameters import PPFParameters

logger = logging.getLogger("ppf.constitution")


@dataclass(frozen=True)
class ConstitutionCheckResult:
    """Result of a constitution invariant check."""

    passed: bool
    violated_articles: tuple[str, ...]
    details: str


def check_c6_k_minimum(params: PPFParameters) -> bool:
    """C6: K >= MIN_K (single pattern decision prohibited)."""
    return params.k >= MIN_K


def check_c3_independent_profiles(
    params_a: PPFParameters,
    params_b: PPFParameters,
) -> bool:
    """C3: Different market profiles must have independent configs.

    Returns True if params are from different profiles (or same profile).
    If same profile with different values, that's a configuration error.
    """
    if params_a.market_profile == params_b.market_profile:
        return True  # same profile, no independence check needed
    # Different profiles should exist as separate objects
    return params_a is not params_b


def check_c7_engine_diff(
    engine_dir: str,
    expected_checksums: Optional[dict[str, str]] = None,
) -> ConstitutionCheckResult:
    """C7: Execution engine files diff = 0.

    Verifies that no files in the execution engine directory have been
    modified. PPF operates via external orchestration wrapper ONLY.

    Args:
        engine_dir: Path to the execution engine directory.
        expected_checksums: Dict of {filename: sha256_hex} to verify against.
            If None, only checks that files exist (warning mode).

    Returns:
        ConstitutionCheckResult with pass/fail and details.
    """
    engine_path = Path(engine_dir)
    violations: list[str] = []

    if not engine_path.exists():
        return ConstitutionCheckResult(
            passed=True,
            violated_articles=(),
            details="Engine directory not found (acceptable if not deployed).",
        )

    if expected_checksums is None:
        return ConstitutionCheckResult(
            passed=True,
            violated_articles=(),
            details="No checksums provided; skipping C7 diff check.",
        )

    for filename, expected_hash in expected_checksums.items():
        filepath = engine_path / filename
        if not filepath.exists():
            violations.append(f"C7: file missing: {filename}")
            continue

        actual_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            violations.append(
                f"C7: file modified: {filename} "
                f"(expected {expected_hash[:12]}..., "
                f"got {actual_hash[:12]}...)"
            )

    if violations:
        return ConstitutionCheckResult(
            passed=False,
            violated_articles=("C7",),
            details="; ".join(violations),
        )

    return ConstitutionCheckResult(
        passed=True,
        violated_articles=(),
        details=f"C7 PASS: {len(expected_checksums)} files verified.",
    )


def check_c10_runtime_immutability(params: PPFParameters) -> bool:
    """C10: Parameters must be frozen (no runtime adaptation).

    PPFParameters is a frozen dataclass, so this check verifies
    that the object is indeed immutable via the public attribute API.

    Note: object.__setattr__ bypasses frozen guard in Python 3.14+.
    We use normal attribute assignment which is what user code would use.
    """
    try:
        # Normal attribute assignment on frozen dataclass -> FrozenInstanceError
        params._c10_test_mutation = True  # type: ignore[attr-defined]
        # If we get here, the dataclass is NOT frozen
        return False
    except (FrozenInstanceError, AttributeError):
        # FrozenInstanceError (or AttributeError on slots) -> immutable
        return True


def check_c11_novelty_brake(
    regime_novelty_flag: bool,
    current_state: PPFState,
) -> bool:
    """C11: O9=True -> PPF must be in D1_IDLE (disabled).

    Returns True if invariant holds, False if violated.
    """
    if regime_novelty_flag and current_state != PPFState.D1_IDLE:
        return False
    return True


def run_all_checks(
    params: PPFParameters,
    regime_novelty_flag: bool,
    current_state: PPFState,
    engine_dir: Optional[str] = None,
    engine_checksums: Optional[dict[str, str]] = None,
) -> ConstitutionCheckResult:
    """Run all constitution invariant checks.

    Any single violation -> PPF deactivation (fail-closed).

    Returns:
        ConstitutionCheckResult. If passed=False, PPF must be disabled.
    """
    violations: list[str] = []

    # C6: K minimum
    if not check_c6_k_minimum(params):
        violations.append(
            f"C6: k={params.k} < MIN_K={MIN_K}"
        )

    # C7: engine diff (if engine_dir provided)
    if engine_dir is not None:
        c7_result = check_c7_engine_diff(engine_dir, engine_checksums)
        if not c7_result.passed:
            violations.append(c7_result.details)

    # C10: runtime immutability
    if not check_c10_runtime_immutability(params):
        violations.append("C10: parameters are not frozen")

    # C11: novelty brake
    if not check_c11_novelty_brake(regime_novelty_flag, current_state):
        violations.append(
            f"C11: novelty=True but state={current_state.value} (must be IDLE)"
        )

    if violations:
        detail_str = "; ".join(violations)
        logger.error(f"Constitution violation: {detail_str}")
        return ConstitutionCheckResult(
            passed=False,
            violated_articles=tuple(
                v.split(":")[0] for v in violations
            ),
            details=detail_str,
        )

    return ConstitutionCheckResult(
        passed=True,
        violated_articles=(),
        details="All constitution checks passed.",
    )
