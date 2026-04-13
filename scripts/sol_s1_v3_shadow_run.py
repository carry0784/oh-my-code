"""SOL S-1 V-3 Shadow Drift Verification Run Script.

Purpose
-------
Shadow drift verification for C1C2_N2 config (N=2, max_positions=2, size=1%).
This is NOT a backtest. NOT a profitability test. This is drift stability
monitoring only.

References
----------
- Design: docs/operations/evidence/sol_s1_v3_design.md
- GO:    docs/operations/evidence/sol_s1_v3_go_receipt.md
- Scope: docs/operations/evidence/sol_s1_v3_impl_scope_lock.md
- Start: docs/operations/evidence/sol_s1_v3_impl_start_go.md

V-2 Baseline References (immutable)
-----------------------------------
- ECR:                   64.3%
- block_rate:            35.7%
- same_direction_ratio:  70.9%
- fitness:               0.4428

State Transition Thresholds
---------------------------
GREEN
  ECR >= 60%
  block_rate <= 40%
  SD_ratio <= 80.9% (baseline 70.9% + 10pp)
  invalid_run == 0

YELLOW  (observation extension, not immediate failure)
  55% <= ECR < 60%                  OR
  40% < block_rate <= 45%           OR
  80.9% < SD_ratio <= 85.9%         OR
  12-bar rolling ECR drop >= 10pp

RED  (fail-closed, immediate stop)
  ECR < 55%                         OR
  block_rate > 45%                  OR
  SD_ratio > 85.9%                  OR
  invalid >= 1                      OR
  Yellow extension exhausted without Green recovery

Stop Reasons (6 enum values, no additions)
------------------------------------------
- STOP_PASS_GREEN
- STOP_RED_ECR
- STOP_RED_BLOCK_RATE
- STOP_RED_SD_RATIO
- STOP_INVALID_RUN
- STOP_YELLOW_EXTENSION_EXHAUSTED

Constitutional Constraints
--------------------------
- Implementation GO allows implementation only, NOT shadow run execution.
- NO modification of V-1/V-2 scripts.
- NO modification of sealed design documents.
- NO modification of strategy source files.
- NO N1 fallback execution.
- NO N3 extension.
- NO profitability optimization logic.
- baseline_mutation must remain false.
- fallback_executed must remain false.

This file is produced under V-3 Implementation Start GO authorization.
Actual shadow run (96+ bars) requires a separate V-3 run GO.
"""

from __future__ import annotations

import asyncio
import dataclasses
import enum
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

# Allow running as a script while still being import-friendly.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Read-only imports (strategy source and service layer are locked)
from strategies.smc_wavetrend_strategy import (  # noqa: E402
    calc_smc_pure_causal,
    calc_wavetrend,
)
from app.core.database import async_session_factory  # noqa: E402
from app.services.history_data_manager import HistoryDataManager  # noqa: E402

# ---------------------------------------------------------------------------
# V-2 Baseline References (IMMUTABLE — do not modify)
# ---------------------------------------------------------------------------

V2_BASELINE_ECR: float = 64.3
V2_BASELINE_BLOCK_RATE: float = 35.7
V2_BASELINE_SD_RATIO: float = 70.9
V2_BASELINE_FITNESS: float = 0.4428

# ---------------------------------------------------------------------------
# State Transition Thresholds (IMMUTABLE)
# ---------------------------------------------------------------------------

GREEN_ECR_MIN: float = 60.0
GREEN_BLOCK_MAX: float = 40.0
GREEN_SD_DELTA_MAX: float = 10.0  # baseline + 10pp -> 80.9%

YELLOW_ECR_MIN: float = 55.0
YELLOW_BLOCK_MAX: float = 45.0
YELLOW_SD_DELTA_MAX: float = 15.0  # baseline + 15pp -> 85.9%

RED_ECR_THRESHOLD: float = 55.0
RED_BLOCK_THRESHOLD: float = 45.0
RED_SD_DELTA_THRESHOLD: float = 15.0

ROLLING_WINDOW: int = 12
ROLLING_ECR_DROP_YELLOW_PP: float = 10.0

# ---------------------------------------------------------------------------
# C1C2_N2 Config (IMMUTABLE)
# ---------------------------------------------------------------------------

CONFIG_LABEL: str = "C1C2_N2"
CONFIG_CONSENSUS_WINDOW: int = 2
CONFIG_MAX_POSITIONS: int = 2
CONFIG_POSITION_SIZE_PCT: float = 1.0
CONFIG_SL_PCT: float = 0.02
CONFIG_TP_PCT: float = 0.04

SYMBOL: str = "SOL/USDT:USDT"
TIMEFRAME: str = "1h"

# ---------------------------------------------------------------------------
# Run Parameters (IMMUTABLE)
# ---------------------------------------------------------------------------

MIN_BARS: int = 96
YELLOW_EXTENSION_BARS: int = 48
MAX_YELLOW_EXTENSIONS: int = 1
MIN_TRADES: int = 10

# ---------------------------------------------------------------------------
# Reference Document IDs
# ---------------------------------------------------------------------------

DESIGN_VERSION: str = "sol_s1_v3_design.md@2026-04-10"
GO_RECEIPT_ID: str = "sol_s1_v3_impl_start_go.md"
SCOPE_LOCK_ID: str = "sol_s1_v3_impl_scope_lock.md"

# Evidence output paths
EVIDENCE_DIR: Path = REPO_ROOT / "docs" / "operations" / "evidence"
SHADOW_LOG_PATH: Path = EVIDENCE_DIR / "sol_s1_v3_shadow_log.json"
COMPLETION_RECEIPT_PATH: Path = EVIDENCE_DIR / "sol_s1_v3_completion_receipt.md"

# ---------------------------------------------------------------------------
# V-3R1 Reference Document IDs (corrective sub-chain, IMMUTABLE)
# ---------------------------------------------------------------------------
# These constants are added under V-3R1 Implementation Start GO authorization
# (sol_s1_v3r1_impl_start_go.md, SEALED 2026-04-10, scope_lock_contract_ref =
# sol_s1_v3r1_scope_lock_go.md#forbidden_count_contract).
# They are ADDITIVE: the V-3 constants above remain intact.

DESIGN_VERSION_V3R1: str = "sol_s1_v3r1_design.md@2026-04-10"
IMPL_START_GO_V3R1_REF: str = "docs/operations/evidence/sol_s1_v3r1_impl_start_go.md"
SCOPE_LOCK_GO_V3R1_REF: str = "docs/operations/evidence/sol_s1_v3r1_scope_lock_go.md"
ANCHOR_GO_V3R1_REF: str = "docs/operations/evidence/sol_s1_v3r1_go_receipt.md"
DESIGN_REF_V3R1: str = "docs/operations/evidence/sol_s1_v3r1_design.md"
IMPL_COMPLETION_RECEIPT_V3R1_REF: str = (
    "docs/operations/evidence/sol_s1_v3r1_impl_completion_receipt.md"
)
SCOPE_LOCK_CONTRACT_REF: str = "sol_s1_v3r1_scope_lock_go.md#forbidden_count_contract"

# V-3R1 corrective-only declaration (fixed text, paste-ready from explicit GO §8)
CORRECTIVE_SCOPE_DECLARATION_V3R1: str = (
    "본 receipt 는 corrective implementation 기록에 한정되며, "
    "run 승인 / attempt #2 승인 / V-4 unlock 근거로 사용 금지."
)

# V-3R1 completion receipt path (separate artifact; V-3 receipt path untouched)
COMPLETION_RECEIPT_V3R1_PATH: Path = EVIDENCE_DIR / "sol_s1_v3r1_run_completion_receipt.md"

# Execution mode enum values (V-3R1 explicit GO §execution_mode 판정 규칙 잠금)
# Speed-only judgment is forbidden; declared value is primary.
EXECUTION_MODE_REALTIME_SHADOW: str = "realtime_shadow"
EXECUTION_MODE_HISTORICAL_REPLAY: str = "historical_replay"
EXECUTION_MODE_AMBIGUOUS: str = "ambiguous"

