"""
timescale_policies.py — Card A: TimescaleDB Continuous Aggregate & Policy SQL

Provides SQL statement factories for:
  - Continuous aggregates: 1m → 5m/15m/1h/4h/1d roll-ups of ohlcv_hyper
  - Refresh policies: automated background refresh for each aggregate
  - Retention policies: data TTL per hypertable

Usage
-----
These functions return raw SQL strings intended to be executed once against the
TimescaleDB-enabled PostgreSQL instance (e.g. via psql, SQLAlchemy text(), or
a one-off management command).  They are NOT run automatically by Alembic to
keep the migration graph simple and avoid long-running DDL inside transactions.

Example (async SQLAlchemy)::

    from sqlalchemy import text
    from app.services.timescale_policies import get_continuous_aggregate_sql

    async with engine.begin() as conn:
        for sql in get_continuous_aggregate_sql():
            await conn.execute(text(sql))
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Continuous aggregate definitions
# ---------------------------------------------------------------------------
# Each aggregate rolls up ohlcv_hyper 1-minute data into a coarser timeframe.
# first() / last() require TimescaleDB hyperfunctions (toolkit extension).
# The aggregates are created as materialized views with WITH (timescaledb.continuous).

_AGGREGATE_CONFIGS: list[tuple[str, str]] = [
    # (view_name, bucket_width)
    ("ohlcv_5m",  "5 minutes"),
    ("ohlcv_15m", "15 minutes"),
    ("ohlcv_1h",  "1 hour"),
    ("ohlcv_4h",  "4 hours"),
    ("ohlcv_1d",  "1 day"),
]

# Refresh policy config: (lag_behind_realtime, schedule_interval)
# Lag must be >= chunk_time_interval of source hypertable (7 days for ohlcv_hyper).
_REFRESH_POLICY_CONFIGS: dict[str, tuple[str, str]] = {
    "ohlcv_5m":  ("1 hour",  "5 minutes"),
    "ohlcv_15m": ("1 hour",  "15 minutes"),
    "ohlcv_1h":  ("2 hours", "1 hour"),
    "ohlcv_4h":  ("4 hours", "4 hours"),
    "ohlcv_1d":  ("1 day",   "1 day"),
}

# Retention policy config: drop_after interval per hypertable
_RETENTION_CONFIGS: dict[str, str] = {
    "ohlcv_hyper":              "730 days",   # 2 years
    "funding_rate_hyper":       "365 days",
    "open_interest_hyper":      "365 days",
    "orderbook_snapshot_hyper": "90 days",
    "sentiment_hyper":          "365 days",
}


def get_continuous_aggregate_sql() -> list[str]:
    """Return CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous) statements.

    Each view aggregates ohlcv_hyper (assumed to contain 1m candles) into the
    target bucket width using OHLCV semantics:
      - open  = first value in bucket (by time)
      - high  = max value in bucket
      - low   = min value in bucket
      - close = last value in bucket (by time)
      - volume = sum of volume in bucket

    Requires:
      - timescaledb extension (always present after migration 029)
      - timescaledb_toolkit extension for first()/last() hyperfunctions

    Call ``CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit`` before running
    these statements if the toolkit is not already installed.
    """
    statements: list[str] = [
        "CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit",
    ]

    for view_name, bucket_width in _AGGREGATE_CONFIGS:
        sql = f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS {view_name}
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '{bucket_width}', time) AS bucket,
    exchange,
    symbol,
    first(open,   time) AS open,
    max(high)           AS high,
    min(low)            AS low,
    last(close,   time) AS close,
    sum(volume)         AS volume
FROM ohlcv_hyper
GROUP BY bucket, exchange, symbol
WITH NO DATA
""".strip()
        statements.append(sql)

    return statements


def get_refresh_policy_sql() -> list[str]:
    """Return add_continuous_aggregate_policy() calls for each aggregate view.

    Each policy instructs TimescaleDB to refresh the aggregate on a schedule,
    keeping it up-to-date within ``lag`` of real-time.

    start_offset: how far back to refresh (covers a sliding 30-day window).
    end_offset:   how close to real-time to refresh (lag).
    schedule_interval: how often to run the refresh job.
    """
    statements: list[str] = []

    for view_name, (lag, schedule) in _REFRESH_POLICY_CONFIGS.items():
        sql = f"""
SELECT add_continuous_aggregate_policy(
    '{view_name}',
    start_offset => INTERVAL '30 days',
    end_offset   => INTERVAL '{lag}',
    schedule_interval => INTERVAL '{schedule}'
)
""".strip()
        statements.append(sql)

    return statements


def get_retention_policy_sql() -> list[str]:
    """Return add_retention_policy() calls for each hypertable.

    Data older than ``drop_after`` is automatically removed by a background job.
    Retention policies only apply to the raw hypertables, not to continuous
    aggregate views (those have their own lifecycle tied to the source data).

    TTL rationale:
      - OHLCV (ohlcv_hyper):            730 days — 2 years of 1m candles for strategy R&D
      - Funding / OI / Sentiment:        365 days — 1 year for regime analysis
      - Orderbook snapshots:              90 days — high-volume, short analytical window
    """
    statements: list[str] = []

    for table_name, drop_after in _RETENTION_CONFIGS.items():
        sql = f"""
SELECT add_retention_policy(
    '{table_name}',
    INTERVAL '{drop_after}'
)
""".strip()
        statements.append(sql)

    return statements


def get_all_policy_sql() -> dict[str, list[str]]:
    """Convenience wrapper returning all policy SQL grouped by category.

    Returns::

        {
            "continuous_aggregates": [...],
            "refresh_policies":      [...],
            "retention_policies":    [...],
        }
    """
    return {
        "continuous_aggregates": get_continuous_aggregate_sql(),
        "refresh_policies": get_refresh_policy_sql(),
        "retention_policies": get_retention_policy_sql(),
    }
