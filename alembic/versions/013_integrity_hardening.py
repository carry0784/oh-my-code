"""013: Integrity hardening — paper_pass_at + receipt fingerprints.

Phase 5B of CR-048.

Revision ID: 013_integrity_hardening
Revises: 012_runtime_loader
"""

from alembic import op
import sqlalchemy as sa

revision = "013_integrity_hardening"
down_revision = "012_runtime_loader"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add paper_pass_at to symbols
    op.add_column(
        "symbols",
        sa.Column("paper_pass_at", sa.DateTime(), nullable=True),
    )

    # Add fingerprint columns to load_decision_receipts
    op.add_column(
        "load_decision_receipts",
        sa.Column("strategy_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "load_decision_receipts",
        sa.Column("fp_fingerprint", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("load_decision_receipts", "fp_fingerprint")
    op.drop_column("load_decision_receipts", "strategy_fingerprint")
    op.drop_column("symbols", "paper_pass_at")
