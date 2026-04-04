"""022: RI-2B-1 — shadow_write_receipt table.

Creates the shadow_write_receipt table (append-only dry-run evidence).
No existing tables modified. FK: ZERO. UNIQUE: 2 (receipt_id, dedupe_key).

This table is NOT a business decision source.
DML contract: INSERT only (UPDATE/DELETE prohibited).
business_write_count = 0 always.

Revision ID: 022_shadow_write_receipt
Revises: 021_shadow_observation_log
Create Date: 2026-04-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "022_shadow_write_receipt"
down_revision: Union[str, None] = "021_shadow_observation_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shadow_write_receipt",
        # Identity
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.String(64), nullable=False, unique=True),
        sa.Column("dedupe_key", sa.String(128), nullable=False, unique=True),
        # Target
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("target_table", sa.String(48), nullable=False),
        sa.Column("target_field", sa.String(48), nullable=False),
        sa.Column("current_value", sa.String(128), nullable=True),
        sa.Column("intended_value", sa.String(128), nullable=False),
        sa.Column("would_change_summary", sa.String(256), nullable=False),
        # Reason
        sa.Column("transition_reason", sa.String(128), nullable=False),
        sa.Column("block_reason_code", sa.String(64), nullable=True),
        # Linkage
        sa.Column("shadow_observation_id", sa.Integer(), nullable=True),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        # Proof fields
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "business_write_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        # Verdict
        sa.Column("verdict", sa.String(32), nullable=False),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_swr_symbol", "shadow_write_receipt", ["symbol"])
    op.create_index("ix_swr_created_at", "shadow_write_receipt", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_swr_created_at", table_name="shadow_write_receipt")
    op.drop_index("ix_swr_symbol", table_name="shadow_write_receipt")
    op.drop_table("shadow_write_receipt")
