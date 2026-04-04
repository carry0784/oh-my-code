"""017: market_states table (CR-038)

Add market_states table for persisting market state snapshots
(price, indicators, sentiment, on-chain, microstructure, regime).

Revision ID: 66dd1bc7be70
Revises: 016_cycle_receipt_tz_fix
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "66dd1bc7be70"
down_revision: Union[str, None] = "016_cycle_receipt_tz_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exchange", sa.String(length=50), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("bid", sa.Float(), nullable=True),
        sa.Column("ask", sa.Float(), nullable=True),
        sa.Column("spread_pct", sa.Float(), nullable=True),
        sa.Column("volume_24h", sa.Float(), nullable=True),
        sa.Column("rsi_14", sa.Float(), nullable=True),
        sa.Column("macd_line", sa.Float(), nullable=True),
        sa.Column("macd_signal", sa.Float(), nullable=True),
        sa.Column("macd_histogram", sa.Float(), nullable=True),
        sa.Column("bb_upper", sa.Float(), nullable=True),
        sa.Column("bb_middle", sa.Float(), nullable=True),
        sa.Column("bb_lower", sa.Float(), nullable=True),
        sa.Column("atr_14", sa.Float(), nullable=True),
        sa.Column("obv", sa.Float(), nullable=True),
        sa.Column("sma_20", sa.Float(), nullable=True),
        sa.Column("sma_50", sa.Float(), nullable=True),
        sa.Column("sma_200", sa.Float(), nullable=True),
        sa.Column("ema_12", sa.Float(), nullable=True),
        sa.Column("ema_26", sa.Float(), nullable=True),
        sa.Column("fear_greed_index", sa.Integer(), nullable=True),
        sa.Column("fear_greed_label", sa.String(length=20), nullable=True),
        sa.Column("hash_rate", sa.Float(), nullable=True),
        sa.Column("difficulty", sa.Float(), nullable=True),
        sa.Column("tx_count_24h", sa.Integer(), nullable=True),
        sa.Column("mempool_size", sa.Integer(), nullable=True),
        sa.Column("mempool_fee_fast", sa.Float(), nullable=True),
        sa.Column("mempool_fee_medium", sa.Float(), nullable=True),
        sa.Column("btc_dominance", sa.Float(), nullable=True),
        sa.Column("total_market_cap_usd", sa.Float(), nullable=True),
        sa.Column("funding_rate", sa.Float(), nullable=True),
        sa.Column("open_interest", sa.Float(), nullable=True),
        sa.Column(
            "regime",
            sa.Enum(
                "TRENDING_UP",
                "TRENDING_DOWN",
                "RANGING",
                "HIGH_VOLATILITY",
                "CRISIS",
                "UNKNOWN",
                name="marketregime",
            ),
            nullable=False,
        ),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_market_states_exchange"), "market_states", ["exchange"], unique=False)
    op.create_index(
        op.f("ix_market_states_snapshot_at"), "market_states", ["snapshot_at"], unique=False
    )
    op.create_index(op.f("ix_market_states_symbol"), "market_states", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_market_states_symbol"), table_name="market_states")
    op.drop_index(op.f("ix_market_states_snapshot_at"), table_name="market_states")
    op.drop_index(op.f("ix_market_states_exchange"), table_name="market_states")
    op.drop_table("market_states")
