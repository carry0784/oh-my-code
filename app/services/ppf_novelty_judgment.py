"""PPF Novelty Judgment Engine — post-hoc TP/FP/UNRESOLVED classification.

Provides judgment logic for PPF novelty brake events (O9=True / C11 activation).
After each novelty event a 20-candle observation window elapses; this engine
determines whether that brake was a True Positive (real disruption) or a False
Positive (noise).

Judgment criteria source: VAL-FPR-001 (SEALED 2026-04-13)
Quantification thresholds:  VAL-QTY-001 (SEALED 2026-04-13)

Design contract:
  - NO execution binding  (execution_binding = NONE)
  - NO promotion authority (promotion_open = FALSE)
  - NO auto-advance       (auto_advance = FORBIDDEN)
  - Read-only with respect to DB; callers own persistence

Reuse path:
  Phase A — PPFReplayEngine   calls judge_from_replay()
  Phase B — ppf_shadow_tasks  calls judge_batch_from_db()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NoveltyJudgment:
    """Post-hoc judgment of a single novelty event.

    Immutable after construction.  All numeric fields carry their
    original precision; callers are responsible for rounding in display.
    """

    event_bar_index: int
    """Zero-based index of the novelty event bar within the data segment."""

    event_timestamp_ms: int
    """Unix epoch milliseconds of the novelty event bar open."""

    close_at_event: float
    """Close price of the candle at which O9=True fired."""

    close_at_window_end: float | None
    """Close price of the candle at bar_index + window_bars.
    None when the observation window could not be completed."""

    window_bars: int
    """Configured observation window length (default 20, i.e. EV2 × 2)."""

    price_change_pct: float
    """Percentage price change over the observation window.

    Formula: (close_at_window_end - close_at_event) / close_at_event * 100
    Value is 0.0 when close_at_window_end is None or close_at_event <= 0.
    """

    judgment: str
    """One of: "TP" | "FP" | "UNRESOLVED"."""

    judgment_reason: str
    """Human-readable explanation referencing VAL-FPR-001 condition IDs."""


@dataclass
class NoveltyJudgmentReport:
    """Aggregated novelty judgment statistics over a set of events.

    FPR formula (VAL-QTY-001 §4-C):
      fpr = fp_count / (tp_count + fp_count)
      If (tp_count + fp_count) == 0, fpr = 0.0 (no resolved events).

    UNRESOLVED rate (VAL-QTY-001 §4-B, S2P-M2):
      unresolved_rate = unresolved_count / total_events
      If total_events == 0, unresolved_rate = 0.0.
    """

    total_events: int = 0
    tp_count: int = 0
    fp_count: int = 0
    unresolved_count: int = 0
    fpr: float = 0.0
    """False Positive Rate among resolved (TP+FP) events."""
    unresolved_rate: float = 0.0
    """Fraction of all events that remain UNRESOLVED."""
    judgments: list[NoveltyJudgment] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class NoveltyJudgmentEngine:
    """Post-hoc TP/FP judgment for PPF novelty brake events.

    Judgment criteria (VAL-FPR-001):

    TP (True Positive — novelty was real):
      |price_change_pct| > disruption_threshold within the observation window.
      Represents significant price movement confirming market disruption
      (simplified proxy for TP-C1 through TP-C4 in the full VAL-FPR-001 frame).

    FP (False Positive — novelty was noise):
      |price_change_pct| <= disruption_threshold AND observation window complete.
      No significant movement occurred; novelty brake fired unnecessarily.

    UNRESOLVED (VAL-FPR-001 §3-C):
      - Observation window incomplete (insufficient future bars)             → UR-C3
      - close_at_window_end is None                                          → UR-C1
      - close_at_event <= 0 (invalid / missing price data)                  → UR-C1

    Priority: UNRESOLVED > TP > FP  (VAL-FPR-001 §3-C judgment priority rule).

    Reusable by:
      - PPFReplayEngine  (Phase A — batch judgment over replay OHLCV segments)
      - ppf_shadow_tasks (Phase B — single-event judgment after window closes)
    """

    DEFAULT_WINDOW_BARS: int = 20
    """EV2 (projection_horizon=10) × 2 = 20 candles (VAL-FPR-001 §4)."""

    DEFAULT_DISRUPTION_THRESHOLD_PCT: float = 3.0
    """Minimum |price_change_pct| to classify a novelty event as TP.

    Default 3.0 % corresponds to the EV2×2 window threshold used during
    the Phase A backtest baseline. Subject to future calibration outside
    this module (VAL-QTY-001 F-9: threshold tuning BLOCKED at this layer).
    """

    def __init__(
        self,
        window_bars: int = DEFAULT_WINDOW_BARS,
        disruption_threshold_pct: float = DEFAULT_DISRUPTION_THRESHOLD_PCT,
    ) -> None:
        """Initialise the engine with frozen judgment parameters.

        Parameters
        ----------
        window_bars:
            Number of forward candles to observe after an O9=True event.
            Must be a positive integer.
        disruption_threshold_pct:
            Absolute price-change percentage threshold that separates TP from FP.
            Must be a positive float.
        """
        if window_bars <= 0:
            raise ValueError(f"window_bars must be > 0, got {window_bars}")
        if disruption_threshold_pct <= 0.0:
            raise ValueError(
                f"disruption_threshold_pct must be > 0, got {disruption_threshold_pct}"
            )

        self._window_bars = window_bars
        self._disruption_threshold_pct = disruption_threshold_pct

        logger.debug(
            "NoveltyJudgmentEngine initialised: window_bars=%d, "
            "disruption_threshold_pct=%.2f%%",
            self._window_bars,
            self._disruption_threshold_pct,
        )

    # ------------------------------------------------------------------
    # Core judgment — single event
    # ------------------------------------------------------------------

    def judge_single(
        self,
        close_at_event: float,
        close_at_window_end: float | None,
        window_complete: bool,
    ) -> tuple[str, str]:
        """Judge a single novelty event. Returns (judgment, reason).

        This is the canonical judgment function shared by both the replay
        path and the live runtime path.  All higher-level methods delegate
        to this function.

        Parameters
        ----------
        close_at_event:
            Close price at the bar where O9=True fired.
        close_at_window_end:
            Close price at bar_index + window_bars.  None when the
            window could not be completed (end-of-segment, data gap, etc.).
        window_complete:
            True when all window_bars forward candles are available.
            False forces UNRESOLVED regardless of price data.

        Returns
        -------
        tuple[str, str]
            (judgment, reason) where judgment is "TP" | "FP" | "UNRESOLVED".
        """
        # ----------------------------------------------------------------
        # UNRESOLVED checks — priority over TP/FP (VAL-FPR-001 §3-C)
        # ----------------------------------------------------------------

        if close_at_event <= 0.0:
            # UR-C1: price data invalid or missing
            reason = (
                f"UR-C1: close_at_event={close_at_event!r} is invalid (<= 0); "
                "observation window data unusable"
            )
            logger.debug("UNRESOLVED — %s", reason)
            return "UNRESOLVED", reason

        if close_at_window_end is None:
            # UR-C1: window-end price data absent
            reason = (
                "UR-C1: close_at_window_end is None; "
                "window-end price data not available"
            )
            logger.debug("UNRESOLVED — %s", reason)
            return "UNRESOLVED", reason

        if not window_complete:
            # UR-C3: observation window did not elapse fully
            reason = (
                "UR-C3: observation window not complete; "
                "insufficient future bars available for judgment"
            )
            logger.debug("UNRESOLVED — %s", reason)
            return "UNRESOLVED", reason

        # ----------------------------------------------------------------
        # Price change calculation
        # ----------------------------------------------------------------
        price_change_pct = (
            (close_at_window_end - close_at_event) / close_at_event * 100.0
        )
        abs_change = abs(price_change_pct)

        # ----------------------------------------------------------------
        # TP check
        # ----------------------------------------------------------------
        if abs_change > self._disruption_threshold_pct:
            reason = (
                f"TP: |price_change_pct|={abs_change:.4f}% exceeds "
                f"disruption_threshold={self._disruption_threshold_pct:.2f}%; "
                "significant price movement within observation window confirms "
                "market disruption (TP-C2 price proxy)"
            )
            logger.debug("TP — %s", reason)
            return "TP", reason

        # ----------------------------------------------------------------
        # FP check — window complete AND price movement within threshold
        # ----------------------------------------------------------------
        reason = (
            f"FP: |price_change_pct|={abs_change:.4f}% <= "
            f"disruption_threshold={self._disruption_threshold_pct:.2f}%; "
            "observation window complete with no significant disruption "
            "(FP-C1 + FP-C2 + FP-C3 satisfied)"
        )
        logger.debug("FP — %s", reason)
        return "FP", reason

    # ------------------------------------------------------------------
    # Phase A path — replay OHLCV segment
    # ------------------------------------------------------------------

    def judge_from_replay(
        self,
        ohlcv: list[list],
        novelty_events: list[dict],
    ) -> NoveltyJudgmentReport:
        """Judge novelty events using available forward bars from replay data.

        Parameters
        ----------
        ohlcv:
            Full OHLCV segment as a list of candles in chronological order.
            Each candle: [timestamp_ms, open, high, low, close, volume].
            Minimum index layout: index 0 = timestamp_ms, index 4 = close.
        novelty_events:
            List of novelty event descriptors, each a dict with keys:
              ``bar_index``    — zero-based candle index within *ohlcv*
              ``timestamp_ms`` — event bar open timestamp (milliseconds)

        Returns
        -------
        NoveltyJudgmentReport
            Aggregated statistics including per-event NoveltyJudgment records.

        Notes
        -----
        For each event at bar_index:
          - If bar_index + window_bars < len(ohlcv):
              close_event   = ohlcv[bar_index][4]
              close_end     = ohlcv[bar_index + window_bars][4]
              window_complete = True
          - Else (insufficient future data):
              UNRESOLVED via judge_single(..., window_complete=False)

        Events at the tail of the segment are always UNRESOLVED.  This is
        expected and not treated as an error.
        """
        report = NoveltyJudgmentReport()

        if not novelty_events:
            logger.debug(
                "judge_from_replay: no novelty events supplied; "
                "returning empty report"
            )
            return report

        segment_len = len(ohlcv)
        logger.info(
            "judge_from_replay: segment_len=%d, novelty_events=%d, "
            "window_bars=%d",
            segment_len,
            len(novelty_events),
            self._window_bars,
        )

        for event in novelty_events:
            bar_index: int = event["bar_index"]
            timestamp_ms: int = event["timestamp_ms"]

            # Determine if forward window is available
            end_index = bar_index + self._window_bars
            if end_index < segment_len:
                close_at_event: float = ohlcv[bar_index][4]
                close_at_window_end: float = ohlcv[end_index][4]
                window_complete = True
            else:
                # Tail of segment — window cannot be completed
                # close_at_event may still be valid for logging
                close_at_event = (
                    ohlcv[bar_index][4] if bar_index < segment_len else 0.0
                )
                close_at_window_end = None
                window_complete = False

            judgment_str, reason = self.judge_single(
                close_at_event=close_at_event,
                close_at_window_end=close_at_window_end,
                window_complete=window_complete,
            )

            price_change_pct = _safe_price_change_pct(
                close_at_event, close_at_window_end
            )

            record = NoveltyJudgment(
                event_bar_index=bar_index,
                event_timestamp_ms=timestamp_ms,
                close_at_event=close_at_event,
                close_at_window_end=close_at_window_end,
                window_bars=self._window_bars,
                price_change_pct=price_change_pct,
                judgment=judgment_str,
                judgment_reason=reason,
            )

            report.judgments.append(record)
            report.total_events += 1

            if judgment_str == "TP":
                report.tp_count += 1
            elif judgment_str == "FP":
                report.fp_count += 1
            else:
                report.unresolved_count += 1

        _finalise_report(report)

        logger.info(
            "judge_from_replay complete: total=%d TP=%d FP=%d UNRESOLVED=%d "
            "fpr=%.4f unresolved_rate=%.4f",
            report.total_events,
            report.tp_count,
            report.fp_count,
            report.unresolved_count,
            report.fpr,
            report.unresolved_rate,
        )
        return report

    # ------------------------------------------------------------------
    # Phase B path — DB-backed live events
    # ------------------------------------------------------------------

    def judge_batch_from_db(
        self,
        events: list,
    ) -> NoveltyJudgmentReport:
        """Judge events loaded from PPFNoveltyEvent DB records.

        Parameters
        ----------
        events:
            List of PPFNoveltyEvent ORM objects (or any object exposing the
            same attributes).  Required attributes per record:
              ``id``                        — primary key (int), used in logs
              ``observation_window_closed`` — bool
              ``close_price_at_event``      — float | None
              ``close_price_at_window_end`` — float | None
              ``observation_window_bars``   — int (may differ per record)

        Returns
        -------
        NoveltyJudgmentReport
            Aggregated statistics; judgments list carries one entry per
            input event, in the same order as *events*.

        Notes
        -----
        For events where observation_window_closed=True:
          judge_single(close_at_event, close_at_window_end, window_complete=True)
        For events where observation_window_closed=False:
          UNRESOLVED (UR-C3: window not yet elapsed)

        The engine does NOT persist judgment results back to the DB.
        Callers are responsible for writing judgment / judgment_reason /
        judgment_ts fields.
        """
        report = NoveltyJudgmentReport()

        if not events:
            logger.debug(
                "judge_batch_from_db: empty events list; returning empty report"
            )
            return report

        logger.info(
            "judge_batch_from_db: processing %d DB event records",
            len(events),
        )

        for ev in events:
            event_id: int = getattr(ev, "id", -1)
            window_closed: bool = bool(getattr(ev, "observation_window_closed", False))
            close_at_event: float | None = getattr(ev, "close_price_at_event", None)
            close_at_end: float | None = getattr(ev, "close_price_at_window_end", None)
            record_window_bars: int = getattr(
                ev, "observation_window_bars", self._window_bars
            )

            # Normalise close_at_event: treat None as 0.0 so judge_single
            # hits the UR-C1 path cleanly.
            effective_close_event: float = (
                float(close_at_event) if close_at_event is not None else 0.0
            )

            judgment_str, reason = self.judge_single(
                close_at_event=effective_close_event,
                close_at_window_end=(
                    float(close_at_end) if close_at_end is not None else None
                ),
                window_complete=window_closed,
            )

            price_change_pct = _safe_price_change_pct(
                effective_close_event,
                float(close_at_end) if close_at_end is not None else None,
            )

            record = NoveltyJudgment(
                event_bar_index=event_id,
                event_timestamp_ms=_event_ts_ms(ev),
                close_at_event=effective_close_event,
                close_at_window_end=(
                    float(close_at_end) if close_at_end is not None else None
                ),
                window_bars=record_window_bars,
                price_change_pct=price_change_pct,
                judgment=judgment_str,
                judgment_reason=reason,
            )

            report.judgments.append(record)
            report.total_events += 1

            if judgment_str == "TP":
                report.tp_count += 1
            elif judgment_str == "FP":
                report.fp_count += 1
            else:
                report.unresolved_count += 1

        _finalise_report(report)

        logger.info(
            "judge_batch_from_db complete: total=%d TP=%d FP=%d UNRESOLVED=%d "
            "fpr=%.4f unresolved_rate=%.4f",
            report.total_events,
            report.tp_count,
            report.fp_count,
            report.unresolved_count,
            report.fpr,
            report.unresolved_rate,
        )
        return report


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _safe_price_change_pct(
    close_at_event: float,
    close_at_window_end: float | None,
) -> float:
    """Compute price change percentage; return 0.0 on invalid inputs.

    Avoids ZeroDivisionError and propagates sentinel 0.0 when window-end
    price is unavailable so that callers can always store a numeric value.
    """
    if close_at_window_end is None:
        return 0.0
    if close_at_event <= 0.0:
        return 0.0
    return (close_at_window_end - close_at_event) / close_at_event * 100.0


def _event_ts_ms(ev: object) -> int:
    """Extract event timestamp as milliseconds from an ORM event object.

    Falls back to 0 when the attribute is absent or non-convertible.
    """
    event_ts = getattr(ev, "event_ts", None)
    if event_ts is None:
        return 0
    try:
        # datetime objects: convert to milliseconds
        return int(event_ts.timestamp() * 1000)
    except (AttributeError, TypeError, ValueError):
        return 0


def _finalise_report(report: NoveltyJudgmentReport) -> None:
    """Compute derived statistics on a partially-populated report in-place.

    Mutates:
      report.fpr             — FP / (TP + FP), 0.0 when denominator is 0
      report.unresolved_rate — UNRESOLVED / total_events, 0.0 when total is 0

    Called once after all events have been counted.
    """
    resolved = report.tp_count + report.fp_count
    report.fpr = report.fp_count / resolved if resolved > 0 else 0.0

    report.unresolved_rate = (
        report.unresolved_count / report.total_events
        if report.total_events > 0
        else 0.0
    )
