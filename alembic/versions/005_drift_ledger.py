"""CR-048 Drift Ledger table (Runtime Immutability Zone)

Revision ID: 005_drift_ledger
Revises: 004_control_plane
Create Date: 2026-04-02

Tables:
  - drift_ledger: Minimal audit trail for bundle hash mismatches
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_drift_ledger"
down_revision: Union[str, None] = "004_control_plane"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drift_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bundle_type", sa.String(20), nullable=False),
        sa.Column("expected_hash", sa.String(64), nullable=False),
        sa.Column("observed_hash", sa.String(64), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("sm3_candidate", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("canonical_snapshot", sa.Text(), nullable=True),
    )
    op.create_index("ix_drift_ledger_bundle_type", "drift_ledger", ["bundle_type"])
    op.create_index("ix_drift_ledger_detected_at", "drift_ledger", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_drift_ledger_detected_at", table_name="drift_ledger")
    op.drop_index("ix_drift_ledger_bundle_type", table_name="drift_ledger")
    op.drop_table("drift_ledger")
