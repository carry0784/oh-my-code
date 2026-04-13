"""PPF replay engine: bar-by-bar gate evaluation over historical OHLCV data.

Authority: PPF-IMPLEMENTATION-001-CORRECTION-R1
Purpose: Backtest the PPF novelty brake system by replaying OHLCV history
         through PPFGate one bar at a time, respecting the no-lookahead rule.

Design laws (enforced here):
    DL-PPF-001: Each bar i only receives ohlcv[0:i+1] — no future data leakage.
    DL-PPF-002: PPFGate is re-instantiated per replay_segment call — no state
                bleeds between independent replay sessions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from strategies.ppf.constants import MarketProfile, PPFState
from strategies.ppf.gate import PPFGate
from strategies.ppf.parameters import PPFParameters

logger = logging.getLogger("ppf.replay")

# Absolute minimum warmup floor (bars).
# Derived from: correlation_length(50) + projection_horizon(10) - small margin.
# Kept at 43 per specification to allow tighter param sets in the future.
_MIN_WARMUP_FLOOR: int = 43

# Sentinel reason code for bars after a constitution violation deactivates the gate.
_DEACTIVATED_REASON: str = "CONSTITUTION_DEACTIVATED"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PPFBarResult:
    """Single-bar PPF gate evaluation result.

    Attributes:
        bar_index: Zero-based index of the bar in the input ohlcv list.
        timestamp_ms: Bar open timestamp in milliseconds (ohlcv[bar_index][0]).
        ppf_state: PPFState.value string for the final state of this bar.
        allow_entry: True only when the gate reaches D6_EXECUTE_READY.
        deny_reason_code: RejectionCode.value or CONSTITUTION_DEACTIVATED
                          when entry is denied; None when allowed.
        regime_novelty_flag: O9 value for this bar (True = novelty brake fired).
        observation_snapshot: O4_raw, O5_raw, and O9 extracted from
                              last_log_entry.filter_contribution_map.
        interpretation_snapshot: I1-I5 values extracted from
                                 last_log_entry.filter_contribution_map.
        close_price: Closing price of this bar.
    """

    bar_index: int
    timestamp_ms: int
    ppf_state: str
    allow_entry: bool
    deny_reason_code: Optional[str]
    regime_novelty_flag: bool
    observation_snapshot: dict
    interpretation_snapshot: dict
    close_price: float


@dataclass
class PPFReplayResult:
    """Aggregated PPF replay result over all evaluated bars.

    Attributes:
        total_bars: Total bars in the input ohlcv list.
        evaluated_bars: Bars actually passed to the gate (i >= warmup).
        warmup_skipped_bars: Bars skipped because i < warmup.
        allow_count: Bars where gate returned allow_entry=True.
        deny_count: Bars where gate returned allow_entry=False (evaluated only).
        novelty_event_count: Bars where O9=True (regime_novelty_flag).
        novelty_events: List of {bar_index, timestamp_ms, close_price} dicts
                        for each novelty event.
        bar_results: Per-bar results (empty when record_bar_results=False).
        deny_reason_distribution: {reason_code: count} for denied bars.
        state_distribution: {ppf_state: count} for evaluated bars.
        deny_rate: deny_count / evaluated_bars, 0.0 if no evaluated bars.
        novelty_rate: novelty_event_count / evaluated_bars, 0.0 if none.
    """

    total_bars: int = 0
    evaluated_bars: int = 0
    warmup_skipped_bars: int = 0
    allow_count: int = 0
    deny_count: int = 0
    novelty_event_count: int = 0
    novelty_events: list[dict] = field(default_factory=list)
    bar_results: list[PPFBarResult] = field(default_factory=list)
    deny_reason_distribution: dict[str, int] = field(default_factory=dict)
    state_distribution: dict[str, int] = field(default_factory=dict)
    deny_rate: float = 0.0
    novelty_rate: float = 0.0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PPFReplayEngine:
    """Bar-by-bar PPF gate replay engine over historical OHLCV data.

    Usage::

        engine = PPFReplayEngine()
        result = engine.replay_segment(ohlcv_bars)
        print(f"allow_count={result.allow_count}, deny_rate={result.deny_rate:.2%}")

    Each call to replay_segment is fully independent: a fresh PPFGate instance
    is created and no state persists between calls (DL-PPF-002).

    The growing-window strategy (ohlcv[0:i+1]) mirrors production behavior
    where the full accumulated history is available at each candle boundary.
    """

    # Absolute warmup floor independent of params.
    MIN_WARMUP_BARS: int = _MIN_WARMUP_FLOOR

    def __init__(self, params: Optional[PPFParameters] = None) -> None:
        """Initialize the replay engine.

        Args:
            params: Frozen PPF parameter set. Defaults to M1_CRYPTO_FUTURES
                    defaults when None (suitable for SOL/USDT:1h backtesting).
        """
        if params is None:
            params = PPFParameters(market_profile=MarketProfile.M1_CRYPTO_FUTURES)
        self._params = params

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def replay_segment(
        self,
        ohlcv: list[list],
        risk_filter_pass: bool = False,
        record_bar_results: bool = True,
        asset_tag: str = "backtest:SOL/USDT:1h",
    ) -> PPFReplayResult:
        """Replay PPF gate evaluation bar-by-bar over a historical OHLCV segment.

        DL-PPF-001 compliance: bar i receives ohlcv[0:i+1] only — the growing
        window never includes future bars.

        DL-PPF-002 compliance: PPFGate is instantiated fresh at the start of
        this call; no inter-call state leakage.

        Args:
            ohlcv: List of bars in ascending time order. Each bar must be
                   [timestamp_ms, open, high, low, close, volume].
                   Bars must be sorted ASC by timestamp_ms.
            risk_filter_pass: External risk filter decision forwarded to
                              PPFGate.evaluate() unchanged. Typically False
                              for backtesting (conservative / no risk model).
            record_bar_results: When True, every evaluated bar's PPFBarResult
                                is appended to PPFReplayResult.bar_results.
                                Set to False for large runs where per-bar
                                detail is not required (saves memory).
            asset_tag: L5 asset-timeframe label forwarded to PPFGate and used
                       in audit log entries. Example: "backtest:SOL/USDT:1h".

        Returns:
            PPFReplayResult aggregating counts, distributions, and optionally
            per-bar results.

        Raises:
            ValueError: If ohlcv is empty or the first bar has fewer than 6
                        elements.
        """
        if not ohlcv:
            raise ValueError("ohlcv must be a non-empty list of bars")

        if len(ohlcv[0]) < 6:
            raise ValueError(
                "Each OHLCV bar must have at least 6 elements "
                "[ts, o, h, l, c, v]; got %d" % len(ohlcv[0])
            )

        result = PPFReplayResult(total_bars=len(ohlcv))
        warmup = self._effective_warmup()

        # DL-PPF-002: fresh gate per replay_segment call
        gate = PPFGate(params=self._params, asset_timeframe_tag=asset_tag)

        logger.info(
            "PPFReplayEngine.replay_segment start: total_bars=%d warmup=%d "
            "asset_tag=%s risk_filter_pass=%s",
            len(ohlcv),
            warmup,
            asset_tag,
            risk_filter_pass,
        )

        for i in range(len(ohlcv)):
            if i < warmup:
                result.warmup_skipped_bars += 1
                continue

            bar_result = self._evaluate_bar(
                gate=gate,
                ohlcv=ohlcv,
                bar_index=i,
                risk_filter_pass=risk_filter_pass,
            )

            result.evaluated_bars += 1

            if bar_result.allow_entry:
                result.allow_count += 1
            else:
                result.deny_count += 1
                reason = bar_result.deny_reason_code or "UNKNOWN"
                result.deny_reason_distribution[reason] = (
                    result.deny_reason_distribution.get(reason, 0) + 1
                )

            state_key = bar_result.ppf_state
            result.state_distribution[state_key] = result.state_distribution.get(state_key, 0) + 1

            if bar_result.regime_novelty_flag:
                result.novelty_event_count += 1
                result.novelty_events.append(
                    {
                        "bar_index": bar_result.bar_index,
                        "timestamp_ms": bar_result.timestamp_ms,
                        "close_price": bar_result.close_price,
                    }
                )

            if record_bar_results:
                result.bar_results.append(bar_result)

            # If constitution violation deactivated the gate, record all
            # remaining bars as CONSTITUTION_DEACTIVATED without further
            # evaluate() calls (fail-closed behavior; gate already returns False).
            if not gate.is_active:
                logger.error(
                    "PPFGate constitution violation detected at bar_index=%d. "
                    "Remaining bars recorded as CONSTITUTION_DEACTIVATED.",
                    i,
                )
                self._drain_deactivated_bars(
                    ohlcv=ohlcv,
                    from_index=i + 1,
                    warmup=warmup,
                    result=result,
                    record_bar_results=record_bar_results,
                )
                break

        if result.evaluated_bars > 0:
            result.deny_rate = result.deny_count / result.evaluated_bars
            result.novelty_rate = result.novelty_event_count / result.evaluated_bars

        logger.info(
            "PPFReplayEngine.replay_segment complete: evaluated=%d "
            "allow=%d deny=%d novelty=%d deny_rate=%.4f novelty_rate=%.4f",
            result.evaluated_bars,
            result.allow_count,
            result.deny_count,
            result.novelty_event_count,
            result.deny_rate,
            result.novelty_rate,
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _effective_warmup(self) -> int:
        """Compute the effective warmup bar count from params.

        Returns the larger of:
        - MIN_WARMUP_BARS (absolute floor = 43)
        - params.correlation_length + params.projection_horizon + 3

        The 3-bar buffer provides headroom for indicator initialisation and
        swing-distance lookback without edge-case index errors.
        """
        param_derived = self._params.correlation_length + self._params.projection_horizon + 3
        return max(self.MIN_WARMUP_BARS, param_derived)

    def _evaluate_bar(
        self,
        gate: PPFGate,
        ohlcv: list[list],
        bar_index: int,
        risk_filter_pass: bool,
    ) -> PPFBarResult:
        """Evaluate a single bar through the gate. Fail-closed on any error.

        DL-PPF-001: passes only ohlcv[0:bar_index+1] to numpy conversion.
        The growing window is equivalent to the production path where the
        full accumulated history is visible at each candle boundary.
        """
        bar = ohlcv[bar_index]
        timestamp_ms = int(bar[0])
        close_price = float(bar[4])

        try:
            # DL-PPF-001: growing window — no future bars included
            window = ohlcv[0 : bar_index + 1]
            highs = np.array([b[2] for b in window], dtype=np.float64)
            lows = np.array([b[3] for b in window], dtype=np.float64)
            closes = np.array([b[4] for b in window], dtype=np.float64)
            volumes = np.array([b[5] for b in window], dtype=np.float64)

            allow = gate.evaluate(
                highs=highs,
                lows=lows,
                closes=closes,
                volumes=volumes,
                risk_filter_pass=risk_filter_pass,
            )

            log_entry = gate.last_log_entry

            if log_entry is not None:
                ppf_state = log_entry.ppf_state
                # deny_reason_code is only meaningful when entry is denied
                deny_reason_code = None if allow else log_entry.rejection_reason_code
                regime_novelty_flag = log_entry.regime_novelty_flag
                observation_snapshot = _extract_observation_snapshot(log_entry)
                interpretation_snapshot = _extract_interpretation_snapshot(log_entry)
            else:
                # Gate returned but emitted no log entry — treat as fail-closed
                logger.warning(
                    "bar_index=%d: gate.last_log_entry is None after evaluate()",
                    bar_index,
                )
                ppf_state = PPFState.D1_IDLE.value
                deny_reason_code = None if allow else "NO_LOG_ENTRY"
                regime_novelty_flag = False
                observation_snapshot = {}
                interpretation_snapshot = {}

            return PPFBarResult(
                bar_index=bar_index,
                timestamp_ms=timestamp_ms,
                ppf_state=ppf_state,
                allow_entry=allow,
                deny_reason_code=deny_reason_code,
                regime_novelty_flag=regime_novelty_flag,
                observation_snapshot=observation_snapshot,
                interpretation_snapshot=interpretation_snapshot,
                close_price=close_price,
            )

        except Exception as exc:
            # Fail-closed: any evaluation error -> deny, record the error code
            logger.error(
                "PPFReplayEngine: bar_index=%d evaluation error (fail-closed): %r",
                bar_index,
                exc,
            )
            return PPFBarResult(
                bar_index=bar_index,
                timestamp_ms=timestamp_ms,
                ppf_state=PPFState.D1_IDLE.value,
                allow_entry=False,
                deny_reason_code="EVALUATION_ERROR",
                regime_novelty_flag=False,
                observation_snapshot={},
                interpretation_snapshot={},
                close_price=close_price,
            )

    def _drain_deactivated_bars(
        self,
        ohlcv: list[list],
        from_index: int,
        warmup: int,
        result: PPFReplayResult,
        record_bar_results: bool,
    ) -> None:
        """Record remaining bars as CONSTITUTION_DEACTIVATED after gate shutdown.

        Called after a constitution violation is detected. The gate is already
        deactivated; redundant evaluate() calls are skipped to avoid noise.
        Only bars that would have passed the warmup threshold are counted.
        """
        for i in range(from_index, len(ohlcv)):
            if i < warmup:
                # Should not normally happen (violation detected post-warmup),
                # but guard defensively.
                result.warmup_skipped_bars += 1
                continue

            bar = ohlcv[i]
            timestamp_ms = int(bar[0])
            close_price = float(bar[4])

            result.evaluated_bars += 1
            result.deny_count += 1
            result.deny_reason_distribution[_DEACTIVATED_REASON] = (
                result.deny_reason_distribution.get(_DEACTIVATED_REASON, 0) + 1
            )
            result.state_distribution[PPFState.D1_IDLE.value] = (
                result.state_distribution.get(PPFState.D1_IDLE.value, 0) + 1
            )

            if record_bar_results:
                result.bar_results.append(
                    PPFBarResult(
                        bar_index=i,
                        timestamp_ms=timestamp_ms,
                        ppf_state=PPFState.D1_IDLE.value,
                        allow_entry=False,
                        deny_reason_code=_DEACTIVATED_REASON,
                        regime_novelty_flag=False,
                        observation_snapshot={},
                        interpretation_snapshot={},
                        close_price=close_price,
                    )
                )


# ---------------------------------------------------------------------------
# Module-level log-entry extraction helpers
# ---------------------------------------------------------------------------


def _extract_observation_snapshot(log_entry) -> dict:
    """Extract observation fields from a PPFLogEntry into a plain dict.

    PPFLogEntry.filter_contribution_map carries O4_raw and O5_raw as the
    raw observation-time snapshots (M1 correction). O9 is stored as the
    top-level regime_novelty_flag. O1-O3 and O6-O8 are consumed upstream by
    the interpretation layer and are not persisted in the log entry; callers
    needing those must introspect ObservationFields directly at compute time.
    """
    fcm = log_entry.filter_contribution_map or {}
    return {
        "O4_raw": fcm.get("O4_raw"),
        "O5_raw": fcm.get("O5_raw"),
        "O9_regime_novelty_flag": log_entry.regime_novelty_flag,
    }


def _extract_interpretation_snapshot(log_entry) -> dict:
    """Extract I1-I5 scores from a PPFLogEntry.filter_contribution_map."""
    fcm = log_entry.filter_contribution_map or {}
    return {
        "I1": fcm.get("I1"),
        "I2": fcm.get("I2"),
        "I3": fcm.get("I3"),
        "I4": fcm.get("I4"),
        "I5": fcm.get("I5"),
    }
