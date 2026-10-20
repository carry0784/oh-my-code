"""
Pipeline Dashboard API — Card B-7 (24-Symbol Data Pipeline Status)
Read-only monitoring endpoint for TimescaleDB hypertable health.

Separated from the main dashboard.py to avoid route-registration edge cases
with FastAPI's router ordering. Mounted at /pipeline prefix in main.py.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/status", include_in_schema=False)
async def pipeline_status(db: AsyncSession = Depends(get_db)):
    """Read-only: 24-symbol hypertable ingestion pipeline health."""
    from app.services.symbol_universe import ALL_SYMBOLS, SYMBOL_UNIVERSE

    now = datetime.now(timezone.utc)
    stale_threshold = timedelta(minutes=10)

    # ── OHLCV per-symbol summary ────────────────────────────────────
    ohlcv_rows = (await db.execute(text(
        "SELECT symbol, COUNT(*) as cnt, MIN(time) as first_t, MAX(time) as last_t "
        "FROM ohlcv_hyper GROUP BY symbol ORDER BY symbol"
    ))).fetchall()

    symbols_data = {}
    total_candles = 0
    fresh_count = 0
    stale_count = 0

    for row in ohlcv_rows:
        sym, cnt, first_t, last_t = row
        age = (now - last_t).total_seconds() if last_t else None
        is_fresh = age is not None and age < stale_threshold.total_seconds()
        if is_fresh:
            fresh_count += 1
        else:
            stale_count += 1
        total_candles += cnt
        symbols_data[sym] = {
            "candle_count": cnt,
            "first_candle": first_t.isoformat() if first_t else None,
            "last_candle": last_t.isoformat() if last_t else None,
            "age_seconds": round(age, 1) if age else None,
            "is_fresh": is_fresh,
        }

    for sym in ALL_SYMBOLS:
        if sym not in symbols_data:
            symbols_data[sym] = {
                "candle_count": 0, "first_candle": None,
                "last_candle": None, "age_seconds": None, "is_fresh": False,
            }
            stale_count += 1

    # ── Hypertable row counts ───────────────────────────────────────
    table_counts = {}
    for table in [
        "ohlcv_hyper", "funding_rate_hyper", "open_interest_hyper",
        "orderbook_snapshot_hyper", "sentiment_hyper",
    ]:
        result = (await db.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar()
        table_counts[table] = result or 0

    # ── Continuous aggregate status ─────────────────────────────────
    agg_rows = (await db.execute(text(
        "SELECT view_name FROM timescaledb_information.continuous_aggregates "
        "ORDER BY view_name"
    ))).fetchall()
    aggregates = [r[0] for r in agg_rows]

    # ── TimescaleDB jobs summary ────────────────────────────────────
    job_rows = (await db.execute(text(
        "SELECT application_name, schedule_interval, hypertable_name "
        "FROM timescaledb_information.jobs "
        "WHERE application_name LIKE '%Policy%' "
        "ORDER BY application_name"
    ))).fetchall()
    jobs = [{"name": r[0], "interval": str(r[1]), "table": r[2]} for r in job_rows]

    # ── Tier breakdown ──────────────────────────────────────────────
    tiers = {}
    for tier_name, tier_symbols in SYMBOL_UNIVERSE.items():
        tier_total = sum(symbols_data.get(s, {}).get("candle_count", 0) for s in tier_symbols)
        tier_fresh = sum(1 for s in tier_symbols if symbols_data.get(s, {}).get("is_fresh", False))
        tiers[tier_name] = {
            "symbols": len(tier_symbols),
            "total_candles": tier_total,
            "fresh": tier_fresh,
            "stale": len(tier_symbols) - tier_fresh,
        }

    return {
        "pipeline_status": "ACTIVE",
        "polled_at": now.isoformat(),
        "summary": {
            "total_symbols": len(ALL_SYMBOLS),
            "total_candles": total_candles,
            "fresh_symbols": fresh_count,
            "stale_symbols": stale_count,
            "coverage_pct": round((fresh_count / len(ALL_SYMBOLS)) * 100, 1) if ALL_SYMBOLS else 0,
        },
        "hypertables": table_counts,
        "continuous_aggregates": aggregates,
        "policies": jobs,
        "tiers": tiers,
        "symbols": symbols_data,
    }
