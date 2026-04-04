"""CR-048 Phase 4B: Paper Shadow + Promotion Gate tables

Revision ID: 010_paper_shadow
Revises: 009_qualification
Create Date: 2026-04-02

Adds:
  - paper_observations table (append-only)
  - promotion_decisions table (append-only)
  - symbols.promotion_eligibility_status column
  - qualification_results.failed_checks column
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010_paper_shadow"
down_revision: Union[str, None] = "009_qualification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── symbols.promotion_eligibility_status ─────────────────────────
    op.add_column(
        "symbols",
        sa.Column(
            "promotion_eligibility_status",
            sa.String(30),
            nullable=False,
            server_default="unchecked",
        ),
    )

    # ── qualification_results.failed_checks ──────────────────────────
    op.add_column(
        "qualification_results",
        sa.Column("failed_checks", sa.Text(), nullable=True),
    )

    # ── paper_observations table ─────────────────────────────────────
    op.create_table(
        "paper_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("metrics_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "observation_status",
            sa.Enum("recorded", "skipped_safe_mode", "skipped_drift", name="observationstatus"),
            nullable=False,
            server_default="recorded",
        ),
        sa.Column("source_qualification_result_id", sa.String(36), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_paper_observations_strategy_id",
        "paper_observations",
        ["strategy_id"],
    )
    op.create_index(
        "ix_paper_observations_symbol",
        "paper_observations",
        ["symbol"],
    )

    # ── promotion_decisions table ────────────────────────────────────
    op.create_table(
        "promotion_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "unchecked",
                "eligible_for_paper",
                "paper_hold",
                "paper_pass",
                "paper_fail",
                "quarantine_candidate",
                name="promotioneligibility",
            ),
            nullable=False,
            server_default="unchecked",
        ),
        sa.Column("previous_decision", sa.String(40), nullable=True),
        sa.Column("reason", sa.String(100), nullable=True),
        sa.Column("eligibility_checks", sa.Text(), nullable=True),
        sa.Column("source_observation_id", sa.String(36), nullable=True),
        sa.Column("suppressed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("decided_by", sa.String(100), nullable=False, server_default="system"),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_promotion_decisions_strategy_id",
        "promotion_decisions",
        ["strategy_id"],
    )
    op.create_index(
        "ix_promotion_decisions_symbol",
        "promotion_decisions",
        ["symbol"],
    )


def downgrade() -> None:
    op.drop_index("ix_promotion_decisions_symbol", table_name="promotion_decisions")
    op.drop_index("ix_promotion_decisions_strategy_id", table_name="promotion_decisions")
    op.drop_table("promotion_decisions")
    op.execute("DROP TYPE IF EXISTS promotioneligibility")

    op.drop_index("ix_paper_observations_symbol", table_name="paper_observations")
    op.drop_index("ix_paper_observations_strategy_id", table_name="paper_observations")
    op.drop_table("paper_observations")
    op.execute("DROP TYPE IF EXISTS observationstatus")

    op.drop_column("qualification_results", "failed_checks")
    op.drop_column("symbols", "promotion_eligibility_status")
