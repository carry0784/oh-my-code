"""CR-046 paper trading tables (sessions, receipts, promotions)

Revision ID: 003_cr046_paper
Revises: 117c4dc320f5
Create Date: 2026-04-01

Tables:
  - paper_trading_sessions: Session state with optimistic lock (version column)
  - paper_trading_receipts: Append-only bar receipts, (session_id, bar_ts) unique
  - promotion_receipts: Append-only promotion audit trail, approved_by != '' enforced
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_cr046_paper"
down_revision: Union[str, None] = "117c4dc320f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- paper_trading_sessions ---
    op.create_table(
        "paper_trading_sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("daily_pnl", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("weekly_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consecutive_losing_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_halted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("halt_reason", sa.Text, nullable=True),
        sa.Column("open_position", postgresql.JSONB, nullable=True),
        sa.Column("last_daily_reset_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_weekly_reset_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # --- paper_trading_receipts ---
    op.create_table(
        "paper_trading_receipts",
        sa.Column("receipt_id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("bar_ts", sa.BigInteger, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("decision_source", sa.String(50), nullable=False),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("data", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_session_bar",
        "paper_trading_receipts",
        ["session_id", "bar_ts"],
    )

    # --- promotion_receipts ---
    op.create_table(
        "promotion_receipts",
        sa.Column("receipt_id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("promotion_target", sa.String(50), nullable=False),
        sa.Column("promotion_basis", sa.Text, nullable=False),
        sa.Column("approved_by", sa.String(50), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("linked_receipt_ids", postgresql.JSONB, nullable=False),
        sa.Column("risk_notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_check_constraint(
        "ck_approved_by_not_empty",
        "promotion_receipts",
        "approved_by != ''",
    )


def downgrade() -> None:
    op.drop_table("promotion_receipts")
    op.drop_table("paper_trading_receipts")
    op.drop_table("paper_trading_sessions")
