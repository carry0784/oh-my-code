"""015: Cycle receipt hardening — add skip_reason_code + guard_snapshot_json.

Phase 6B-2 hardening of CR-048.

Revision ID: 015_cycle_receipt_hardening
Revises: 014_universe_runner
"""

from alembic import op
import sqlalchemy as sa

revision = "015_cycle_receipt_hardening"
down_revision = "014_universe_runner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cycle_receipts",
        sa.Column(
            "skip_reason_code",
            sa.String(40),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "cycle_receipts",
        sa.Column(
            "guard_snapshot_json",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("cycle_receipts", "guard_snapshot_json")
    op.drop_column("cycle_receipts", "skip_reason_code")
