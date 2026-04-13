"""026: ohlcv_history table — Phase A backtest data plane

CR: Phase A (400-Day Backtest Data Plane)
Purpose: Persistent OHLCV candle storage for deterministic backtest replay.
         Backtest-only write path. No runtime/execution coupling.

Table: ohlcv_history
  - One row = one canonical candle (exchange + symbol + timeframe + open_time)
  - Event metadata columns (event_week_flag, macro_event_type, high_volatility_flag)
    for future event_week_resilience_score computation.
  - Unique constraint prevents duplicate candle ingestion.

Scope: Data infrastructure only. No runtime table changes.
"""

from alembic import op
import sqlalchemy as sa

revision = "026_ohlcv_history"
down_revision = "025_btc_latency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ohlcv_history",
        sa.Column("id", sa.String(36), primary_key=True),
        # Identity
        sa.Column("exchange", sa.String(50), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("timeframe", sa.String(10), nullable=False, server_default="1h"),
        # OHLCV
        sa.Column("open_time", sa.BigInteger(), nullable=False, index=True),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        # Event metadata
        sa.Column("event_week_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("macro_event_type", sa.String(50), nullable=True),
        sa.Column("high_volatility_flag", sa.Boolean(), nullable=False, server_default="false"),
        # Timestamps
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
        # Constraints
        sa.UniqueConstraint(
            "exchange",
            "symbol",
            "timeframe",
            "open_time",
            name="uq_ohlcv_canonical_slot",
        ),
    )
    op.create_index(
        "ix_ohlcv_lookup",
        "ohlcv_history",
        ["exchange", "symbol", "timeframe", "open_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_ohlcv_lookup", table_name="ohlcv_history")
    op.drop_table("ohlcv_history")
