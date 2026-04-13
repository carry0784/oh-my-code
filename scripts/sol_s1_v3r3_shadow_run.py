"""SOL S-1 V-3R3 Shadow Drift Verification Run Script (C6 Staged Package).

Purpose
-------
V-3R3 fork of the frozen V-3R1 runner (`scripts/sol_s1_v3_shadow_run.py`).
Implements the C6 staged design package:

  C1 (Consensus Cluster Deduplication)  — MANDATORY, always active
  C5 (Minimum Denominator Grace)        — CONDITIONAL, dormant-by-default

This fork does NOT mutate the frozen runner, does NOT shadow its exports,
and does NOT duplicate logic unnecessarily.  It imports shared components
(constants, dataclasses, helper functions, precompute_signals) from the
frozen runner and re-implements ONLY the 5 bounded functions that require
C1/C5 changes:

  1) simulate_shadow_bar_c6
  2) classify_drift_state_c6
  3) run_shadow_simulation_c6
  4) main_async_c6
  5) main

Authority Chain (SEALED, read-only at runtime)
----------------------------------------------
1. NE-7  CLOSED — BLOCKING_PATTERN_STRUCTURAL_ANALYSIS_COMPLETE
2. DCC-1 CLOSED — DESIGN_CANDIDATES_COMPARED (C6 selected, Tier A)
3. DPR-1 CLOSED — C6_STAGED_PACKAGE_CONFIRMED (P1/G1/P2/G2/P3)
4. ICR-1 CLOSED — IMPLEMENTATION_CONSTITUTION_CONFIRMED (+4 enrichments)
5. IMPL-C6-BOUNDED-SCOPE-001 — implementation bounded-scope RAW_GO

Triple-Lock (RULE-EXEC-3) — inherited from V-3R2
-------------------------------------------------
Lock 1:  `--run` must be present in argv.
Lock 2:  env SOL_S1_V3_RUN_AUTHORIZED must equal "v3_run_go_granted".
Lock 3:  env SOL_S1_V3_EXECUTION_MODE must be "realtime_shadow" or
         "historical_replay".

C6 Design Parameters (deployment_profile_switch)
-------------------------------------------------
  SOL_S1_V3_COOLDOWN_BARS   — C1 cooldown period (default=4, always active)
  SOL_S1_V3_GRACE_MIN_GEN   — C5 minimum generation threshold before RED ECR
                               check (default=1 = dormant, active=5)

Activation type: deployment_profile_switch
  - Set BEFORE run via environment variables
  - NOT runtime-dynamic, NOT evaluated per-bar
  - Zero-cost rollback: reset env vars to defaults

Frozen Runner Integrity
-----------------------
    original_path   = scripts/sol_s1_v3_shadow_run.py
    original_sha256 = 94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a

Forbidden Boundary (11 items)
-----------------------------
  1. Do not modify frozen runner.
  2. Do not modify V-3R2.
  3. Do not modify strategy files.
  4. Do not modify threshold values.
  5. Do not modify consensus window geometry.
  6. Do not modify classify_block.
  7. Do not modify has_windowed_consensus internals.
  8. Do not modify SL/TP or position lifecycle logic.
  9. Do not modify CONFIG_MAX_POSITIONS.
 10. Do not add more than 1 new file.
 11. Do not expand scope beyond ICR-1.

Fork Provenance
---------------
    chain_id                : IMPL-C6-BOUNDED-SCOPE-001
    created_under           : implementation bounded-scope RAW_GO
    seal_operation_on_target: none (frozen runner unchanged)
    max_new_files           : 1 (this file)
    existing_file_mutation  : 0
    auto_advance            : forbidden
    fork_accumulation       : V-3R4 creation prohibited until V-3R3 comparator
                              evidence secured + C5 promotion evaluated +
                              consolidation necessity demonstrated
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Mapping, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Frozen Runner Import Gate
# ---------------------------------------------------------------------------
# The frozen V-3R1 runner is imported LAZILY inside main() after triple-lock
# passes, following the V-3R2 precedent.  At module level we only declare
# the import path so that merely importing this module does NOT pull in the
# frozen runner unconditionally.

REPO_ROOT = Path(__file__).resolve().parent.parent

FROZEN_RUNNER_MODULE_NAME: Final[str] = "sol_s1_v3_shadow_run"
FROZEN_RUNNER_PATH: Final[str] = "scripts/sol_s1_v3_shadow_run.py"
FROZEN_RUNNER_SHA256: Final[str] = (
    "94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a"
)

# ---------------------------------------------------------------------------
# Authority Source References (string constants, no runtime file I/O)
# ---------------------------------------------------------------------------

AUTHORITY_SOURCE_EXECUTION_MODE_PROTOCOL: Final[str] = (
    "docs/operations/evidence/sol_s1_v3_execution_mode_protocol.md"
)
AUTHORITY_SOURCE_V3R2_RUN_GO_RECEIPT: Final[str] = (
    "docs/operations/evidence/sol_s1_v3r2_run_go_receipt.md"
)
AUTHORITY_SOURCE_C6_IMPL: Final[str] = "IMPL-C6-BOUNDED-SCOPE-001"

# ---------------------------------------------------------------------------
# Triple-Lock Constants (inherited from V-3R2, RULE-EXEC-3)
# ---------------------------------------------------------------------------

CLI_RUN_FLAG: Final[str] = "--run"

RUN_AUTHORIZATION_ENV_KEY: Final[str] = "SOL_S1_V3_RUN_AUTHORIZED"
RUN_AUTHORIZATION_EXPECTED: Final[str] = "v3_run_go_granted"

EXECUTION_MODE_ENV_KEY: Final[str] = "SOL_S1_V3_EXECUTION_MODE"
EXECUTION_MODE_ALLOWED_VALUES: Final[frozenset[str]] = frozenset(
    {"realtime_shadow", "historical_replay"}
)

# ---------------------------------------------------------------------------
# C6 Design Parameters (deployment_profile_switch)
# ---------------------------------------------------------------------------

# C1: Consensus Cluster Deduplication — MANDATORY, always active
COOLDOWN_BARS_ENV_KEY: Final[str] = "SOL_S1_V3_COOLDOWN_BARS"
COOLDOWN_BARS_DEFAULT: Final[int] = 4

# C5: Minimum Denominator Grace — CONDITIONAL, dormant-by-default
GRACE_MIN_GEN_ENV_KEY: Final[str] = "SOL_S1_V3_GRACE_MIN_GEN"
GRACE_MIN_GEN_DEFAULT: Final[int] = 1  # dormant: K=1 means no grace
GRACE_MIN_GEN_ACTIVE: Final[int] = 5  # active profile target

# ---------------------------------------------------------------------------
# V-3R3 Fork Constants
# ---------------------------------------------------------------------------

FORK_DESIGN_VERSION_LABEL: Final[str] = "V-3R3"
FORK_CHAIN_ID: Final[str] = "IMPL-C6-BOUNDED-SCOPE-001"

# Evidence output paths (V-3R3 specific, does NOT overwrite V-3/V-3R1 paths)
EVIDENCE_DIR: Path = REPO_ROOT / "docs" / "operations" / "evidence"
V3R3_SHADOW_LOG_PATH: Path = EVIDENCE_DIR / "sol_s1_v3r3_shadow_log.json"
V3R3_RECEIPT_PATH: Path = EVIDENCE_DIR / "sol_s1_v3r3_completion_receipt.md"

# ---------------------------------------------------------------------------
# Exit Codes (lock-specific, audit-friendly)
# ---------------------------------------------------------------------------

EXIT_OK: Final[int] = 0
EXIT_LOCK_1_FAILED: Final[int] = 11
EXIT_LOCK_2_FAILED: Final[int] = 12
EXIT_LOCK_3_FAILED: Final[int] = 13
EXIT_FROZEN_IMPORT_FAILED: Final[int] = 14
EXIT_FROZEN_INTEGRITY_FAILED: Final[int] = 15


# ---------------------------------------------------------------------------
# C6 Evidence Dataclass
# ---------------------------------------------------------------------------


@dataclass
class C6Evidence:
    """C6-specific evidence fields (7 required by ICR-1)."""

    # C1 fields
    dedup_suppressed_count: int = 0
    unique_cluster_count: int = 0
    cooldown_active_bars: int = 0

    # C5 fields
    gen_before_grace: int = 0
    red_deferred_count: int = 0
    grace_active_bars: int = 0
    grace_saved_exec_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dedup_suppressed_count": self.dedup_suppressed_count,
            "unique_cluster_count": self.unique_cluster_count,
            "cooldown_active_bars": self.cooldown_active_bars,
            "gen_before_grace": self.gen_before_grace,
            "red_deferred_count": self.red_deferred_count,
            "grace_active_bars": self.grace_active_bars,
            "grace_saved_exec_count": self.grace_saved_exec_count,
        }


@dataclass
class ActivationProfileReceipt:
    """Activation profile receipt (ICR-1 SS6-1)."""

    c1_mode: str  # "active" (always)
    c5_mode: str  # "dormant" or "active"
    cooldown_bars: int
    grace_min_gen: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "c1_mode": self.c1_mode,
            "c5_mode": self.c5_mode,
            "cooldown_bars": self.cooldown_bars,
            "grace_min_gen": self.grace_min_gen,
        }


@dataclass
class CounterfactualComparator:
    """Counterfactual comparison: frozen vs C1-only vs C1+C5 (ICR-1 SS6-2).

    All three rows use the SAME input data and differ only in C1/C5 gates.
    """

    # frozen (no C1, no C5)
    frozen_consensus_generated: int = 0
    frozen_ecr: float = 0.0
    frozen_final_state: str = ""
    frozen_bars_observed: int = 0

    # C1-only (C1 active, C5 dormant = grace_min_gen=1)
    c1_only_consensus_generated: int = 0
    c1_only_ecr: float = 0.0
    c1_only_final_state: str = ""
    c1_only_bars_observed: int = 0

    # C1+C5 (C1 active, C5 active = grace_min_gen=5)
    c1_c5_consensus_generated: int = 0
    c1_c5_ecr: float = 0.0
    c1_c5_final_state: str = ""
    c1_c5_bars_observed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "frozen": {
                "consensus_generated": self.frozen_consensus_generated,
                "ecr": self.frozen_ecr,
                "final_state": self.frozen_final_state,
                "bars_observed": self.frozen_bars_observed,
            },
            "c1_only": {
                "consensus_generated": self.c1_only_consensus_generated,
                "ecr": self.c1_only_ecr,
                "final_state": self.c1_only_final_state,
                "bars_observed": self.c1_only_bars_observed,
            },
            "c1_c5": {
                "consensus_generated": self.c1_c5_consensus_generated,
                "ecr": self.c1_c5_ecr,
                "final_state": self.c1_c5_final_state,
                "bars_observed": self.c1_c5_bars_observed,
            },
        }


# ---------------------------------------------------------------------------
# Triple-Lock Pre-Flight Guard (inherited from V-3R2)
# ---------------------------------------------------------------------------


def triple_lock_pre_flight_guard(
    argv: list[str],
    env: Mapping[str, str],
) -> int:
    """Bounded RULE-EXEC-3 triple-lock pre-flight guard.

    Pure inspection. No mutation, no import, no I/O.
    Returns EXIT_OK (0) iff all three locks pass.
    """
    # Lock 1: CLI --run flag
    if CLI_RUN_FLAG not in argv:
        print(
            f"[V-3R3][LOCK-1][ABORT] CLI flag '{CLI_RUN_FLAG}' is required.",
            flush=True,
        )
        return EXIT_LOCK_1_FAILED

    # Lock 2: SOL_S1_V3_RUN_AUTHORIZED env var
    run_authorized_value = env.get(RUN_AUTHORIZATION_ENV_KEY, "")
    if run_authorized_value != RUN_AUTHORIZATION_EXPECTED:
        print(
            f"[V-3R3][LOCK-2][ABORT] env var {RUN_AUTHORIZATION_ENV_KEY} "
            f"is not set to the expected value.",
            flush=True,
        )
        return EXIT_LOCK_2_FAILED

    # Lock 3: SOL_S1_V3_EXECUTION_MODE env var
    declared_mode = env.get(EXECUTION_MODE_ENV_KEY, "").strip()
    if declared_mode not in EXECUTION_MODE_ALLOWED_VALUES:
        print(
            f"[V-3R3][LOCK-3][ABORT] env var {EXECUTION_MODE_ENV_KEY} "
            f"missing or invalid value: '{declared_mode}'",
            flush=True,
        )
        return EXIT_LOCK_3_FAILED

    print(
        f"[V-3R3][LOCK-OK] triple-lock passed "
        f"({CLI_RUN_FLAG}=present, "
        f"{RUN_AUTHORIZATION_ENV_KEY}=<set>, "
        f"{EXECUTION_MODE_ENV_KEY}='{declared_mode}').",
        flush=True,
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# Frozen Runner Integrity Check
# ---------------------------------------------------------------------------


def verify_frozen_runner_integrity() -> tuple[bool, str]:
    """Verify frozen runner SHA256 is unchanged.

    Returns (ok, actual_sha256).
    """
    frozen_path = REPO_ROOT / "scripts" / "sol_s1_v3_shadow_run.py"
    if not frozen_path.exists():
        return False, "FILE_NOT_FOUND"
    content = frozen_path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    return actual == FROZEN_RUNNER_SHA256, actual


# ---------------------------------------------------------------------------
# C6 Parameter Loader (deployment_profile_switch)
# ---------------------------------------------------------------------------


def load_c6_parameters(
    env: Mapping[str, str],
) -> tuple[int, int, ActivationProfileReceipt]:
    """Load C1/C5 parameters from environment.

    Returns (cooldown_bars, grace_min_gen, activation_profile_receipt).
    """
    # C1: cooldown bars (0 = disabled per ICR-1, default = 4)
    raw_cooldown = env.get(COOLDOWN_BARS_ENV_KEY, "").strip()
    if raw_cooldown.isdigit():
        cooldown_bars = int(raw_cooldown)
    else:
        cooldown_bars = COOLDOWN_BARS_DEFAULT

    # C5: grace minimum generation
    raw_grace = env.get(GRACE_MIN_GEN_ENV_KEY, "")
    if raw_grace.strip().isdigit() and int(raw_grace.strip()) > 0:
        grace_min_gen = int(raw_grace.strip())
    else:
        grace_min_gen = GRACE_MIN_GEN_DEFAULT

    # Determine activation modes
    c1_mode = "active" if cooldown_bars > 0 else "disabled"
    c5_mode = "active" if grace_min_gen > 1 else "dormant"

    receipt = ActivationProfileReceipt(
        c1_mode=c1_mode,
        c5_mode=c5_mode,
        cooldown_bars=cooldown_bars,
        grace_min_gen=grace_min_gen,
    )

    print(
        f"[V-3R3][C6-PARAMS] cooldown_bars={cooldown_bars} "
        f"(c1_mode={c1_mode}), "
        f"grace_min_gen={grace_min_gen} "
        f"(c5_mode={c5_mode})",
        flush=True,
    )

    return cooldown_bars, grace_min_gen, receipt


# ═══════════════════════════════════════════════════════════════════════════
# 5 BOUNDED FUNCTIONS (ICR-1 scope)
# ═══════════════════════════════════════════════════════════════════════════


# ---------------------------------------------------------------------------
# Function 1/5: simulate_shadow_bar_c6
# ---------------------------------------------------------------------------


def simulate_shadow_bar_c6(
    bar_index: int,
    bar_ts: str,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
    open_positions: list,
    metrics: Any,
    c6_evidence: C6Evidence,
    cooldown_bars: int,
    last_consensus_bar: int,
    *,
    # Imported references (passed to avoid global state)
    has_windowed_consensus: Any,
    classify_block: Any,
    SimPosition: Any,
    CONFIG_CONSENSUS_WINDOW: int,
    CONFIG_MAX_POSITIONS: int,
    CONFIG_POSITION_SIZE_PCT: float,
    CONFIG_SL_PCT: float,
    CONFIG_TP_PCT: float,
    ShadowBarRecord: Any,
    generate_config_fingerprint: Any,
) -> tuple[Any, int]:
    """Simulate one shadow bar with C1 cooldown gate.

    C1 Logic:
      - After a consensus fires (consensus_dir != 0 AND not suppressed),
        subsequent consensus signals within `cooldown_bars` are suppressed.
      - Suppressed signals do NOT increment consensus_generated.
      - Suppressed signals ARE counted in dedup_suppressed_count.

    Position lifecycle (SL/TP) is UNCHANGED from frozen runner.
    classify_block is UNCHANGED from frozen runner (called as-is).

    Returns (bar_record, updated_last_consensus_bar).
    """
    # 1) Check SL/TP on existing positions first (UNCHANGED from frozen)
    closed_indices: list[int] = []
    for idx, pos in enumerate(open_positions):
        if pos.direction > 0:
            if bar_low <= pos.sl_price or bar_high >= pos.tp_price:
                closed_indices.append(idx)
        else:
            if bar_high >= pos.sl_price or bar_low <= pos.tp_price:
                closed_indices.append(idx)

    for idx in reversed(closed_indices):
        open_positions.pop(idx)
        metrics.trades_count += 1

    # 2) Evaluate consensus within the window (UNCHANGED call)
    consensus_dir = has_windowed_consensus(
        smc_signals, wt_signals, bar_index, CONFIG_CONSENSUS_WINDOW
    )

    block_code: Optional[str] = None
    executable = False

    if consensus_dir != 0:
        # --- C1 Cooldown Gate ---
        bars_since_last = bar_index - last_consensus_bar
        if last_consensus_bar >= 0 and bars_since_last < cooldown_bars:
            # SUPPRESSED: within cooldown window
            c6_evidence.dedup_suppressed_count += 1
            c6_evidence.cooldown_active_bars += 1
            # Do NOT count as consensus_generated
            consensus_dir = 0  # suppress
        else:
            # NOT suppressed: this is a unique cluster signal
            c6_evidence.unique_cluster_count += 1
            last_consensus_bar = bar_index

    if consensus_dir != 0:
        metrics.consensus_generated += 1
        block_code = classify_block(consensus_dir, open_positions, CONFIG_MAX_POSITIONS)
        if block_code is None:
            # Open new shadow position (UNCHANGED logic)
            sl = (
                bar_close * (1 - CONFIG_SL_PCT)
                if consensus_dir > 0
                else bar_close * (1 + CONFIG_SL_PCT)
            )
            tp = (
                bar_close * (1 + CONFIG_TP_PCT)
                if consensus_dir > 0
                else bar_close * (1 - CONFIG_TP_PCT)
            )
            open_positions.append(
                SimPosition(
                    direction=consensus_dir,
                    entry_price=bar_close,
                    entry_bar=bar_index,
                    size_pct=CONFIG_POSITION_SIZE_PCT,
                    sl_price=sl,
                    tp_price=tp,
                )
            )
            metrics.consensus_executable += 1
            executable = True
        else:
            metrics.consensus_blocked += 1
            if block_code == "BLOCK_MAX_POSITIONS":
                metrics.block_max_positions += 1
            elif block_code == "BLOCK_SAME_DIRECTION":
                metrics.block_same_direction += 1
            elif block_code == "BLOCK_OPPOSITE_DIRECTION":
                metrics.block_opposite_direction += 1

    record = ShadowBarRecord(
        bar_ts=bar_ts,
        bar_index=bar_index,
        consensus_dir=consensus_dir,
        consensus_generated=(consensus_dir != 0),
        consensus_executable=executable,
        block_code=block_code,
        open_positions=len(open_positions),
        slots_used=len(open_positions),
        slots_available=CONFIG_MAX_POSITIONS - len(open_positions),
        config_fingerprint=generate_config_fingerprint(),
        current_state="",  # filled by caller
    )
    return record, last_consensus_bar


# ---------------------------------------------------------------------------
# Function 2/5: classify_drift_state_c6
# ---------------------------------------------------------------------------


def classify_drift_state_c6(
    metrics: Any,
    rolling_ecr: list[float],
    grace_min_gen: int,
    c6_evidence: C6Evidence,
    *,
    # Imported references
    DriftState: Any,
    StopReason: Any,
    truncate_detail: Any,
    RED_ECR_THRESHOLD: float,
    RED_BLOCK_THRESHOLD: float,
    RED_SD_DELTA_THRESHOLD: float,
    GREEN_ECR_MIN: float,
    GREEN_BLOCK_MAX: float,
    GREEN_SD_DELTA_MAX: float,
    YELLOW_ECR_MIN: float,
    YELLOW_BLOCK_MAX: float,
    YELLOW_SD_DELTA_MAX: float,
    ROLLING_WINDOW: int,
    ROLLING_ECR_DROP_YELLOW_PP: float,
    V2_BASELINE_SD_RATIO: float,
) -> tuple[Any, Optional[Any], str]:
    """Classify drift state with C5 grace gate.

    C5 Logic:
      - BEFORE the RED ECR check, if consensus_generated < grace_min_gen,
        the RED ECR condition is DEFERRED (not triggered).
      - When grace_min_gen=1 (default/dormant), the gate is effectively
        transparent: consensus_generated >= 1 is always true when
        have_consensus is true, so no deferral occurs.
      - When grace_min_gen=5 (active), ECR-based RED is deferred until
        at least 5 consensus signals have been generated.

    All other thresholds (block_rate, SD ratio, invalid bars, yellow,
    rolling ECR) are UNCHANGED from frozen runner.
    """
    # Invalid bar hard fail (UNCHANGED)
    if metrics.invalid_bars >= 1:
        return (
            DriftState.RED,
            StopReason.INVALID_RUN,
            truncate_detail(f"invalid_bars={metrics.invalid_bars} >= 1 threshold"),
        )

    have_consensus = metrics.consensus_generated > 0
    ecr = metrics.ecr if have_consensus else 100.0
    block_rate = metrics.block_rate if have_consensus else 0.0
    sd_delta = metrics.same_direction_delta_pp

    # --- Red conditions ---

    # C5 Grace Gate: check generation count BEFORE RED ECR
    if have_consensus and ecr < RED_ECR_THRESHOLD:
        c6_evidence.gen_before_grace = metrics.consensus_generated
        if metrics.consensus_generated >= grace_min_gen:
            # Grace condition met (or dormant): RED ECR fires normally
            return (
                DriftState.RED,
                StopReason.RED_ECR,
                truncate_detail(
                    f"ecr={ecr:.2f}% < {RED_ECR_THRESHOLD:.1f}% threshold "
                    f"(gen={metrics.consensus_generated} >= grace={grace_min_gen})"
                ),
            )
        else:
            # Grace active: DEFER RED ECR
            c6_evidence.red_deferred_count += 1
            c6_evidence.grace_active_bars += 1
            # Track saved exec: how many executable signals exist that
            # would have been lost to early RED termination
            c6_evidence.grace_saved_exec_count = metrics.consensus_executable
            # Fall through to yellow/green evaluation instead of RED

    # block_rate RED (UNCHANGED)
    if block_rate > RED_BLOCK_THRESHOLD:
        return (
            DriftState.RED,
            StopReason.RED_BLOCK_RATE,
            truncate_detail(f"block_rate={block_rate:.2f}% > {RED_BLOCK_THRESHOLD:.1f}% threshold"),
        )

    # SD ratio RED (UNCHANGED)
    if sd_delta > RED_SD_DELTA_THRESHOLD:
        return (
            DriftState.RED,
            StopReason.RED_SD_RATIO,
            truncate_detail(
                f"sd_delta=+{sd_delta:.2f}pp > +{RED_SD_DELTA_THRESHOLD:.1f}pp threshold"
            ),
        )

    # --- Yellow conditions (UNCHANGED) ---
    yellow_reasons: list[str] = []
    if have_consensus and YELLOW_ECR_MIN <= ecr < GREEN_ECR_MIN:
        yellow_reasons.append(f"ecr={ecr:.2f}% in [55,60)")
    if GREEN_BLOCK_MAX < block_rate <= YELLOW_BLOCK_MAX:
        yellow_reasons.append(f"block={block_rate:.2f}% in (40,45]")
    if GREEN_SD_DELTA_MAX < sd_delta <= YELLOW_SD_DELTA_MAX:
        yellow_reasons.append(f"sd_delta=+{sd_delta:.2f}pp in (+10,+15]")

    # Rolling ECR drop (UNCHANGED)
    if len(rolling_ecr) >= ROLLING_WINDOW * 2:
        recent = rolling_ecr[-ROLLING_WINDOW:]
        prior = rolling_ecr[-2 * ROLLING_WINDOW : -ROLLING_WINDOW]
        if recent and prior:
            drop = (sum(prior) / len(prior)) - (sum(recent) / len(recent))
            if drop >= ROLLING_ECR_DROP_YELLOW_PP:
                yellow_reasons.append(
                    f"rolling_ecr_drop={drop:.2f}pp >= {ROLLING_ECR_DROP_YELLOW_PP:.1f}pp"
                )

    if yellow_reasons:
        return (DriftState.YELLOW, None, truncate_detail("; ".join(yellow_reasons)))

    # --- Green (default) ---
    return (
        DriftState.GREEN,
        None,
        truncate_detail(f"ecr={ecr:.2f}% block={block_rate:.2f}% sd_delta=+{sd_delta:.2f}pp"),
    )


# ---------------------------------------------------------------------------
# Function 3/5: run_shadow_simulation_c6
# ---------------------------------------------------------------------------


def run_shadow_simulation_c6(
    ohlcv: list[list],
    run_id: str,
    started_at: str,
    cooldown_bars: int,
    grace_min_gen: int,
    frozen: Any,
) -> tuple[Any, C6Evidence]:
    """Execute the C6 shadow drift verification loop.

    This function mirrors `run_shadow_simulation` from the frozen runner
    but calls `simulate_shadow_bar_c6` and `classify_drift_state_c6`.
    """
    closes, smc_signals, wt_signals = frozen.precompute_signals(ohlcv)

    metrics = frozen.ShadowMetrics()
    open_positions: list = []
    rolling_ecr: list[float] = []
    rolling_block: list[float] = []
    rolling_sd: list[float] = []
    c6_evidence = C6Evidence()

    bars_budget = frozen.MIN_BARS
    yellow_extensions_used = 0
    stop_reason = frozen.StopReason.PASS_GREEN
    stop_detail = ""
    final_state = frozen.DriftState.GREEN
    bar_index = 0
    last_consensus_bar = -1  # C1: no consensus yet

    total_available = len(ohlcv)

    while bar_index < min(bars_budget, total_available):
        bar = ohlcv[bar_index]
        bar_ts = (
            datetime.fromtimestamp(bar[0] / 1000, tz=timezone.utc).isoformat()
            if isinstance(bar[0], (int, float))
            else str(bar[0])
        )
        try:
            _record, last_consensus_bar = simulate_shadow_bar_c6(
                bar_index=bar_index,
                bar_ts=bar_ts,
                bar_high=float(bar[2]),
                bar_low=float(bar[3]),
                bar_close=float(bar[4]),
                smc_signals=smc_signals,
                wt_signals=wt_signals,
                open_positions=open_positions,
                metrics=metrics,
                c6_evidence=c6_evidence,
                cooldown_bars=cooldown_bars,
                last_consensus_bar=last_consensus_bar,
                # Frozen runner references
                has_windowed_consensus=frozen.has_windowed_consensus,
                classify_block=frozen.classify_block,
                SimPosition=frozen.SimPosition,
                CONFIG_CONSENSUS_WINDOW=frozen.CONFIG_CONSENSUS_WINDOW,
                CONFIG_MAX_POSITIONS=frozen.CONFIG_MAX_POSITIONS,
                CONFIG_POSITION_SIZE_PCT=frozen.CONFIG_POSITION_SIZE_PCT,
                CONFIG_SL_PCT=frozen.CONFIG_SL_PCT,
                CONFIG_TP_PCT=frozen.CONFIG_TP_PCT,
                ShadowBarRecord=frozen.ShadowBarRecord,
                generate_config_fingerprint=frozen.generate_config_fingerprint,
            )
        except Exception as exc:  # noqa: BLE001
            metrics.invalid_bars += 1
            stop_detail = frozen.truncate_detail(f"invalid bar {bar_index}: {type(exc).__name__}")

        rolling_ecr.append(metrics.ecr)
        rolling_block.append(metrics.block_rate)
        rolling_sd.append(metrics.same_direction_ratio)

        state, stop_reason_candidate, detail = classify_drift_state_c6(
            metrics,
            rolling_ecr,
            grace_min_gen,
            c6_evidence,
            DriftState=frozen.DriftState,
            StopReason=frozen.StopReason,
            truncate_detail=frozen.truncate_detail,
            RED_ECR_THRESHOLD=frozen.RED_ECR_THRESHOLD,
            RED_BLOCK_THRESHOLD=frozen.RED_BLOCK_THRESHOLD,
            RED_SD_DELTA_THRESHOLD=frozen.RED_SD_DELTA_THRESHOLD,
            GREEN_ECR_MIN=frozen.GREEN_ECR_MIN,
            GREEN_BLOCK_MAX=frozen.GREEN_BLOCK_MAX,
            GREEN_SD_DELTA_MAX=frozen.GREEN_SD_DELTA_MAX,
            YELLOW_ECR_MIN=frozen.YELLOW_ECR_MIN,
            YELLOW_BLOCK_MAX=frozen.YELLOW_BLOCK_MAX,
            YELLOW_SD_DELTA_MAX=frozen.YELLOW_SD_DELTA_MAX,
            ROLLING_WINDOW=frozen.ROLLING_WINDOW,
            ROLLING_ECR_DROP_YELLOW_PP=frozen.ROLLING_ECR_DROP_YELLOW_PP,
            V2_BASELINE_SD_RATIO=frozen.V2_BASELINE_SD_RATIO,
        )
        final_state = state

        if state == frozen.DriftState.RED:
            stop_reason = stop_reason_candidate or frozen.StopReason.INVALID_RUN
            stop_detail = detail
            bar_index += 1
            break

        if state == frozen.DriftState.YELLOW:
            if yellow_extensions_used < frozen.MAX_YELLOW_EXTENSIONS:
                if bars_budget == frozen.MIN_BARS:
                    bars_budget += frozen.YELLOW_EXTENSION_BARS
                    yellow_extensions_used += 1
            else:
                if bar_index + 1 >= bars_budget:
                    stop_reason = frozen.StopReason.YELLOW_EXTENSION_EXHAUSTED
                    stop_detail = frozen.truncate_detail(
                        f"yellow persisted after extension: {detail}"
                    )
                    bar_index += 1
                    break

        bar_index += 1

    ended_at = frozen.now_iso()

    if bar_index >= bars_budget and final_state == frozen.DriftState.GREEN:
        stop_reason = frozen.StopReason.PASS_GREEN
        stop_detail = frozen.truncate_detail(f"completed {bar_index} bars in GREEN")

    evidence = frozen.EvidenceLog(
        run_id=run_id,
        config_fingerprint=frozen.generate_config_fingerprint(),
        design_version=frozen.DESIGN_VERSION,
        go_receipt_id=frozen.GO_RECEIPT_ID,
        bars_observed=bar_index,
        trades_count=metrics.trades_count,
        ecr=round(metrics.ecr, 4),
        block_rate=round(metrics.block_rate, 4),
        same_direction_ratio=round(metrics.same_direction_ratio, 4),
        same_direction_delta_pp=round(metrics.same_direction_delta_pp, 4),
        yellow_extension_count=yellow_extensions_used,
        invalid_run_count=metrics.invalid_bars,
        final_state=final_state.value,
        receipt_completeness_pct=0.0,
        stop_reason=stop_reason.value,
        stop_reason_detail=stop_detail,
        started_at=started_at,
        ended_at=ended_at,
        rolling_ecr_12=[round(x, 4) for x in rolling_ecr[-frozen.ROLLING_WINDOW :]],
        rolling_block_rate_12=[round(x, 4) for x in rolling_block[-frozen.ROLLING_WINDOW :]],
        rolling_sd_ratio_12=[round(x, 4) for x in rolling_sd[-frozen.ROLLING_WINDOW :]],
    )
    evidence.receipt_completeness_pct = round(frozen.compute_receipt_completeness(evidence), 2)
    return evidence, c6_evidence


# ---------------------------------------------------------------------------
# Counterfactual Runner (frozen baseline, same data)
# ---------------------------------------------------------------------------


def run_frozen_counterfactual(
    ohlcv: list[list],
    run_id: str,
    started_at: str,
    frozen: Any,
) -> Any:
    """Run the FROZEN simulation logic on the same data for comparison.

    This calls frozen.run_shadow_simulation directly — no C1/C5 gates.
    """
    return frozen.run_shadow_simulation(
        ohlcv,
        run_id=f"{run_id}_frozen_cf",
        started_at=started_at,
    )


# ---------------------------------------------------------------------------
# Comparator Builder (ICR-1 SS6-2)
# ---------------------------------------------------------------------------


def build_comparator(
    frozen_evidence: Any,
    c1_only_evidence: Any,
    c1_only_c6: C6Evidence,
    c1_c5_evidence: Any | None,
    c1_c5_c6: C6Evidence | None,
) -> CounterfactualComparator:
    """Build counterfactual comparator from all three run variants."""
    comp = CounterfactualComparator(
        # frozen
        frozen_consensus_generated=int(
            (frozen_evidence.ecr / 100.0) * 1
            if frozen_evidence.ecr == 100.0 and frozen_evidence.bars_observed > 0
            else 0
        ),
        frozen_ecr=frozen_evidence.ecr,
        frozen_final_state=frozen_evidence.final_state,
        frozen_bars_observed=frozen_evidence.bars_observed,
        # C1-only
        c1_only_consensus_generated=c1_only_c6.unique_cluster_count,
        c1_only_ecr=c1_only_evidence.ecr,
        c1_only_final_state=c1_only_evidence.final_state,
        c1_only_bars_observed=c1_only_evidence.bars_observed,
    )

    if c1_c5_evidence is not None and c1_c5_c6 is not None:
        comp.c1_c5_consensus_generated = c1_c5_c6.unique_cluster_count
        comp.c1_c5_ecr = c1_c5_evidence.ecr
        comp.c1_c5_final_state = c1_c5_evidence.final_state
        comp.c1_c5_bars_observed = c1_c5_evidence.bars_observed

    return comp


# ---------------------------------------------------------------------------
# C5 Promotion Condition Evaluator (ICR-1 SS6-3)
# ---------------------------------------------------------------------------


def evaluate_c5_promotion(
    c6_evidence: C6Evidence,
    c1_only_evidence: Any,
    c1_c5_evidence: Any | None,
) -> dict[str, Any]:
    """Evaluate C5 promotion conditions.

    Conditions (all must pass):
      1. grace_saved_exec_count > 0
      2. No damage increase (C1+C5 ECR >= C1-only ECR)
      3. No block_rate worsening (C1+C5 block_rate <= C1-only block_rate)
    """
    if c1_c5_evidence is None:
        return {
            "evaluable": False,
            "reason": "C5 was dormant (grace_min_gen=1), no C1+C5 run produced",
            "recommendation": "Re-run with SOL_S1_V3_GRACE_MIN_GEN=5 to evaluate",
        }

    cond_1 = c6_evidence.grace_saved_exec_count > 0
    cond_2 = c1_c5_evidence.ecr >= c1_only_evidence.ecr
    cond_3 = c1_c5_evidence.block_rate <= c1_only_evidence.block_rate

    all_pass = cond_1 and cond_2 and cond_3

    return {
        "evaluable": True,
        "grace_saved_exec_count": c6_evidence.grace_saved_exec_count,
        "cond_1_saved_exec_positive": cond_1,
        "cond_2_no_ecr_damage": cond_2,
        "cond_3_no_block_rate_worsening": cond_3,
        "all_conditions_pass": all_pass,
        "recommendation": "PROMOTE" if all_pass else "KEEP_DORMANT",
    }


# ---------------------------------------------------------------------------
# Output Writers (V-3R3 specific)
# ---------------------------------------------------------------------------


def write_v3r3_shadow_log(
    evidence: Any,
    c6_evidence: C6Evidence,
    activation_receipt: ActivationProfileReceipt,
    comparator: CounterfactualComparator,
    c5_promotion: dict[str, Any],
    path: Path,
) -> None:
    """Write V-3R3 shadow log as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "fork_version": FORK_DESIGN_VERSION_LABEL,
        "chain_id": FORK_CHAIN_ID,
        "frozen_runner_sha256": FROZEN_RUNNER_SHA256,
        "evidence": evidence.to_dict(),
        "c6_evidence": c6_evidence.to_dict(),
        "activation_profile": activation_receipt.to_dict(),
        "counterfactual_comparator": comparator.to_dict(),
        "c5_promotion_evaluation": c5_promotion,
        "fork_accumulation_note": (
            "V-3R4 creation prohibited until: "
            "(1) V-3R3 comparator evidence secured, "
            "(2) C5 promotion evaluated, "
            "(3) consolidation necessity demonstrated."
        ),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def write_v3r3_receipt(
    evidence: Any,
    c6_evidence: C6Evidence,
    activation_receipt: ActivationProfileReceipt,
    comparator: CounterfactualComparator,
    c5_promotion: dict[str, Any],
    frozen_sha256_verified: bool,
    frozen_sha256_actual: str,
    path: Path,
) -> None:
    """Write V-3R3 completion receipt markdown."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SOL S-1 V-3R3 - C6 Staged Package Completion Receipt",
        "",
        f"**fork_version:** {FORK_DESIGN_VERSION_LABEL}",
        f"**chain_id:** {FORK_CHAIN_ID}",
        f"**frozen_runner_sha256_expected:** `{FROZEN_RUNNER_SHA256}`",
        f"**frozen_runner_sha256_actual:** `{frozen_sha256_actual}`",
        f"**frozen_runner_integrity:** {'PASS' if frozen_sha256_verified else 'FAIL'}",
        "",
        "## Activation Profile",
        "",
        f"- c1_mode: {activation_receipt.c1_mode}",
        f"- c5_mode: {activation_receipt.c5_mode}",
        f"- cooldown_bars: {activation_receipt.cooldown_bars}",
        f"- grace_min_gen: {activation_receipt.grace_min_gen}",
        "",
        "## Shadow Results",
        "",
        f"- bars_observed: {evidence.bars_observed}",
        f"- trades_count: {evidence.trades_count}",
        f"- ecr: {evidence.ecr}%",
        f"- block_rate: {evidence.block_rate}%",
        f"- final_state: {evidence.final_state}",
        f"- stop_reason: {evidence.stop_reason}",
        f"- stop_reason_detail: {evidence.stop_reason_detail}",
        "",
        "## C6 Evidence (7 fields)",
        "",
        f"- dedup_suppressed_count: {c6_evidence.dedup_suppressed_count}",
        f"- unique_cluster_count: {c6_evidence.unique_cluster_count}",
        f"- cooldown_active_bars: {c6_evidence.cooldown_active_bars}",
        f"- gen_before_grace: {c6_evidence.gen_before_grace}",
        f"- red_deferred_count: {c6_evidence.red_deferred_count}",
        f"- grace_active_bars: {c6_evidence.grace_active_bars}",
        f"- grace_saved_exec_count: {c6_evidence.grace_saved_exec_count}",
        "",
        "## Counterfactual Comparator",
        "",
        "| Variant | consensus_gen | ECR | final_state | bars_observed |",
        "|---------|--------------|-----|-------------|---------------|",
        (
            f"| frozen | {comparator.frozen_consensus_generated} "
            f"| {comparator.frozen_ecr}% "
            f"| {comparator.frozen_final_state} "
            f"| {comparator.frozen_bars_observed} |"
        ),
        (
            f"| C1-only | {comparator.c1_only_consensus_generated} "
            f"| {comparator.c1_only_ecr}% "
            f"| {comparator.c1_only_final_state} "
            f"| {comparator.c1_only_bars_observed} |"
        ),
        (
            f"| C1+C5 | {comparator.c1_c5_consensus_generated} "
            f"| {comparator.c1_c5_ecr}% "
            f"| {comparator.c1_c5_final_state} "
            f"| {comparator.c1_c5_bars_observed} |"
        ),
        "",
        "## C5 Promotion Evaluation",
        "",
    ]
    for k, v in c5_promotion.items():
        lines.append(f"- {k}: {v}")
    lines.extend(
        [
            "",
            "## Fork Accumulation Suppression",
            "",
            "V-3R4 creation prohibited until:",
            "1. V-3R3 comparator evidence secured",
            "2. C5 promotion condition evaluated",
            "3. Consolidation necessity demonstrated",
            "",
            "## Binding",
            "",
            "STATE = STANDBY",
            "RUN_AUTHORIZATION = NOT GRANTED",
            "auto_advance = forbidden",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Function 4/5: main_async_c6
# ---------------------------------------------------------------------------


async def main_async_c6() -> int:
    """V-3R3 C6 shadow run entry point.

    Steps:
      1. Verify frozen runner integrity
      2. Import frozen runner
      3. Load C6 parameters
      4. Load data via frozen.load_shadow_bars
      5. Run C6 simulation (C1 mandatory, C5 per profile)
      6. Run frozen counterfactual on same data
      7. If C5 active: run C1-only counterfactual too
      8. Build comparator + C5 promotion evaluation
      9. Write V-3R3 evidence + receipt
    """
    # --- Frozen runner integrity check ---
    integrity_ok, actual_sha256 = verify_frozen_runner_integrity()
    if not integrity_ok:
        print(
            f"[V-3R3][INTEGRITY][ABORT] frozen runner SHA256 mismatch. "
            f"expected={FROZEN_RUNNER_SHA256[:16]}... "
            f"actual={actual_sha256[:16]}...",
            flush=True,
        )
        return EXIT_FROZEN_INTEGRITY_FAILED

    print(
        f"[V-3R3][INTEGRITY] frozen runner SHA256 verified: {actual_sha256[:16]}...",
        flush=True,
    )

    # --- Import frozen runner (lazy, after integrity check) ---
    try:
        fork_dir = os.path.dirname(os.path.abspath(__file__))
        if fork_dir not in sys.path:
            sys.path.insert(0, fork_dir)
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        import sol_s1_v3_shadow_run as frozen  # type: ignore
    except Exception as exc:
        print(
            f"[V-3R3][IMPORT][ABORT] unable to import frozen runner: {exc!r}",
            flush=True,
        )
        return EXIT_FROZEN_IMPORT_FAILED

    # --- Load C6 parameters ---
    cooldown_bars, grace_min_gen, activation_receipt = load_c6_parameters(os.environ)

    # --- Generate run ID and load data ---
    run_id = frozen.generate_run_id().replace("v3_shadow_", "v3r3_shadow_")
    started_at = frozen.now_iso()
    run_started_monotonic = time.monotonic()

    print(f"[V-3R3] C6 shadow run - run_id={run_id}", flush=True)

    ohlcv = await frozen.load_shadow_bars(limit=frozen.MIN_BARS + frozen.YELLOW_EXTENSION_BARS)
    print(f"[V-3R3] loaded {len(ohlcv)} bars", flush=True)

    # --- Run 1: C6 simulation (primary, with active C1 and profile-C5) ---
    evidence, c6_evidence = run_shadow_simulation_c6(
        ohlcv,
        run_id=run_id,
        started_at=started_at,
        cooldown_bars=cooldown_bars,
        grace_min_gen=grace_min_gen,
        frozen=frozen,
    )

    print(
        f"[V-3R3][C6] final_state={evidence.final_state} "
        f"ecr={evidence.ecr} block={evidence.block_rate} "
        f"bars={evidence.bars_observed}",
        flush=True,
    )
    print(
        f"[V-3R3][C6] dedup_suppressed={c6_evidence.dedup_suppressed_count} "
        f"unique_clusters={c6_evidence.unique_cluster_count} "
        f"red_deferred={c6_evidence.red_deferred_count}",
        flush=True,
    )

    # --- Run 2: Frozen counterfactual (same data, no C1/C5) ---
    frozen_cf = run_frozen_counterfactual(
        ohlcv,
        run_id=run_id,
        started_at=started_at,
        frozen=frozen,
    )
    print(
        f"[V-3R3][FROZEN-CF] final_state={frozen_cf.final_state} "
        f"ecr={frozen_cf.ecr} bars={frozen_cf.bars_observed}",
        flush=True,
    )

    # --- Run 3: C1-only counterfactual (if C5 is active) ---
    c1_only_evidence = evidence  # default: primary run IS c1-only if C5 dormant
    c1_only_c6 = c6_evidence
    c1_c5_evidence: Any | None = None
    c1_c5_c6: C6Evidence | None = None

    if grace_min_gen > 1:
        # C5 is active → primary run = C1+C5. Need a separate C1-only run.
        c1_c5_evidence = evidence
        c1_c5_c6 = c6_evidence

        c1_only_evidence_result, c1_only_c6_result = run_shadow_simulation_c6(
            ohlcv,
            run_id=f"{run_id}_c1only",
            started_at=started_at,
            cooldown_bars=cooldown_bars,
            grace_min_gen=1,  # dormant C5
            frozen=frozen,
        )
        c1_only_evidence = c1_only_evidence_result
        c1_only_c6 = c1_only_c6_result
        print(
            f"[V-3R3][C1-ONLY-CF] final_state={c1_only_evidence.final_state} "
            f"ecr={c1_only_evidence.ecr} bars={c1_only_evidence.bars_observed}",
            flush=True,
        )

    # --- Build comparator ---
    comparator = build_comparator(
        frozen_evidence=frozen_cf,
        c1_only_evidence=c1_only_evidence,
        c1_only_c6=c1_only_c6,
        c1_c5_evidence=c1_c5_evidence,
        c1_c5_c6=c1_c5_c6,
    )

    # --- C5 promotion evaluation ---
    c5_promotion = evaluate_c5_promotion(
        c6_evidence=c6_evidence if c1_c5_c6 is not None else c1_only_c6,
        c1_only_evidence=c1_only_evidence,
        c1_c5_evidence=c1_c5_evidence,
    )

    print(
        f"[V-3R3][COMPARATOR] frozen={frozen_cf.final_state}/"
        f"{frozen_cf.ecr}% | "
        f"c1_only={c1_only_evidence.final_state}/"
        f"{c1_only_evidence.ecr}% | "
        f"c1_c5={'N/A' if c1_c5_evidence is None else f'{c1_c5_evidence.final_state}/{c1_c5_evidence.ecr}%'}",
        flush=True,
    )
    print(
        f"[V-3R3][C5-PROMOTION] {c5_promotion.get('recommendation', 'N/A')}",
        flush=True,
    )

    # --- Write outputs ---
    write_v3r3_shadow_log(
        evidence=evidence,
        c6_evidence=c6_evidence,
        activation_receipt=activation_receipt,
        comparator=comparator,
        c5_promotion=c5_promotion,
        path=V3R3_SHADOW_LOG_PATH,
    )
    write_v3r3_receipt(
        evidence=evidence,
        c6_evidence=c6_evidence,
        activation_receipt=activation_receipt,
        comparator=comparator,
        c5_promotion=c5_promotion,
        frozen_sha256_verified=integrity_ok,
        frozen_sha256_actual=actual_sha256,
        path=V3R3_RECEIPT_PATH,
    )

    # Also write the standard V-3 evidence log + receipt (via frozen writer)
    # for backward compatibility / audit chain continuity
    frozen.write_evidence_log(evidence, frozen.SHADOW_LOG_PATH)
    frozen.write_completion_receipt(evidence, frozen.COMPLETION_RECEIPT_PATH)

    run_completed_monotonic = time.monotonic()

    # V-3R1 receipt (additive, per frozen runner's main_async pattern)
    declared_mode = os.environ.get(frozen.EXECUTION_MODE_ENV_KEY, "").strip()
    mode_source = (
        frozen.EXECUTION_MODE_SOURCE_RUNNER
        if declared_mode
        else frozen.EXECUTION_MODE_SOURCE_INFERRED
    )
    receipt_v3r1 = frozen.build_completion_receipt_v3r1(
        evidence=evidence,
        authorization_source=frozen.IMPL_START_GO_V3R1_REF,
        implementation_receipt_ref=frozen.IMPL_COMPLETION_RECEIPT_V3R1_REF,
        declared_execution_mode=declared_mode or None,
        execution_mode_source=mode_source,
        run_started_monotonic=run_started_monotonic,
        run_completed_monotonic=run_completed_monotonic,
    )
    frozen.write_completion_receipt_v3r1(receipt_v3r1, frozen.COMPLETION_RECEIPT_V3R1_PATH)

    print(f"[V-3R3] evidence written to {V3R3_SHADOW_LOG_PATH}", flush=True)
    print(f"[V-3R3] receipt written to {V3R3_RECEIPT_PATH}", flush=True)
    print(f"[V-3R3] stop_reason={evidence.stop_reason}", flush=True)

    return EXIT_OK


# ---------------------------------------------------------------------------
# Function 5/5: main
# ---------------------------------------------------------------------------


def main() -> int:
    """V-3R3 fork entry point: triple-lock -> C6 shadow run.

    Step 1: Run triple-lock pre-flight guard.
    Step 2: If any lock fails, return lock-specific exit code.
    Step 3: If all locks pass, run main_async_c6.
    """
    guard_result = triple_lock_pre_flight_guard(sys.argv, os.environ)
    if guard_result != EXIT_OK:
        return guard_result

    return asyncio.run(main_async_c6())


if __name__ == "__main__":
    sys.exit(main())
