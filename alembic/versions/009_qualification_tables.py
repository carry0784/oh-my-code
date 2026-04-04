"""CR-048 Phase 4A: Qualification tables + symbol qualification_status

Revision ID: 009_qualification
Revises: 008_asset_tables
Create Date: 2026-04-02

Adds:
  - qualification_results table (append-only)
  - symbols.qualification_status column
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009_qualification"
down_revision: Union[str, None] = "008_asset_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── symbols.qualification_status ─────────────────────────────────
    op.add_column(
        "symbols",
        sa.Column(
            "qualification_status",
            sa.String(20),
            nullable=False,
            server_default="unchecked",
        ),
    )

    # ── qualification_results table ──────────────────────────────────
    op.create_table(
        "qualification_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(64), nullable=True),
        sa.Column("bars_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("date_range_start", sa.DateTime(), nullable=True),
        sa.Column("date_range_end", sa.DateTime(), nullable=True),
        sa.Column("check_data_compat", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("check_warmup", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("check_leakage", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("check_data_quality", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("check_min_bars", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("check_performance", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("check_cost_sanity", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("all_passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "qualification_status",
            sa.Enum("unchecked", "pass", "fail", name="qualificationstatus"),
            nullable=False,
            server_default="unchecked",
        ),
        sa.Column("disqualify_reason", sa.String(60), nullable=True),
        sa.Column("metrics_snapshot", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_qualification_results_strategy_id", "qualification_results", ["strategy_id"]
    )
    op.create_index("ix_qualification_results_symbol", "qualification_results", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_qualification_results_symbol", table_name="qualification_results")
    op.drop_index("ix_qualification_results_strategy_id", table_name="qualification_results")
    op.drop_table("qualification_results")
    op.execute("DROP TYPE IF EXISTS qualificationstatus")
    op.drop_column("symbols", "qualification_status")