EXECUTION_MODE_SOURCE_GO: str = "declared_by_go"
EXECUTION_MODE_SOURCE_RUNNER: str = "declared_by_runner"
EXECUTION_MODE_SOURCE_INFERRED: str = "inferred_from_runtime"

MODE_CONSISTENCY_CONSISTENT: str = "consistent"
MODE_CONSISTENCY_WARNING: str = "warning"
MODE_CONSISTENCY_AMBIGUOUS: str = "ambiguous"

# Technical execution status (meta-layer core 5)
EXEC_STATUS_EXECUTED: str = "EXECUTED"
EXEC_STATUS_ABORTED: str = "ABORTED"
EXEC_STATUS_FAILED_TO_START: str = "FAILED_TO_START"

# Governance validity status (meta-layer core 5)
GOV_STATUS_VALID: str = "VALID"
GOV_STATUS_INVALID: str = "INVALID"
GOV_STATUS_CONFLICTED: str = "CONFLICTED"

# Optional runner-declared execution mode (env var)
EXECUTION_MODE_ENV_KEY: str = "SOL_S1_V3_EXECUTION_MODE"


# ---------------------------------------------------------------------------
# Block Reason Codes (V-3 design §5.1)
# ---------------------------------------------------------------------------

BLOCK_MAX_POSITIONS: str = "BLOCK_MAX_POSITIONS"
BLOCK_SAME_DIRECTION: str = "BLOCK_SAME_DIRECTION"
BLOCK_OPPOSITE_DIRECTION: str = "BLOCK_OPPOSITE_DIRECTION"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StopReason(str, enum.Enum):
    """Fixed 6-value enum. Adding new values requires a separate explicit GO."""

    PASS_GREEN = "STOP_PASS_GREEN"
    RED_ECR = "STOP_RED_ECR"
    RED_BLOCK_RATE = "STOP_RED_BLOCK_RATE"
    RED_SD_RATIO = "STOP_RED_SD_RATIO"
    INVALID_RUN = "STOP_INVALID_RUN"
    YELLOW_EXTENSION_EXHAUSTED = "STOP_YELLOW_EXTENSION_EXHAUSTED"

    @classmethod
    def allowed_values(cls) -> list[str]:
        return [e.value for e in cls]


