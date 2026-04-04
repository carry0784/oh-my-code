"""012: Runtime Loader tables — load_decision_receipts.

Phase 5A of CR-048.

Revision ID: 012_runtime_loader
Revises: 011_paper_evaluation
"""

from alembic import op
import sqlalchemy as sa

revision = "012_runtime_loader"
down_revision = "011_paper_evaluation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "load_decision_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), index=True, nullable=False),
        sa.Column("symbol_id", sa.String(36), index=True, nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("primary_reason", sa.String(60), nullable=True),
        sa.Column("failed_checks", sa.Text(), nullable=True),
        sa.Column("status_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("load_decision_receipts")
