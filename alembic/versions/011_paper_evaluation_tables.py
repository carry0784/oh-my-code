"""CR-048 Phase 4C: Paper Evaluation tables + model updates

Revision ID: 011_paper_evaluation
Revises: 010_paper_shadow
Create Date: 2026-04-02

Adds:
  - paper_evaluation_records table (append-only)
  - symbols.paper_evaluation_status column
  - paper_observations.observation_window_fingerprint column
  - promotion_decisions.blocked_checks column
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011_paper_evaluation"
down_revision: Union[str, None] = "010_paper_shadow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── symbols.paper_evaluation_status ──────────────────────────────
    op.add_column(
        "symbols",
        sa.Column(
            "paper_evaluation_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
    )

    # ── paper_observations.observation_window_fingerprint ────────────
    op.add_column(
        "paper_observations",
        sa.Column("observation_window_fingerprint", sa.String(64), nullable=True),
    )

    # ── promotion_decisions.blocked_checks ──────────────────────────
    op.add_column(
        "promotion_decisions",
        sa.Column("blocked_checks", sa.Text(), nullable=True),
    )

    # ── paper_evaluation_records table ──────────────────────────────
    op.create_table(
        "paper_evaluation_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expected_observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observation_window_fingerprint", sa.String(64), nullable=True),
        sa.Column("cumulative_return_pct", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column("avg_turnover_annual", sa.Float(), nullable=True),
        sa.Column("avg_slippage_pct", sa.Float(), nullable=True),
        sa.Column("rule_min_observations", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "rule_cumulative_performance", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("rule_max_drawdown", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rule_turnover", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rule_slippage", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rule_completeness", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("all_passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("decision", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("primary_reason", sa.String(60), nullable=True),
        sa.Column("failed_rules", sa.Text(), nullable=True),
        sa.Column("metrics_summary", sa.Text(), nullable=True),
        sa.Column("source_qualification_result_id", sa.String(36), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_paper_evaluation_records_strategy_id",
        "paper_evaluation_records",
        ["strategy_id"],
    )
    op.create_index(
        "ix_paper_evaluation_records_symbol",
        "paper_evaluation_records",
        ["symbol"],
    )


def downgrade() -> None:
    op.drop_index("ix_paper_evaluation_records_symbol", table_name="paper_evaluation_records")
    op.drop_index("ix_paper_evaluation_records_strategy_id", table_name="paper_evaluation_records")
    op.drop_table("paper_evaluation_records")
    op.drop_column("promotion_decisions", "blocked_checks")
    op.drop_column("paper_observations", "observation_window_fingerprint")
    op.drop_column("symbols", "paper_evaluation_status")