class DriftState(str, enum.Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ShadowBarRecord:
    """Per-bar observation record (not persisted individually, aggregated)."""

    bar_ts: str
    bar_index: int
    consensus_dir: int
    consensus_generated: bool
    consensus_executable: bool
    block_code: Optional[str]
    open_positions: int
    slots_used: int
    slots_available: int
    config_fingerprint: str
    current_state: str


@dataclass
class ShadowMetrics:
    """Running aggregate metrics used for state classification."""

    consensus_generated: int = 0
    consensus_executable: int = 0
    consensus_blocked: int = 0
    block_max_positions: int = 0
    block_same_direction: int = 0
    block_opposite_direction: int = 0
    trades_count: int = 0
    invalid_bars: int = 0

    @property
    def total_blocks(self) -> int:
        return self.block_max_positions + self.block_same_direction + self.block_opposite_direction

    @property
    def ecr(self) -> float:
        if self.consensus_generated == 0:
            return 100.0  # no consensus yet → defer to Green defaults
        return (self.consensus_executable / self.consensus_generated) * 100.0

    @property
    def block_rate(self) -> float:
        if self.consensus_generated == 0:
            return 0.0
        return (self.consensus_blocked / self.consensus_generated) * 100.0

    @property
    def same_direction_ratio(self) -> float:
        if self.total_blocks == 0:
            return V2_BASELINE_SD_RATIO  # neutral until first block arrives
        return (self.block_same_direction / self.total_blocks) * 100.0

    @property
    def same_direction_delta_pp(self) -> float:
        return self.same_direction_ratio - V2_BASELINE_SD_RATIO


@dataclass
class SimPosition:
    """Shadow-simulated open position (no orders submitted)."""

    direction: int  # +1 long, -1 short
    entry_price: float
    entry_bar: int
    size_pct: float
    sl_price: float
    tp_price: float


@dataclass
class EvidenceLog:
    """Shadow evidence log — 18 required fields + 3 optional rolling fields."""

    # Required (18)
    run_id: str
    config_fingerprint: str
    design_version: str
    go_receipt_id: str
    bars_observed: int
    trades_count: int
    ecr: float
    block_rate: float
    same_direction_ratio: float
    same_direction_delta_pp: float
    yellow_extension_count: int
    invalid_run_count: int
    final_state: str
    receipt_completeness_pct: float
    stop_reason: str
    stop_reason_detail: str
    started_at: str
    ended_at: str
    # Optional (3)
    rolling_ecr_12: list[float] = field(default_factory=list)
    rolling_block_rate_12: list[float] = field(default_factory=list)
    rolling_sd_ratio_12: list[float] = field(default_factory=list)

    REQUIRED_FIELDS: tuple[str, ...] = (
        "run_id",
        "config_fingerprint",
        "design_version",
        "go_receipt_id",
        "bars_observed",
        "trades_count",
        "ecr",
        "block_rate",
        "same_direction_ratio",
        "same_direction_delta_pp",
        "yellow_extension_count",
        "invalid_run_count",
        "final_state",
        "receipt_completeness_pct",
        "stop_reason",
        "stop_reason_detail",
        "started_at",
        "ended_at",
    )

    def to_dict(self) -> dict:
        # Exclude class-level REQUIRED_FIELDS tuple from serialization
        data = {}
        for f in dataclasses.fields(self):
            data[f.name] = getattr(self, f.name)
        return data

    def validate_required(self) -> tuple[bool, list[str]]:
        """Return (ok, missing_field_names)."""
        missing: list[str] = []
        for field_name in self.REQUIRED_FIELDS:
            value = getattr(self, field_name, None)
            if value is None:
                missing.append(field_name)
            elif isinstance(value, str) and value == "":
                missing.append(field_name)
        return (len(missing) == 0, missing)


# ---------------------------------------------------------------------------
# V-3R1 CompletionReceipt (corrective schema — 16 required + 7 meta + 2 hash)
# ---------------------------------------------------------------------------
# This dataclass is ADDITIVE. It does NOT replace EvidenceLog above; the
# 18-field JSON shadow log schema remains unchanged. Instead, V-3R1 runs
# emit BOTH the V-3 artifacts (shadow_log.json + V-3 completion receipt)
# AND this new 25-field corrective receipt (V-3R1 completion receipt).
#
# Source of truth (do not modify without a fresh V-3R1 re-GO):
#   docs/operations/evidence/sol_s1_v3r1_go_receipt.md
#     §"Receipt 16필드 잠금 (V-3R1 완료 후 script가 반드시 출력)"
#     §"Meta-layer 필드 잠금 (핵심 5 + 보강 2 = 총 7)"
#     §"Schema hash 필드 잠금"
#     §"execution_mode 판정 규칙 잠금"


@dataclass
class CompletionReceipt:
    """V-3R1 Completion Receipt.

    Field groups (per V-3R1 explicit GO, verbatim from the "Receipt 16필드
    잠금" and "Meta-layer 필드 잠금" blocks):

    - Meta & Trust Chain (6): authorization_source, implementation_receipt_ref,
      design_version, implementation_artifacts_frozen, run_started_at,
      run_completed_at
    - Shadow Results Summary (6): final_state, run_result_class,
      bars_observed, trades_count, ecr, block_rate
    - Invariance Guards (4): baseline_mutation, fallback_executed,
      code_mutation_during_run, scope_lock_respected
    - Meta-layer core (5): technical_execution_status,
      governance_validity_status, execution_mode, run_duration_ms,
      bars_per_second
    - Meta-layer supplement (2): execution_mode_source,
      mode_consistency_check
    - Schema hashes (2): receipt_schema_hash, evidence_schema_hash

    Required field count = 16 (Meta 6 + Results 6 + Invariance 4).
    Meta-layer field count = 7 (core 5 + supplement 2).
    Schema hash field count = 2.
    """

    # --- Meta & Trust Chain (6) ---
    authorization_source: str
    implementation_receipt_ref: str
    design_version: str
    implementation_artifacts_frozen: bool
    run_started_at: str
    run_completed_at: str

    # --- Shadow Results Summary (6) ---
    final_state: str
    run_result_class: str
    bars_observed: int
    trades_count: int
    ecr: float
    block_rate: float

    # --- Invariance Guards (4) ---
    baseline_mutation: bool
    fallback_executed: bool
    code_mutation_during_run: bool
    scope_lock_respected: bool

    # --- Meta-layer core (5) ---
    technical_execution_status: str
    governance_validity_status: str
    execution_mode: str
    run_duration_ms: int
    bars_per_second: float

    # --- Meta-layer supplement (2) ---
    execution_mode_source: str
    mode_consistency_check: str

    # --- Schema hashes (2) ---
    receipt_schema_hash: str
    evidence_schema_hash: str

    # Class-level field inventories. Annotated so they match the EvidenceLog
    # self-describing pattern (they are serialized into the receipt for
    # schema traceability).
    REQUIRED_FIELDS_16: tuple[str, ...] = (
        # Meta & Trust Chain (6)
        "authorization_source",
        "implementation_receipt_ref",
        "design_version",
        "implementation_artifacts_frozen",
        "run_started_at",
        "run_completed_at",
        # Shadow Results Summary (6)
        "final_state",
        "run_result_class",
        "bars_observed",
        "trades_count",
        "ecr",
        "block_rate",
        # Invariance Guards (4)
        "baseline_mutation",
        "fallback_executed",
        "code_mutation_during_run",
        "scope_lock_respected",
    )

    META_LAYER_FIELDS_7: tuple[str, ...] = (
        # Core 5
        "technical_execution_status",
        "governance_validity_status",
        "execution_mode",
        "run_duration_ms",
        "bars_per_second",
        # Supplement 2
        "execution_mode_source",
        "mode_consistency_check",
    )

    SCHEMA_HASH_FIELDS_2: tuple[str, ...] = (
        "receipt_schema_hash",
        "evidence_schema_hash",
    )

    def to_dict(self) -> dict:
        data = {}
        for f in dataclasses.fields(self):
            data[f.name] = getattr(self, f.name)
        return data

    def validate_16_required(self) -> tuple[bool, list[str]]:
        """Check that all 16 required fields are present and non-empty.

        Booleans may be False; the check only rejects None and empty strings.
        Numeric zero values are permitted (e.g. 0 trades, 0% block_rate).
        """
        missing: list[str] = []
        for field_name in self.REQUIRED_FIELDS_16:
            value = getattr(self, field_name, None)
            if value is None:
                missing.append(field_name)
            elif isinstance(value, str) and value == "":
                missing.append(field_name)
        return (len(missing) == 0, missing)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def generate_run_id() -> str:
    """Deterministic-ish run id with ISO timestamp suffix."""
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"v3_shadow_{now}"


def generate_config_fingerprint() -> str:
    """Generate immutable config fingerprint for C1C2_N2."""
    payload = (
        f"{CONFIG_LABEL}|w={CONFIG_CONSENSUS_WINDOW}|"
        f"maxpos={CONFIG_MAX_POSITIONS}|size={CONFIG_POSITION_SIZE_PCT}|"
        f"sl={CONFIG_SL_PCT}|tp={CONFIG_TP_PCT}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{CONFIG_LABEL}_v3_{digest}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def truncate_detail(detail: str, limit: int = 160) -> str:
    """Stop reason detail must be <= 160 chars, single line."""
    single_line = detail.replace("\n", " ").replace("\r", " ")
    if len(single_line) > limit:
        return single_line[: limit - 3] + "..."
    return single_line


def has_windowed_consensus(
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
    bar_idx: int,
    window: int,
) -> int:
    """Return +1/-1 if SMC and WT agree within +/- window bars, else 0."""
    lo = max(0, bar_idx - window)
    hi = min(len(smc_signals), bar_idx + window + 1)
    smc_slice = smc_signals[lo:hi]
    wt_slice = wt_signals[lo:hi]
    # Long consensus
    if np.any(smc_slice > 0) and np.any(wt_slice > 0):
        return 1
    # Short consensus
    if np.any(smc_slice < 0) and np.any(wt_slice < 0):
        return -1
    return 0


def classify_block(
    consensus_dir: int,
    open_positions: list[SimPosition],
    max_positions: int,
) -> Optional[str]:
    """Classify why a consensus signal cannot open a new position."""
    if len(open_positions) >= max_positions:
        return BLOCK_MAX_POSITIONS
    for pos in open_positions:
        if pos.direction == consensus_dir:
            return BLOCK_SAME_DIRECTION
        if pos.direction == -consensus_dir:
            return BLOCK_OPPOSITE_DIRECTION
    return None


def classify_drift_state(
    metrics: ShadowMetrics,
    rolling_ecr: list[float],
) -> tuple[DriftState, Optional[StopReason], str]:
    """Classify current drift state using V-3 design §4 thresholds.

    Returns (state, stop_reason_if_red, detail_message).
    """
    # Invalid bar hard fail
    if metrics.invalid_bars >= 1:
        return (
            DriftState.RED,
            StopReason.INVALID_RUN,
            truncate_detail(f"invalid_bars={metrics.invalid_bars} >= 1 threshold"),
        )

    # Only evaluate ECR/block if we have at least one consensus signal
    have_consensus = metrics.consensus_generated > 0

    ecr = metrics.ecr if have_consensus else 100.0
    block_rate = metrics.block_rate if have_consensus else 0.0
    sd_delta = metrics.same_direction_delta_pp

    # --- Red conditions (fail-closed) ---
    if have_consensus and ecr < RED_ECR_THRESHOLD:
        return (
            DriftState.RED,
            StopReason.RED_ECR,
            truncate_detail(f"ecr={ecr:.2f}% < {RED_ECR_THRESHOLD:.1f}% threshold"),
        )
    if block_rate > RED_BLOCK_THRESHOLD:
        return (
            DriftState.RED,
            StopReason.RED_BLOCK_RATE,
            truncate_detail(f"block_rate={block_rate:.2f}% > {RED_BLOCK_THRESHOLD:.1f}% threshold"),
        )
    if sd_delta > RED_SD_DELTA_THRESHOLD:
        return (
            DriftState.RED,
            StopReason.RED_SD_RATIO,
            truncate_detail(
                f"sd_delta=+{sd_delta:.2f}pp > +{RED_SD_DELTA_THRESHOLD:.1f}pp threshold"
            ),
        )

    # --- Yellow conditions (observation extension) ---
    yellow_reasons: list[str] = []
    if have_consensus and YELLOW_ECR_MIN <= ecr < GREEN_ECR_MIN:
        yellow_reasons.append(f"ecr={ecr:.2f}% in [55,60)")
    if GREEN_BLOCK_MAX < block_rate <= YELLOW_BLOCK_MAX:
        yellow_reasons.append(f"block={block_rate:.2f}% in (40,45]")
    if GREEN_SD_DELTA_MAX < sd_delta <= YELLOW_SD_DELTA_MAX:
        yellow_reasons.append(f"sd_delta=+{sd_delta:.2f}pp in (+10,+15]")

    # Rolling ECR drop detection (2-axis drift: absolute + rate)
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


def compute_receipt_completeness(evidence: EvidenceLog) -> float:
    """Percentage of required fields present."""
    ok, missing = evidence.validate_required()
    total = len(evidence.REQUIRED_FIELDS)
    present = total - len(missing)
    return (present / total) * 100.0 if total > 0 else 0.0


# ---------------------------------------------------------------------------
# V-3R1 Schema Hash + Execution Mode Judgment (corrective helpers)
# ---------------------------------------------------------------------------


def compute_receipt_schema_hash() -> str:
    """Compute sha256 hash of the V-3R1 16-field completion receipt schema.

    The hash is taken over the pipe-delimited field names in
    `CompletionReceipt.REQUIRED_FIELDS_16`. It is emitted in every
    completion receipt to detect silent schema drift between V-3R1 runs.
    """
    payload = "|".join(CompletionReceipt.REQUIRED_FIELDS_16)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_evidence_schema_hash() -> str:
    """Compute sha256 hash of the 18-field evidence log schema.

    The hash is taken over the pipe-delimited field names in
    `EvidenceLog.REQUIRED_FIELDS`. It is emitted in every completion
    receipt so the completion receipt and the JSON shadow log can be
    cross-validated for schema drift.
    """
    payload = "|".join(EvidenceLog.REQUIRED_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def determine_execution_mode(
    declared_value: Optional[str],
    declared_source: str,
    run_duration_ms: int,
    bars_per_second: float,
) -> tuple[str, str, str]:
    """V-3R1 execution_mode 판정 로직 — DECLARED VALUE IS PRIMARY.

    Rules copied verbatim from V-3R1 explicit GO §"execution_mode 판정 규칙 잠금":

      - 주 판정 기준 = 명시 선언값 (execution_mode_source 로 출처 기록)
      - 보조 witness = run_duration_ms / bars_per_second
        (판정 근거 아님, 일치성 경고용)
      - 속도값(bars_per_second / run_duration_ms) 단독으로 execution_mode 를
        확정 판정하는 설계 절대 금지
      - ambiguous 구간 명시 허용

    This function IMPLEMENTS these rules. The speed values are consulted
    ONLY for the consistency check and NEVER to change the primary mode.
    If no valid declared value is supplied, the mode is `ambiguous`,
    regardless of how fast or slow the run was.

    Returns (execution_mode, execution_mode_source, mode_consistency_check).
    """
    # --- Primary judgment: declared value only ---
    if declared_value in (
        EXECUTION_MODE_REALTIME_SHADOW,
        EXECUTION_MODE_HISTORICAL_REPLAY,
    ):
        mode = declared_value
        source = declared_source
    else:
        # No valid declared value → ambiguous.
        # The speed witness is intentionally IGNORED here.
        mode = EXECUTION_MODE_AMBIGUOUS
        source = EXECUTION_MODE_SOURCE_INFERRED

    # --- Auxiliary witness: consistency check only ---
    # This block NEVER overrides `mode`. It only sets a consistency label.
    if mode == EXECUTION_MODE_HISTORICAL_REPLAY:
        # Replay is CPU-bound; sub-1 bps is suspicious but not disqualifying.
        if bars_per_second < 1.0:
            consistency = MODE_CONSISTENCY_WARNING
        else:
            consistency = MODE_CONSISTENCY_CONSISTENT
    elif mode == EXECUTION_MODE_REALTIME_SHADOW:
        # Realtime 1h feed should produce ~1 bar per 3600 seconds.
        # A realtime-declared run exceeding 0.1 bps is suspicious.
        if bars_per_second > 0.1:
            consistency = MODE_CONSISTENCY_WARNING
        else:
            consistency = MODE_CONSISTENCY_CONSISTENT
    else:
        # Ambiguous: by definition no consistency check is possible.
        consistency = MODE_CONSISTENCY_AMBIGUOUS

    return (mode, source, consistency)


def classify_run_result_class(
    final_state: DriftState,
    stop_reason: StopReason,
) -> str:
    """Classify V-3R1 `run_result_class` from drift state + stop reason.

    This label is a CORRECTIVE-CHAIN label and is NOT a V-3 PASS verdict.
    It encodes only the coarse terminal classification required by the
    V-3R1 Shadow Results Summary block.
    """
    if final_state == DriftState.GREEN and stop_reason == StopReason.PASS_GREEN:
        # Corrective-only PASS — NOT a V-3 shadow verification PASS.
        return "CORRECTIVE_PASS_GREEN"
    if final_state == DriftState.YELLOW:
        return "CORRECTIVE_YELLOW_OBSERVATION"
    if final_state == DriftState.RED:
        return "CORRECTIVE_RED_STOP"
    return "CORRECTIVE_UNDETERMINED"


def build_completion_receipt_v3r1(
    evidence: EvidenceLog,
    authorization_source: str,
    implementation_receipt_ref: str,
    declared_execution_mode: Optional[str],
    execution_mode_source: str,
    run_started_monotonic: float,
    run_completed_monotonic: float,
    technical_status: str = EXEC_STATUS_EXECUTED,
    governance_status: str = GOV_STATUS_VALID,
) -> "CompletionReceipt":
    """Assemble a CompletionReceipt from a shadow EvidenceLog + runtime meta.

    This function does NOT execute the shadow run; it only consumes the
    finished EvidenceLog and wraps it in the V-3R1 25-field structure.
    """
    # Runtime duration from monotonic clock (immune to wall-clock jumps).
    run_duration_ms = int(max(0.0, (run_completed_monotonic - run_started_monotonic) * 1000.0))
    if run_duration_ms > 0 and evidence.bars_observed > 0:
        bars_per_second = evidence.bars_observed / (run_duration_ms / 1000.0)
    else:
        bars_per_second = 0.0

    mode, mode_source, mode_consistency = determine_execution_mode(
        declared_value=declared_execution_mode,
        declared_source=execution_mode_source,
        run_duration_ms=run_duration_ms,
        bars_per_second=bars_per_second,
    )

    result_class = classify_run_result_class(
        final_state=DriftState(evidence.final_state),
        stop_reason=StopReason(evidence.stop_reason),
    )

    return CompletionReceipt(
        # Meta & Trust Chain (6)
        authorization_source=authorization_source,
        implementation_receipt_ref=implementation_receipt_ref,
        design_version=DESIGN_VERSION_V3R1,
        implementation_artifacts_frozen=True,
        run_started_at=evidence.started_at,
        run_completed_at=evidence.ended_at,
        # Shadow Results Summary (6)
        final_state=evidence.final_state,
        run_result_class=result_class,
        bars_observed=evidence.bars_observed,
        trades_count=evidence.trades_count,
        ecr=evidence.ecr,
        block_rate=evidence.block_rate,
        # Invariance Guards (4) — all static per V-3R1 scope lock
        baseline_mutation=False,
        fallback_executed=False,
        code_mutation_during_run=False,
        scope_lock_respected=True,
        # Meta-layer core (5)
        technical_execution_status=technical_status,
        governance_validity_status=governance_status,
        execution_mode=mode,
        run_duration_ms=run_duration_ms,
        bars_per_second=round(bars_per_second, 6),
        # Meta-layer supplement (2)
        execution_mode_source=mode_source,
        mode_consistency_check=mode_consistency,
        # Schema hashes (2)
        receipt_schema_hash=compute_receipt_schema_hash(),
        evidence_schema_hash=compute_evidence_schema_hash(),
    )


# ---------------------------------------------------------------------------
# Signal Precomputation (read-only use of strategy source)
# ---------------------------------------------------------------------------


def precompute_signals(
    ohlcv: list[list],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute SMC + WT signals for all loaded bars."""
    highs = np.array([bar[2] for bar in ohlcv], dtype=float)
    lows = np.array([bar[3] for bar in ohlcv], dtype=float)
    closes = np.array([bar[4] for bar in ohlcv], dtype=float)
    _, smc_signals = calc_smc_pure_causal(highs, lows, closes, internal_length=5)
    _, _, wt_signals = calc_wavetrend(highs, lows, closes, n1=10, n2=21)
    return closes, smc_signals, wt_signals


# ---------------------------------------------------------------------------
# Shadow Simulation Core (NOT called during implementation-only phase)
# ---------------------------------------------------------------------------


def simulate_shadow_bar(
    bar_index: int,
    bar_ts: str,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    smc_signals: np.ndarray,
    wt_signals: np.ndarray,
    open_positions: list[SimPosition],
    metrics: ShadowMetrics,
) -> ShadowBarRecord:
    """Simulate one shadow bar and update metrics.

    This function is deterministic and side-effect-free on external systems.
    Orders are NOT submitted; positions are tracked in memory only.
    """
    # 1) Check SL/TP on existing positions first
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

    # 2) Evaluate consensus within the window
    consensus_dir = has_windowed_consensus(
        smc_signals, wt_signals, bar_index, CONFIG_CONSENSUS_WINDOW
    )

    block_code: Optional[str] = None
    executable = False

    if consensus_dir != 0:
        metrics.consensus_generated += 1
        block_code = classify_block(consensus_dir, open_positions, CONFIG_MAX_POSITIONS)
        if block_code is None:
            # Open new shadow position
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
            if block_code == BLOCK_MAX_POSITIONS:
                metrics.block_max_positions += 1
            elif block_code == BLOCK_SAME_DIRECTION:
                metrics.block_same_direction += 1
            elif block_code == BLOCK_OPPOSITE_DIRECTION:
                metrics.block_opposite_direction += 1

    return ShadowBarRecord(
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
        current_state="",  # filled by caller after classify_drift_state
    )


def run_shadow_simulation(
    ohlcv: list[list],
    run_id: str,
    started_at: str,
) -> EvidenceLog:
    """Execute the full shadow drift verification loop.

    WARNING: this function is the actual shadow run. It MUST NOT be invoked
    during the implementation-only phase. It is called from `main()` which
    is guarded by a run authorization check.
    """
    closes, smc_signals, wt_signals = precompute_signals(ohlcv)

    metrics = ShadowMetrics()
    open_positions: list[SimPosition] = []
    rolling_ecr: list[float] = []
    rolling_block: list[float] = []
    rolling_sd: list[float] = []

    bars_budget = MIN_BARS
    yellow_extensions_used = 0
    stop_reason: StopReason = StopReason.PASS_GREEN
    stop_detail = ""
    final_state = DriftState.GREEN
    bar_index = 0

    total_available = len(ohlcv)

    while bar_index < min(bars_budget, total_available):
        bar = ohlcv[bar_index]
        bar_ts = (
            datetime.fromtimestamp(bar[0] / 1000, tz=timezone.utc).isoformat()
            if isinstance(bar[0], (int, float))
            else str(bar[0])
        )
        try:
            _record = simulate_shadow_bar(
                bar_index=bar_index,
                bar_ts=bar_ts,
                bar_high=float(bar[2]),
                bar_low=float(bar[3]),
                bar_close=float(bar[4]),
                smc_signals=smc_signals,
                wt_signals=wt_signals,
                open_positions=open_positions,
                metrics=metrics,
            )
        except Exception as exc:  # noqa: BLE001
            metrics.invalid_bars += 1
            stop_detail = truncate_detail(f"invalid bar {bar_index}: {type(exc).__name__}")

        rolling_ecr.append(metrics.ecr)
        rolling_block.append(metrics.block_rate)
        rolling_sd.append(metrics.same_direction_ratio)

        state, stop_reason_candidate, detail = classify_drift_state(metrics, rolling_ecr)
        final_state = state

        if state == DriftState.RED:
            stop_reason = stop_reason_candidate or StopReason.INVALID_RUN
            stop_detail = detail
            bar_index += 1
            break

        if state == DriftState.YELLOW:
            if yellow_extensions_used < MAX_YELLOW_EXTENSIONS:
                # Extend budget once; if we already extended we keep going
                # until the extension runs out, then re-check.
                if bars_budget == MIN_BARS:
                    bars_budget += YELLOW_EXTENSION_BARS
                    yellow_extensions_used += 1
            else:
                # Extension used; once we exceed base budget remain in Yellow
                if bar_index + 1 >= bars_budget:
                    stop_reason = StopReason.YELLOW_EXTENSION_EXHAUSTED
                    stop_detail = truncate_detail(f"yellow persisted after extension: {detail}")
                    bar_index += 1
                    break

        bar_index += 1

    ended_at = now_iso()

    # Final classification if not stopped early
    if bar_index >= bars_budget and final_state == DriftState.GREEN:
        stop_reason = StopReason.PASS_GREEN
        stop_detail = truncate_detail(f"completed {bar_index} bars in GREEN")

    evidence = EvidenceLog(
        run_id=run_id,
        config_fingerprint=generate_config_fingerprint(),
        design_version=DESIGN_VERSION,
        go_receipt_id=GO_RECEIPT_ID,
        bars_observed=bar_index,
        trades_count=metrics.trades_count,
        ecr=round(metrics.ecr, 4),
        block_rate=round(metrics.block_rate, 4),
        same_direction_ratio=round(metrics.same_direction_ratio, 4),
        same_direction_delta_pp=round(metrics.same_direction_delta_pp, 4),
        yellow_extension_count=yellow_extensions_used,
        invalid_run_count=metrics.invalid_bars,
        final_state=final_state.value,
        receipt_completeness_pct=0.0,  # filled below
        stop_reason=stop_reason.value,
        stop_reason_detail=stop_detail,
        started_at=started_at,
        ended_at=ended_at,
        rolling_ecr_12=[round(x, 4) for x in rolling_ecr[-ROLLING_WINDOW:]],
        rolling_block_rate_12=[round(x, 4) for x in rolling_block[-ROLLING_WINDOW:]],
        rolling_sd_ratio_12=[round(x, 4) for x in rolling_sd[-ROLLING_WINDOW:]],
    )
    evidence.receipt_completeness_pct = round(compute_receipt_completeness(evidence), 2)
    return evidence


# ---------------------------------------------------------------------------
# Output Writers
# ---------------------------------------------------------------------------


def write_evidence_log(evidence: EvidenceLog, path: Path) -> None:
    """Persist evidence log as JSON with atomic write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = evidence.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def write_completion_receipt(evidence: EvidenceLog, path: Path) -> None:
    """Write the shadow completion receipt markdown (run phase only)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SOL S-1 V-3 — Shadow Drift Verification Completion Receipt",
        "",
        f"**run_id:** {evidence.run_id}",
        f"**config_fingerprint:** {evidence.config_fingerprint}",
        f"**design_version:** {evidence.design_version}",
        f"**go_receipt_id:** {evidence.go_receipt_id}",
        f"**started_at:** {evidence.started_at}",
        f"**ended_at:** {evidence.ended_at}",
        "",
        "## Results",
        "",
        f"- bars_observed: {evidence.bars_observed}",
        f"- trades_count: {evidence.trades_count}",
        f"- ecr: {evidence.ecr}%",
        f"- block_rate: {evidence.block_rate}%",
        f"- same_direction_ratio: {evidence.same_direction_ratio}%",
        f"- same_direction_delta_pp: {evidence.same_direction_delta_pp}pp",
        f"- yellow_extension_count: {evidence.yellow_extension_count}",
        f"- invalid_run_count: {evidence.invalid_run_count}",
        f"- final_state: {evidence.final_state}",
        f"- stop_reason: {evidence.stop_reason}",
        f"- stop_reason_detail: {evidence.stop_reason_detail}",
        f"- receipt_completeness_pct: {evidence.receipt_completeness_pct}%",
        "",
        "## Immutability Witnesses",
        "",
        "- baseline_mutation: false",
        "- fallback_executed: false",
        "",
        "## Binding",
        "",
        "STATE = STANDBY",
        "RUN_AUTHORIZATION = NOT GRANTED",
        "auto_advance = 금지",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_completion_receipt_v3r1(receipt: CompletionReceipt, path: Path) -> None:
    """Write the V-3R1 corrective completion receipt markdown file.

    This is a NEW artifact separate from `write_completion_receipt` above;
    the V-3 receipt writer is unchanged. V-3R1 runs emit BOTH receipts so
    the original V-3 artifact chain remains intact for auditability.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SOL S-1 V-3R1 — Corrective Completion Receipt",
        "",
        "**design_reference:** `docs/operations/evidence/sol_s1_v3r1_design.md`",
        f"**authorization_source:** `{receipt.authorization_source}`",
        f"**scope_lock_contract_ref:** `{SCOPE_LOCK_CONTRACT_REF}`",
        f"**receipt_schema_hash:** `{receipt.receipt_schema_hash}`",
        f"**evidence_schema_hash:** `{receipt.evidence_schema_hash}`",
        "",
        "## Meta & Trust Chain (6)",
        "",
        f"- authorization_source: {receipt.authorization_source}",
        f"- implementation_receipt_ref: {receipt.implementation_receipt_ref}",
        f"- design_version: {receipt.design_version}",
        (
            f"- implementation_artifacts_frozen: "
            f"{str(receipt.implementation_artifacts_frozen).lower()}"
        ),
        f"- run_started_at: {receipt.run_started_at}",
        f"- run_completed_at: {receipt.run_completed_at}",
        "",
        "## Shadow Results Summary (6)",
        "",
        f"- final_state: {receipt.final_state}",
        f"- run_result_class: {receipt.run_result_class}",
        f"- bars_observed: {receipt.bars_observed}",
        f"- trades_count: {receipt.trades_count}",
        f"- ecr: {receipt.ecr}%",
        f"- block_rate: {receipt.block_rate}%",
        "",
        "## Invariance Guards (4)",
        "",
        f"- baseline_mutation: {str(receipt.baseline_mutation).lower()}",
        f"- fallback_executed: {str(receipt.fallback_executed).lower()}",
        (f"- code_mutation_during_run: {str(receipt.code_mutation_during_run).lower()}"),
        f"- scope_lock_respected: {str(receipt.scope_lock_respected).lower()}",
        "",
        "## Meta-layer Core (5)",
        "",
        f"- technical_execution_status: {receipt.technical_execution_status}",
        f"- governance_validity_status: {receipt.governance_validity_status}",
        f"- execution_mode: {receipt.execution_mode}",
        f"- run_duration_ms: {receipt.run_duration_ms}",
        f"- bars_per_second: {receipt.bars_per_second}",
        "",
        "## Meta-layer Supplement (2)",
        "",
        f"- execution_mode_source: {receipt.execution_mode_source}",
        f"- mode_consistency_check: {receipt.mode_consistency_check}",
        "",
        "## Schema Hashes (2)",
        "",
        f"- receipt_schema_hash: {receipt.receipt_schema_hash}",
        f"- evidence_schema_hash: {receipt.evidence_schema_hash}",
        "",
        "## Corrective Scope Declaration",
        "",
        CORRECTIVE_SCOPE_DECLARATION_V3R1,
        "",
        "## Binding",
        "",
        "STATE = STANDBY",
        "RUN_AUTHORIZATION = NOT GRANTED (V-3R1 corrective record only)",
        "auto_advance = 금지",
        "historical_replay PASS != realtime_shadow PASS",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Implementation-Phase Validation (syntax/import/schema/enum/fields)
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    name: str
    passed: bool
    detail: str


def validate_stop_reason_enum() -> ValidationResult:
    expected = {
        "STOP_PASS_GREEN",
        "STOP_RED_ECR",
        "STOP_RED_BLOCK_RATE",
        "STOP_RED_SD_RATIO",
        "STOP_INVALID_RUN",
        "STOP_YELLOW_EXTENSION_EXHAUSTED",
    }
    actual = set(StopReason.allowed_values())
    ok = actual == expected and len(actual) == 6
    return ValidationResult(
        name="stop_reason_enum",
        passed=ok,
        detail=f"expected 6 values, got {len(actual)}; match={actual == expected}",
    )


def validate_evidence_required_fields() -> ValidationResult:
    required = EvidenceLog.REQUIRED_FIELDS
    count = len(required)
    ok = count == 18
    return ValidationResult(
        name="evidence_required_fields",
        passed=ok,
        detail=f"required field count = {count} (expected 18)",
    )


def validate_evidence_instantiable() -> ValidationResult:
    try:
        sample = EvidenceLog(
            run_id="validation_stub",
            config_fingerprint=generate_config_fingerprint(),
            design_version=DESIGN_VERSION,
            go_receipt_id=GO_RECEIPT_ID,
            bars_observed=0,
            trades_count=0,
            ecr=0.0,
            block_rate=0.0,
            same_direction_ratio=0.0,
            same_direction_delta_pp=0.0,
            yellow_extension_count=0,
            invalid_run_count=0,
            final_state=DriftState.GREEN.value,
            receipt_completeness_pct=0.0,
            stop_reason=StopReason.PASS_GREEN.value,
            stop_reason_detail="validation stub",
            started_at=now_iso(),
            ended_at=now_iso(),
        )
        ok, missing = sample.validate_required()
        return ValidationResult(
            name="evidence_instantiable",
            passed=ok,
            detail=f"missing={missing}" if not ok else "all required fields present",
        )
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(
            name="evidence_instantiable",
            passed=False,
            detail=f"exception: {type(exc).__name__}: {exc}",
        )


def validate_block_taxonomy() -> ValidationResult:
    codes = {BLOCK_MAX_POSITIONS, BLOCK_SAME_DIRECTION, BLOCK_OPPOSITE_DIRECTION}
    ok = len(codes) == 3
    return ValidationResult(
        name="block_taxonomy",
        passed=ok,
        detail=f"block codes = {sorted(codes)}",
    )


def validate_config_immutability() -> ValidationResult:
    ok = (
        CONFIG_LABEL == "C1C2_N2"
        and CONFIG_CONSENSUS_WINDOW == 2
        and CONFIG_MAX_POSITIONS == 2
        and CONFIG_POSITION_SIZE_PCT == 1.0
        and CONFIG_SL_PCT == 0.02
        and CONFIG_TP_PCT == 0.04
    )
    return ValidationResult(
        name="config_immutability",
        passed=ok,
        detail=(
            f"label={CONFIG_LABEL} window={CONFIG_CONSENSUS_WINDOW} "
            f"max_pos={CONFIG_MAX_POSITIONS} size={CONFIG_POSITION_SIZE_PCT}"
        ),
    )


def validate_baseline_references() -> ValidationResult:
    ok = (
        V2_BASELINE_ECR == 64.3
        and V2_BASELINE_BLOCK_RATE == 35.7
        and V2_BASELINE_SD_RATIO == 70.9
        and abs(V2_BASELINE_FITNESS - 0.4428) < 1e-9
    )
    return ValidationResult(
        name="baseline_references",
        passed=ok,
        detail=(
            f"ecr={V2_BASELINE_ECR} block={V2_BASELINE_BLOCK_RATE} "
            f"sd={V2_BASELINE_SD_RATIO} fit={V2_BASELINE_FITNESS}"
        ),
    )


def validate_thresholds() -> ValidationResult:
    ok = (
        GREEN_ECR_MIN == 60.0
        and GREEN_BLOCK_MAX == 40.0
        and GREEN_SD_DELTA_MAX == 10.0
        and YELLOW_ECR_MIN == 55.0
        and YELLOW_BLOCK_MAX == 45.0
        and YELLOW_SD_DELTA_MAX == 15.0
    )
    return ValidationResult(
        name="state_thresholds",
        passed=ok,
        detail=(f"green: ecr>=60, block<=40, sd<=+10; yellow: ecr>=55, block<=45, sd<=+15"),
    )


def validate_paths() -> ValidationResult:
    ok = (
        SHADOW_LOG_PATH.name == "sol_s1_v3_shadow_log.json"
        and COMPLETION_RECEIPT_PATH.name == "sol_s1_v3_completion_receipt.md"
        and "sol_s1_v3" in SHADOW_LOG_PATH.name
    )
    return ValidationResult(
        name="output_paths",
        passed=ok,
        detail=f"log={SHADOW_LOG_PATH.name} receipt={COMPLETION_RECEIPT_PATH.name}",
    )


def validate_completion_receipt_schema_v3r1() -> ValidationResult:
    """V-3R1: CompletionReceipt must declare exactly 16 required fields."""
    count_16 = len(CompletionReceipt.REQUIRED_FIELDS_16)
    ok = count_16 == 16
    return ValidationResult(
        name="v3r1_completion_receipt_16_fields",
        passed=ok,
        detail=f"required field count = {count_16} (expected 16)",
    )


def validate_meta_layer_schema_v3r1() -> ValidationResult:
    """V-3R1: meta-layer must declare exactly 7 fields (core 5 + supplement 2)."""
    count_7 = len(CompletionReceipt.META_LAYER_FIELDS_7)
    ok = count_7 == 7
    return ValidationResult(
        name="v3r1_meta_layer_7_fields",
        passed=ok,
        detail=f"meta-layer field count = {count_7} (expected 7: 5 core + 2 supplement)",
    )


def validate_schema_hash_fields_v3r1() -> ValidationResult:
    """V-3R1: schema hash group must declare exactly 2 fields."""
    count_2 = len(CompletionReceipt.SCHEMA_HASH_FIELDS_2)
    ok = count_2 == 2
    return ValidationResult(
        name="v3r1_schema_hash_2_fields",
        passed=ok,
        detail=f"schema hash field count = {count_2} (expected 2)",
    )


def validate_schema_hash_stable_v3r1() -> ValidationResult:
    """V-3R1: schema hash computations must be deterministic and 64-hex."""
    h1 = compute_receipt_schema_hash()
    h2 = compute_receipt_schema_hash()
    e1 = compute_evidence_schema_hash()
    e2 = compute_evidence_schema_hash()
    ok = (
        h1 == h2
        and e1 == e2
        and len(h1) == 64
        and len(e1) == 64
        and h1 != e1  # 16-field and 18-field schemas MUST hash differently
    )
    return ValidationResult(
        name="v3r1_schema_hash_stable",
        passed=ok,
        detail=f"receipt={h1[:12]}... evidence={e1[:12]}... distinct={h1 != e1}",
    )


def validate_execution_mode_logic_v3r1() -> ValidationResult:
    """V-3R1: execution_mode must be judged from declared value, not speed.

    Per V-3R1 explicit GO §"execution_mode 판정 규칙 잠금":
      - 속도값 단독으로 execution_mode 를 확정 판정하는 설계 절대 금지

    This test exercises four cases to prove the rule:
      1. declared=historical_replay + fast speed → historical_replay/consistent
      2. declared=realtime_shadow + slow speed → realtime_shadow/consistent
      3. declared=None + VERY fast speed → ambiguous (NOT historical_replay)
      4. declared=historical_replay + VERY slow speed → historical_replay/warning
         (mode stays historical_replay; witness only raises warning)
    """
    # Case 1: declared historical_replay with high speed → consistent
    m1, _, c1 = determine_execution_mode(
        declared_value=EXECUTION_MODE_HISTORICAL_REPLAY,
        declared_source=EXECUTION_MODE_SOURCE_GO,
        run_duration_ms=1000,
        bars_per_second=100.0,
    )
    case1_ok = m1 == EXECUTION_MODE_HISTORICAL_REPLAY and c1 == MODE_CONSISTENCY_CONSISTENT

    # Case 2: declared realtime_shadow with slow speed → consistent
    m2, _, c2 = determine_execution_mode(
        declared_value=EXECUTION_MODE_REALTIME_SHADOW,
        declared_source=EXECUTION_MODE_SOURCE_RUNNER,
        run_duration_ms=3_600_000,
        bars_per_second=0.0003,
    )
    case2_ok = m2 == EXECUTION_MODE_REALTIME_SHADOW and c2 == MODE_CONSISTENCY_CONSISTENT

    # Case 3: missing declared value → ambiguous (NOT inferred from high speed)
    m3, s3, c3 = determine_execution_mode(
        declared_value=None,
        declared_source=EXECUTION_MODE_SOURCE_INFERRED,
        run_duration_ms=100,
        bars_per_second=1000.0,
    )
    case3_ok = (
        m3 == EXECUTION_MODE_AMBIGUOUS
        and s3 == EXECUTION_MODE_SOURCE_INFERRED
        and c3 == MODE_CONSISTENCY_AMBIGUOUS
    )

    # Case 4: declared historical_replay with VERY low speed → warning
    # but mode MUST still be historical_replay (witness does not override).
    m4, _, c4 = determine_execution_mode(
        declared_value=EXECUTION_MODE_HISTORICAL_REPLAY,
        declared_source=EXECUTION_MODE_SOURCE_GO,
        run_duration_ms=86_400_000,
        bars_per_second=0.001,
    )
    case4_ok = m4 == EXECUTION_MODE_HISTORICAL_REPLAY and c4 == MODE_CONSISTENCY_WARNING

    ok = all([case1_ok, case2_ok, case3_ok, case4_ok])
    return ValidationResult(
        name="v3r1_execution_mode_declared_primary",
        passed=ok,
        detail=(
            f"c1={case1_ok} c2={case2_ok} c3={case3_ok} c4={case4_ok} "
            f"(speed-only judgment forbidden)"
        ),
    )


def validate_completion_receipt_instantiable_v3r1() -> ValidationResult:
    """V-3R1: CompletionReceipt must instantiate with a stub EvidenceLog."""
    try:
        stub = EvidenceLog(
            run_id="v3r1_validation_stub",
            config_fingerprint=generate_config_fingerprint(),
            design_version=DESIGN_VERSION,
            go_receipt_id=GO_RECEIPT_ID,
            bars_observed=0,
            trades_count=0,
            ecr=0.0,
            block_rate=0.0,
            same_direction_ratio=0.0,
            same_direction_delta_pp=0.0,
            yellow_extension_count=0,
            invalid_run_count=0,
            final_state=DriftState.GREEN.value,
            receipt_completeness_pct=0.0,
            stop_reason=StopReason.PASS_GREEN.value,
            stop_reason_detail="validation stub",
            started_at=now_iso(),
            ended_at=now_iso(),
        )
        receipt = build_completion_receipt_v3r1(
            evidence=stub,
            authorization_source=IMPL_START_GO_V3R1_REF,
            implementation_receipt_ref=IMPL_COMPLETION_RECEIPT_V3R1_REF,
            declared_execution_mode=EXECUTION_MODE_HISTORICAL_REPLAY,
            execution_mode_source=EXECUTION_MODE_SOURCE_GO,
            run_started_monotonic=0.0,
            run_completed_monotonic=1.0,
        )
        ok, missing = receipt.validate_16_required()
        total_fields = len(dataclasses.fields(receipt))
        expected_total = 16 + 7 + 2 + 3  # 16 required + 7 meta + 2 hash + 3 class-level tuples
        return ValidationResult(
            name="v3r1_completion_receipt_instantiable",
            passed=ok and total_fields == expected_total,
            detail=(f"missing={missing} total_fields={total_fields} expected={expected_total}"),
        )
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(
            name="v3r1_completion_receipt_instantiable",
            passed=False,
            detail=f"exception: {type(exc).__name__}: {exc}",
        )


def validate_v3r1_reference_constants() -> ValidationResult:
    """V-3R1: all reference constants must point to V-3R1 documents."""
    ok = (
        DESIGN_VERSION_V3R1.startswith("sol_s1_v3r1_design.md")
        and "sol_s1_v3r1_impl_start_go.md" in IMPL_START_GO_V3R1_REF
        and "sol_s1_v3r1_scope_lock_go.md" in SCOPE_LOCK_GO_V3R1_REF
        and "sol_s1_v3r1_go_receipt.md" in ANCHOR_GO_V3R1_REF
        and ("sol_s1_v3r1_impl_completion_receipt.md" in IMPL_COMPLETION_RECEIPT_V3R1_REF)
        and SCOPE_LOCK_CONTRACT_REF == "sol_s1_v3r1_scope_lock_go.md#forbidden_count_contract"
        and "corrective" in CORRECTIVE_SCOPE_DECLARATION_V3R1
        and "V-4 unlock" in CORRECTIVE_SCOPE_DECLARATION_V3R1
    )
    return ValidationResult(
        name="v3r1_reference_constants",
        passed=ok,
        detail=f"design={DESIGN_VERSION_V3R1}",
    )


def validate_no_speed_only_execution_mode_code() -> ValidationResult:
    """V-3R1: source-level check that no speed-only judgment code exists.

    Per V-3R1 explicit GO INVALID condition:
      - 속도값 단독 판정 코드가 구현에 포함됨

    This heuristic scans the current source file for a forbidden pattern:
    a direct assignment of `execution_mode` from bars_per_second or
    run_duration_ms without going through `determine_execution_mode`.
    """
    try:
        source = Path(__file__).read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(
            name="v3r1_no_speed_only_judgment",
            passed=False,
            detail=f"source read failed: {exc}",
        )
    # Forbidden patterns: any direct assignment of the execution_mode
    # variable from a speed witness. The pattern strings are built from
    # fragments so the validator itself does NOT contain the literal
    # forbidden substrings (which would otherwise self-trigger).
    _em = "execution" + "_mode"
    _bps = "bars" + "_per_second"
    _dur = "run" + "_duration_ms"
    forbidden_patterns = [
        _em + " = " + _bps,
        _em + "=" + _bps,
        _em + " = " + _dur,
        _em + "=" + _dur,
    ]
    hits = [p for p in forbidden_patterns if p in source]
    ok = len(hits) == 0
    return ValidationResult(
        name="v3r1_no_speed_only_judgment",
        passed=ok,
        detail=(
            "no forbidden speed-only assignment pattern"
            if ok
            else f"forbidden pattern detected: {hits}"
        ),
    )


def run_implementation_validation() -> list[ValidationResult]:
    """Run all implementation-phase validations (no shadow execution)."""
    return [
        validate_stop_reason_enum(),
        validate_evidence_required_fields(),
        validate_evidence_instantiable(),
        validate_block_taxonomy(),
        validate_config_immutability(),
        validate_baseline_references(),
        validate_thresholds(),
        validate_paths(),
        # --- V-3R1 corrective validations (ADDITIVE) ---
        validate_completion_receipt_schema_v3r1(),
        validate_meta_layer_schema_v3r1(),
        validate_schema_hash_fields_v3r1(),
        validate_schema_hash_stable_v3r1(),
        validate_execution_mode_logic_v3r1(),
        validate_completion_receipt_instantiable_v3r1(),
        validate_v3r1_reference_constants(),
        validate_no_speed_only_execution_mode_code(),
    ]


# ---------------------------------------------------------------------------
# Data Loader (reads only, no writes)
# ---------------------------------------------------------------------------


async def load_shadow_bars(limit: int) -> list[list]:
    """Fetch OHLCV bars via HistoryDataManager (read-only)."""
    async with async_session_factory() as session:
        hdm = HistoryDataManager()
        ohlcv = await hdm.get_replay_candles(
            session=session,
            exchange="binance",
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            limit=limit,
        )
    return ohlcv


# ---------------------------------------------------------------------------
# Main Entry Point (guarded against implementation-phase execution)
# ---------------------------------------------------------------------------


RUN_AUTHORIZATION_ENV_KEY = "SOL_S1_V3_RUN_AUTHORIZED"
RUN_AUTHORIZATION_EXPECTED = "v3_run_go_granted"


async def main_async() -> int:
    """Shadow run entry point — only allowed with explicit run GO env var."""
    import os
    import time

    run_flag = os.environ.get(RUN_AUTHORIZATION_ENV_KEY, "")
    if run_flag != RUN_AUTHORIZATION_EXPECTED:
        print(
            "[ABORT] shadow run is NOT authorized by implementation GO.",
            flush=True,
        )
        print(
            f"[ABORT] set {RUN_AUTHORIZATION_ENV_KEY}={RUN_AUTHORIZATION_EXPECTED} "
            "only after a separate V-3 run GO is issued.",
            flush=True,
        )
        return 2

    run_id = generate_run_id()
    started_at = now_iso()
    run_started_monotonic = time.monotonic()
    print(f"[V-3] shadow run authorized — run_id={run_id}", flush=True)

    ohlcv = await load_shadow_bars(limit=MIN_BARS + YELLOW_EXTENSION_BARS)
    print(f"[V-3] loaded {len(ohlcv)} bars", flush=True)

    evidence = run_shadow_simulation(ohlcv, run_id=run_id, started_at=started_at)
    run_completed_monotonic = time.monotonic()

    write_evidence_log(evidence, SHADOW_LOG_PATH)
    write_completion_receipt(evidence, COMPLETION_RECEIPT_PATH)

    # --- V-3R1 corrective additions ---
    # Build and emit the 25-field (16 required + 7 meta-layer + 2 schema hash)
    # completion receipt. This is ADDITIVE: the V-3 receipt above is unchanged.
    declared_mode = os.environ.get(EXECUTION_MODE_ENV_KEY, "").strip()
    if declared_mode:
        mode_source_for_build = EXECUTION_MODE_SOURCE_RUNNER
    else:
        mode_source_for_build = EXECUTION_MODE_SOURCE_INFERRED

    receipt_v3r1 = build_completion_receipt_v3r1(
        evidence=evidence,
        authorization_source=IMPL_START_GO_V3R1_REF,
        implementation_receipt_ref=IMPL_COMPLETION_RECEIPT_V3R1_REF,
        declared_execution_mode=declared_mode or None,
        execution_mode_source=mode_source_for_build,
        run_started_monotonic=run_started_monotonic,
        run_completed_monotonic=run_completed_monotonic,
    )
    write_completion_receipt_v3r1(receipt_v3r1, COMPLETION_RECEIPT_V3R1_PATH)

    print(f"[V-3] final_state={evidence.final_state}", flush=True)
    print(f"[V-3] stop_reason={evidence.stop_reason}", flush=True)
    print(f"[V-3] bars_observed={evidence.bars_observed}", flush=True)
    print(f"[V-3] ecr={evidence.ecr} block={evidence.block_rate}", flush=True)
    print(
        f"[V-3R1] execution_mode={receipt_v3r1.execution_mode} "
        f"source={receipt_v3r1.execution_mode_source} "
        f"consistency={receipt_v3r1.mode_consistency_check}",
        flush=True,
    )
    print(
        f"[V-3R1] receipt_schema_hash={receipt_v3r1.receipt_schema_hash[:12]}... "
        f"evidence_schema_hash={receipt_v3r1.evidence_schema_hash[:12]}...",
        flush=True,
    )
    print(
        f"[V-3R1] run_result_class={receipt_v3r1.run_result_class} "
        f"run_duration_ms={receipt_v3r1.run_duration_ms}",
        flush=True,
    )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    # Default CLI behavior: validation only. The actual shadow run requires
    # the explicit --run flag AND the SOL_S1_V3_RUN_AUTHORIZED environment
    # variable AND a separate V-3 run GO.
    if "--run" in sys.argv:
        sys.exit(main())
    # Default path: implementation-phase validation
    print("[V-3] implementation-phase validation only (no shadow run)", flush=True)
    results = run_implementation_validation()
    all_passed = all(r.passed for r in results)
    for r in results:
        status = "OK" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}: {r.detail}", flush=True)
    print(
        f"[V-3] validation summary: {sum(1 for r in results if r.passed)}/{len(results)} passed",
        flush=True,
    )
    sys.exit(0 if all_passed else 1)
