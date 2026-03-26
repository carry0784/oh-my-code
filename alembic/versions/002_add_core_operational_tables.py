"""add core operational tables (positions, trades, orders, signals)

Revision ID: 002_core_ops
Revises: 001_asset_snapshots
Create Date: 2026-03-24

Schema source-of-truth: app/models/*.py
- positions  → app/models/position.py
- trades     → app/models/trade.py
- orders     → app/models/order.py
- signals    → app/models/signal.py

Policy:
- No server_default — all defaults are ORM client-side
- Enum types created explicitly before tables, dropped after tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_core_ops"
down_revision: Union[str, None] = "001_asset_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Enum definitions — must match app/models exactly
# ---------------------------------------------------------------------------
# Enum definitions — used inline in create_table, SQLAlchemy manages CREATE TYPE
positionside_enum = sa.Enum("long", "short", name="positionside")
orderside_enum = sa.Enum("buy", "sell", name="orderside")
ordertype_enum = sa.Enum("market", "limit", "stop_loss", "take_profit", name="ordertype")
orderstatus_enum = sa.Enum(
    "pending", "submitted", "filled", "partially_filled", "cancelled", "rejected",
    name="orderstatus",
)
signaltype_enum = sa.Enum("long", "short", "close", name="signaltype")
signalstatus_enum = sa.Enum(
    "pending", "validated", "rejected", "executed", "expired",
    name="signalstatus",
)


def upgrade() -> None:
    # -- positions (app/models/position.py) --
    # Enum types are auto-created by SQLAlchemy when used in create_table
    op.create_table(
        "positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", positionside_enum, nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("leverage", sa.Float(), nullable=False),
        sa.Column("liquidation_price", sa.Float(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # -- trades (app/models/trade.py) --
    op.create_table(
        "trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("order_id", sa.String(36), nullable=False),
        sa.Column("exchange_trade_id", sa.String(100), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("fee_currency", sa.String(10), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # -- orders (app/models/order.py) --
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", orderside_enum, nullable=False),
        sa.Column("order_type", ordertype_enum, nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("status", orderstatus_enum, nullable=False),
        sa.Column("exchange_order_id", sa.String(100), nullable=True),
        sa.Column("filled_quantity", sa.Float(), nullable=False),
        sa.Column("average_price", sa.Float(), nullable=True),
        sa.Column("signal_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # -- signals (app/models/signal.py) --
    # Note: signal_metadata field uses name="metadata" → DB column is "metadata"
    op.create_table(
        "signals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("signal_type", signaltype_enum, nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", signalstatus_enum, nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("agent_analysis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    # -- Drop tables first --
    op.drop_table("signals")
    op.drop_table("orders")
    op.drop_table("trades")
    op.drop_table("positions")

    # -- Drop enum types after tables --
    signalstatus_enum.drop(op.get_bind(), checkfirst=True)
    signaltype_enum.drop(op.get_bind(), checkfirst=True)
    orderstatus_enum.drop(op.get_bind(), checkfirst=True)
    ordertype_enum.drop(op.get_bind(), checkfirst=True)
    orderside_enum.drop(op.get_bind(), checkfirst=True)
    positionside_enum.drop(op.get_bind(), checkfirst=True)
