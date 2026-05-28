"""029: TimescaleDB hypertables — Card A Data Lake (5 time-series tables).

Creates five hypertable-backed tables for live market data ingestion:
  - ohlcv_hyper          (7-day chunks)
  - funding_rate_hyper   (30-day chunks)
  - open_interest_hyper  (30-day chunks)
  - orderbook_snapshot_hyper (30-day chunks)
  - sentiment_hyper      (30-day chunks)

Requires timescale/timescaledb:latest-pg16 Docker image.
TimescaleDB extension is created idempotently before any hypertable conversion.

Revision ID: 029_timescaledb_hypertables
Revises: 028_observation_chain
"""

from alembic import op
import sqlalchemy as sa

revision = "029_timescaledb_hypertables"
down_revision = "028_observation_chain"
branch_labels = None
depends_on = None

# Chunk intervals expressed as PostgreSQL interval strings
_7_DAYS = "INTERVAL '7 days'"
_30_DAYS = "INTERVAL '30 days'"


def upgrade():
    # ── 1. Enable TimescaleDB extension ──────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # ── 2. Create tables ──────────────────────────────────────────────

    op.create_table(
        "ohlcv_hyper",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, primary_key=True),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("open", sa.Float, nullable=False),
        sa.Column("high", sa.Float, nullable=False),
        sa.Column("low", sa.Float, nullable=False),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.Float, nullable=False),
        sa.UniqueConstraint("exchange", "symbol", "timeframe", "time", name="uq_ohlcv_hyper_slot"),
    )

    op.create_table(
        "funding_rate_hyper",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, primary_key=True),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("funding_rate", sa.Float, nullable=False),
        sa.Column("mark_price", sa.Float, nullable=True),
        sa.Column("index_price", sa.Float, nullable=True),
        sa.Column("next_funding_time", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("exchange", "symbol", "time", name="uq_funding_rate_hyper_slot"),
    )

    op.create_table(
        "open_interest_hyper",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, primary_key=True),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("open_interest", sa.Float, nullable=False),
        sa.Column("open_interest_value", sa.Float, nullable=True),
        sa.UniqueConstraint("exchange", "symbol", "time", name="uq_open_interest_hyper_slot"),
    )

    op.create_table(
        "orderbook_snapshot_hyper",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, primary_key=True),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("bid_prices", sa.JSON, nullable=False),
        sa.Column("bid_volumes", sa.JSON, nullable=False),
        sa.Column("ask_prices", sa.JSON, nullable=False),
        sa.Column("ask_volumes", sa.JSON, nullable=False),
        sa.Column("spread", sa.Float, nullable=False),
        sa.Column("mid_price", sa.Float, nullable=False),
        sa.UniqueConstraint("exchange", "symbol", "time", name="uq_orderbook_snapshot_hyper_slot"),
    )

    op.create_table(
        "sentiment_hyper",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=True, primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("raw_json", sa.JSON, nullable=True),
        sa.UniqueConstraint(
            "source", "symbol", "metric_name", "time", name="uq_sentiment_hyper_slot"
        ),
    )

    # ── 3. Convert each table to a hypertable ────────────────────────
    op.execute(
        f"SELECT create_hypertable('ohlcv_hyper', 'time', "
        f"chunk_time_interval => {_7_DAYS}, migrate_data => true)"
    )
    op.execute(
        f"SELECT create_hypertable('funding_rate_hyper', 'time', "
        f"chunk_time_interval => {_30_DAYS}, migrate_data => true)"
    )
    op.execute(
        f"SELECT create_hypertable('open_interest_hyper', 'time', "
        f"chunk_time_interval => {_30_DAYS}, migrate_data => true)"
    )
    op.execute(
        f"SELECT create_hypertable('orderbook_snapshot_hyper', 'time', "
        f"chunk_time_interval => {_30_DAYS}, migrate_data => true)"
    )
    op.execute(
        f"SELECT create_hypertable('sentiment_hyper', 'time', "
        f"chunk_time_interval => {_30_DAYS}, migrate_data => true)"
    )

    # ── 4. Additional query-pattern indexes ──────────────────────────
    # ohlcv_hyper: common pattern is symbol+timeframe range scan
    op.create_index(
        "ix_ohlcv_hyper_lookup",
        "ohlcv_hyper",
        ["exchange", "symbol", "timeframe", "time"],
    )
    # funding / OI / orderbook / sentiment: symbol+time range scan
    op.create_index(
        "ix_funding_rate_hyper_lookup",
        "funding_rate_hyper",
        ["exchange", "symbol", "time"],
    )
    op.create_index(
        "ix_open_interest_hyper_lookup",
        "open_interest_hyper",
        ["exchange", "symbol", "time"],
    )
    op.create_index(
        "ix_orderbook_snapshot_hyper_lookup",
        "orderbook_snapshot_hyper",
        ["exchange", "symbol", "time"],
    )
    op.create_index(
        "ix_sentiment_hyper_lookup",
        "sentiment_hyper",
        ["source", "symbol", "metric_name", "time"],
    )


def downgrade():
    # Drop indexes first, then tables (hypertable drop cascades chunks automatically)
    op.drop_index("ix_sentiment_hyper_lookup", "sentiment_hyper")
    op.drop_index("ix_orderbook_snapshot_hyper_lookup", "orderbook_snapshot_hyper")
    op.drop_index("ix_open_interest_hyper_lookup", "open_interest_hyper")
    op.drop_index("ix_funding_rate_hyper_lookup", "funding_rate_hyper")
    op.drop_index("ix_ohlcv_hyper_lookup", "ohlcv_hyper")

    op.drop_table("sentiment_hyper")
    op.drop_table("orderbook_snapshot_hyper")
    op.drop_table("open_interest_hyper")
    op.drop_table("funding_rate_hyper")
    op.drop_table("ohlcv_hyper")

    # Note: we intentionally do NOT drop the timescaledb extension on downgrade
    # because other objects may depend on it.
