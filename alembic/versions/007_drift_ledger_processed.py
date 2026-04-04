"""CR-048 Add processed columns to drift_ledger (Phase 9 hardening)

Revision ID: 007_drift_processed
Revises: 006_safe_mode
Create Date: 2026-04-02

Adds:
  - drift_ledger.processed (bool, default false)
  - drift_ledger.processed_at (datetime, nullable)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_drift_processed"
down_revision: Union[str, None] = "006_safe_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "drift_ledger",
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "drift_ledger",
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_drift_ledger_processed", "drift_ledger", ["processed"])


def downgrade() -> None:
    op.drop_index("ix_drift_ledger_processed", table_name="drift_ledger")
    op.drop_column("drift_ledger", "processed_at")
    op.drop_column("drift_ledger", "processed")
