"""CR-048 Phase 5a-C: add consecutive_high_latency to paper_trading_sessions.

BTC guarded paper lane requires tracking consecutive high-latency
executions (>10s). 3 consecutive triggers lane pause (K_LATENCY).

Revision ID: 025_btc_latency
Revises: 024_add_adx_14
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa

revision = "025_btc_latency"
down_revision = "024_add_adx_14_to_market_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_trading_sessions",
        sa.Column(
            "consecutive_high_latency",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("paper_trading_sessions", "consecutive_high_latency")
