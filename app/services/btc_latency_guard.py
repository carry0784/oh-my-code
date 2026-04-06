"""CR-048 Phase 5a-C -- BTC 7-Point Latency Guard.

Pure computation, no I/O, no DB, no logging.

All 7 guards must PASS or action resolves to SKIP_LATENCY_GUARD.
Any missing latency/spread metric resolves to FAIL (fail-closed).

BTC lane design must fail closed: any missing latency field, stale metric,
or ambiguous same-bar timing must resolve to SKIP_LATENCY_GUARD, not execution.

BTC lane adds guarded paper capability only; it does not expand
runtime activation capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.services.paper_trading_session_cr046 import CR046PaperSession

# ---------------------------------------------------------------------------
# Thresholds (Phase 4 evidence: BTC Sharpe drops 91% with 1-bar delay)
# ---------------------------------------------------------------------------

EXECUTION_LATENCY_MAX_MS = 5_000  # G2: order within 5 seconds of signal
API_LATENCY_MAX_MS = 2_000  # G3: API response under 2 seconds
SPREAD_MAX_PCT = 0.001  # G4: bid-ask spread under 0.1%
SAME_BAR_BUFFER_MINUTES = 55  # G1: T+55min deadline (5min buffer)
BAR_INTERVAL_MS = 3_600_000  # 1H bars

HIGH_LATENCY_THRESHOLD_MS = 10_000  # 10 seconds
HIGH_LATENCY_CONSECUTIVE_LIMIT = 3  # 3 consecutive → lane pause


# ---------------------------------------------------------------------------
# Guard result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GuardResult:
    """Immutable result of 7-point guard evaluation."""

    passed: bool
    fail_reason: str | None = None
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Guard evaluation (pure function)
# ---------------------------------------------------------------------------


def evaluate_btc_guard(
    bar_ts_ms: int,
    now_utc: datetime,
    execution_latency_ms: float | None,
    api_latency_ms: float | None,
    spread_pct: float | None,
    session: CR046PaperSession,
) -> GuardResult:
    """Evaluate all 7 BTC pre-trade guards.

    Returns GuardResult with pass/fail and per-guard details.
    Fail-closed: any None metric or ambiguous timing → FAIL.
    """
    details: dict = {}

    # G1: Same-bar check
    g1_pass = _check_same_bar(bar_ts_ms, now_utc)
    details["G1_same_bar"] = g1_pass
    details["G1_bar_ts_ms"] = bar_ts_ms
    if not g1_pass:
        details["overall"] = False
        details["fail_reason"] = "G1:same_bar_violation"
        return GuardResult(passed=False, fail_reason="G1:same_bar_violation", details=details)

    # G2: Execution latency
    g2_pass = execution_latency_ms is not None and execution_latency_ms <= EXECUTION_LATENCY_MAX_MS
    details["G2_execution_latency_ms"] = execution_latency_ms
    details["G2_pass"] = g2_pass
    if not g2_pass:
        reason = (
            "G2:execution_latency_missing"
            if execution_latency_ms is None
            else "G2:execution_latency_exceeded"
        )
        details["overall"] = False
        details["fail_reason"] = reason
        return GuardResult(passed=False, fail_reason=reason, details=details)

    # G3: API latency
    g3_pass = api_latency_ms is not None and api_latency_ms <= API_LATENCY_MAX_MS
    details["G3_api_latency_ms"] = api_latency_ms
    details["G3_pass"] = g3_pass
    if not g3_pass:
        reason = "G3:api_latency_missing" if api_latency_ms is None else "G3:api_latency_exceeded"
        details["overall"] = False
        details["fail_reason"] = reason
        return GuardResult(passed=False, fail_reason=reason, details=details)

    # G4: Spread
    g4_pass = spread_pct is not None and spread_pct <= SPREAD_MAX_PCT
    details["G4_spread_pct"] = spread_pct
    details["G4_pass"] = g4_pass
    if not g4_pass:
        reason = "G4:spread_missing" if spread_pct is None else "G4:spread_exceeded"
        details["overall"] = False
        details["fail_reason"] = reason
        return GuardResult(passed=False, fail_reason=reason, details=details)

    # G5: Daily loss check
    from app.services.paper_trading_session_cr046 import DAILY_LOSS_LIMIT

    g5_pass = session.daily_pnl > DAILY_LOSS_LIMIT
    details["G5_daily_pnl"] = session.daily_pnl
    details["G5_pass"] = g5_pass
    if not g5_pass:
        details["overall"] = False
        details["fail_reason"] = "G5:daily_loss_exceeded"
        return GuardResult(passed=False, fail_reason="G5:daily_loss_exceeded", details=details)

    # G6: Position check
    g6_pass = session.open_position is None
    details["G6_position_clear"] = g6_pass
    if not g6_pass:
        details["overall"] = False
        details["fail_reason"] = "G6:position_occupied"
        return GuardResult(passed=False, fail_reason="G6:position_occupied", details=details)

    # G7: Kill-switch / halt status
    g7_pass = not session.is_halted
    details["G7_not_halted"] = g7_pass
    if not g7_pass:
        details["overall"] = False
        details["fail_reason"] = f"G7:session_halted:{session.halt_reason}"
        return GuardResult(
            passed=False,
            fail_reason=f"G7:session_halted:{session.halt_reason}",
            details=details,
        )

    # All passed
    details["overall"] = True
    details["fail_reason"] = None
    return GuardResult(passed=True, fail_reason=None, details=details)


# ---------------------------------------------------------------------------
# Same-bar check (pure)
# ---------------------------------------------------------------------------


def _check_same_bar(bar_ts_ms: int, now_utc: datetime) -> bool:
    """Check if now_utc is within the valid execution window for bar_ts_ms.

    Valid window: [bar_open, bar_open + 55min].
    T+55min = 5-min buffer before next bar opens.
    """
    if bar_ts_ms <= 0:
        return False  # Invalid bar timestamp → fail-closed
    bar_open = datetime.fromtimestamp(bar_ts_ms / 1000, tz=timezone.utc)
    bar_deadline = bar_open + timedelta(minutes=SAME_BAR_BUFFER_MINUTES)
    return bar_open <= now_utc <= bar_deadline


# ---------------------------------------------------------------------------
# High-latency consecutive tracker (pure)
# ---------------------------------------------------------------------------


def update_high_latency_counter(
    session: CR046PaperSession,
    execution_latency_ms: float | None,
) -> tuple[CR046PaperSession, bool]:
    """Update consecutive high-latency counter.

    Returns (updated_session, should_pause).
    If execution_latency_ms > 10s, increment counter.
    If counter >= 3, set should_pause=True.
    If execution_latency_ms <= 10s or None, reset counter to 0.

    None latency does NOT increment (already handled by guard G2 skip),
    but does NOT reset either (conservative).
    """
    if execution_latency_ms is None:
        # Can't measure → don't change counter (conservative)
        should_pause = session.consecutive_high_latency >= HIGH_LATENCY_CONSECUTIVE_LIMIT
        return session, should_pause

    if execution_latency_ms > HIGH_LATENCY_THRESHOLD_MS:
        session.consecutive_high_latency += 1
    else:
        session.consecutive_high_latency = 0

    should_pause = session.consecutive_high_latency >= HIGH_LATENCY_CONSECUTIVE_LIMIT
    return session, should_pause
