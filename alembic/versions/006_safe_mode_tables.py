"""CR-048 Safe Mode tables (Phase 9 minimal)

Revision ID: 006_safe_mode
Revises: 005_drift_ledger
Create Date: 2026-04-02

Tables:
  - safe_mode_status: Current system safe mode state (singleton row)
  - safe_mode_transitions: Append-only audit trail for state transitions
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_safe_mode"
down_revision: Union[str, None] = "005_drift_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── safe_mode_status (singleton) ─────────────────────────────────
    op.create_table(
        "safe_mode_status",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("current_state", sa.String(30), nullable=False, server_default="normal"),
        sa.Column("previous_state", sa.String(30), nullable=True),
        sa.Column("entered_at", sa.DateTime(), nullable=True),
        sa.Column("entered_reason_code", sa.String(50), nullable=True),
        sa.Column("source_event_id", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("release_reason", sa.String(200), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # ── safe_mode_transitions (append-only audit) ────────────────────
    op.create_table(
        "safe_mode_transitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("from_state", sa.String(30), nullable=False),
        sa.Column("to_state", sa.String(30), nullable=False),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("source_event_id", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_safe_mode_transitions_created_at",
        "safe_mode_transitions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_safe_mode_transitions_created_at", table_name="safe_mode_transitions")
    op.drop_table("safe_mode_transitions")
    op.drop_table("safe_mode_status")
