"""014: Universe runner tables — cycle_receipts.

Phase 6A of CR-048.

Revision ID: 014_universe_runner
Revises: 013_integrity_hardening
"""

from alembic import op
import sqlalchemy as sa

revision = "014_universe_runner"
down_revision = "013_integrity_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cycle_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cycle_id", sa.String(60), nullable=False, index=True),
        sa.Column("universe_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strategies_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("signal_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("entries_json", sa.Text(), nullable=True),
        sa.Column("safe_mode_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("drift_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("cycle_receipts")
