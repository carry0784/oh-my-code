"""020: CR-048 Stage 2A — asset metadata alignment.

Creates the symbol_status_audits table (append-only audit trail for
symbol status transitions).  No existing tables modified.

Stage 2A scope: static DDL only, no DML, no runtime hooking.

Revision ID: 020_stage2a_asset_metadata
Revises: 019_cr048_design_card
Create Date: 2026-04-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "020_stage2a_asset_metadata"
down_revision: Union[str, None] = "019_cr048_design_card"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "symbol_status_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol_id", sa.String(36), nullable=False, index=True),
        sa.Column("symbol", sa.String(40), nullable=False, index=True),
        sa.Column("from_status", sa.String(20), nullable=False),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reason_code", sa.String(60), nullable=True),
        sa.Column("reason_detail", sa.Text, nullable=True),
        sa.Column("triggered_by", sa.String(100), nullable=False),
        sa.Column("approval_level", sa.String(20), nullable=True),
        sa.Column("context", sa.Text, nullable=True),
        sa.Column(
            "transitioned_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("symbol_status_audits")
