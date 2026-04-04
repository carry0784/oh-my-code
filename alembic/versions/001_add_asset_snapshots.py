"""add asset_snapshots table

Revision ID: 001_asset_snapshots
Revises:
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_asset_snapshots"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("total_value", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_balance", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("snapshot_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_asset_snapshots_snapshot_at", "asset_snapshots", ["snapshot_at"])


def downgrade() -> None:
    op.drop_index("ix_asset_snapshots_snapshot_at", table_name="asset_snapshots")
    op.drop_table("asset_snapshots")
