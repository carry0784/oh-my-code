"""PPF Logging schema (L1-L6 + rejection codes).

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1

Log fields:
    L1: projection_actual_error (post-hoc, after projection horizon expires)
    L2: filter_contribution_map (per-judgment, includes O4_raw/O5_raw)
    L3: false_positive_flag (post-hoc, after position close)
    L4: rejection_reason_code (on R1 occurrence)
    L5: asset_timeframe_tag (every candle)
    L6: regime_novelty_flag (every candle)

Audit principle: ALL state transitions are logged, not just final state.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from strategies.ppf.constants import PPFState, RejectionCode, TransitionOutcome
from strategies.ppf.decision import DecisionResult
from strategies.ppf.interpretation import InterpretationScores
from strategies.ppf.observation import ObservationFields

logger = logging.getLogger("ppf.audit")


@dataclass
class PPFLogEntry:
    """Single PPF audit log entry capturing full evaluation state.

    Captures L1-L6 fields plus observation/interpretation snapshots.
    """

    # Metadata
    timestamp: str
    asset_timeframe_tag: str  # L5: e.g. "binance:SOL/USDT:1h"

    # Decision result
    ppf_state: str
    allow_entry: bool

    # L2: filter_contribution_map (includes O4_raw, O5_raw)
    filter_contribution_map: dict[str, float]

    # L4: rejection_reason_code (null if no rejection)
    rejection_reason_code: Optional[str]

    # B2 audit trail: the state where rejection occurred (null if no rejection)
    reached_state: Optional[str]

    # L6: regime_novelty_flag
    regime_novelty_flag: bool

    # L1: projection_actual_error (filled post-hoc, null at judgment time)
    projection_actual_error: Optional[float] = None

    # L3: false_positive_flag (filled post-hoc, null at judgment time)
    false_positive_flag: Optional[bool] = None


def build_log_entry(
    obs: ObservationFields,
    scores: InterpretationScores,
    result: DecisionResult,
    asset_timeframe_tag: str,
) -> PPFLogEntry:
    """Build a PPF audit log entry from evaluation results.

    L2 filter_contribution_map includes:
    - I1-I5 scores
    - O4_raw, O5_raw (observation time raw snapshot, M1 correction)

    L1 and L3 are set to None (filled post-hoc after projection expires).
    """
    return PPFLogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        asset_timeframe_tag=asset_timeframe_tag,
        ppf_state=result.state.value,
        allow_entry=result.allow_entry,
        filter_contribution_map={
            "I1": scores.projection_bias_score,
            "I2": scores.trend_alignment_score,
            "I3": scores.volume_confirmation_score,
            "I4": scores.path_quality_score,
            "I5": scores.structure_rr_score,
            "O4_raw": obs.expected_adverse_excursion_before_target,
            "O5_raw": obs.expected_favorable_excursion_to_target,
        },
        rejection_reason_code=(result.rejection_code.value if result.rejection_code else None),
        reached_state=(result.reached_state.value if result.reached_state else None),
        regime_novelty_flag=obs.regime_novelty_flag,
        projection_actual_error=None,  # L1: filled post-hoc
        false_positive_flag=None,  # L3: filled post-hoc
    )


def emit_log(entry: PPFLogEntry) -> None:
    """Emit a PPF audit log entry.

    All state transitions must be logged (audit principle).
    """
    log_dict: dict[str, Any] = {
        "timestamp": entry.timestamp,
        "asset_timeframe_tag": entry.asset_timeframe_tag,
        "ppf_state": entry.ppf_state,
        "allow_entry": entry.allow_entry,
        "filter_contribution_map": entry.filter_contribution_map,
        "rejection_reason_code": entry.rejection_reason_code,
        "reached_state": entry.reached_state,
        "regime_novelty_flag": entry.regime_novelty_flag,
    }

    # Only include post-hoc fields if they are set
    if entry.projection_actual_error is not None:
        log_dict["projection_actual_error"] = entry.projection_actual_error
    if entry.false_positive_flag is not None:
        log_dict["false_positive_flag"] = entry.false_positive_flag

    logger.info(json.dumps(log_dict, ensure_ascii=False))
