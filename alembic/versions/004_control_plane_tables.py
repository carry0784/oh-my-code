"""CR-048 Control Plane tables (indicators, feature_packs, strategies, promotion_events)

Revision ID: 004_control_plane
Revises: 003_cr046_paper
Create Date: 2026-04-02

Tables:
  - indicators: Single technical indicator metadata and version
  - feature_packs: Indicator bundle used by strategies
  - strategies: Strategy metadata, market matrix, promotion status
  - promotion_events: Append-only state transition audit trail
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_control_plane"
down_revision: Union[str, None] = "003_cr046_paper"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── indicators ────────────────────────────────────────────────────
    op.create_table(
        "indicators",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_params", sa.Text(), nullable=True),
        sa.Column("output_fields", sa.Text(), nullable=True),
        sa.Column("warmup_bars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("compute_module", sa.String(200), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_indicators_name", "indicators", ["name"])
    op.create_index("ix_indicators_status", "indicators", ["status"])

    # ── feature_packs ─────────────────────────────────────────────────
    op.create_table(
        "feature_packs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("indicator_ids", sa.Text(), nullable=False),
        sa.Column("weights", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_feature_packs_name", "feature_packs", ["name"])

    # ── strategies ────────────────────────────────────────────────────
    op.create_table(
        "strategies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feature_pack_id", sa.String(36), nullable=False),
        sa.Column("compute_module", sa.String(200), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("asset_classes", sa.Text(), nullable=False),
        sa.Column("exchanges", sa.Text(), nullable=False),
        sa.Column("sectors", sa.Text(), nullable=True),
        sa.Column("timeframes", sa.Text(), nullable=False),
        sa.Column("regimes", sa.Text(), nullable=True),
        sa.Column("max_symbols", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("promoted_at", sa.DateTime(), nullable=True),
        sa.Column("promoted_by", sa.String(100), nullable=True),
        sa.Column("is_champion", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("champion_since", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_strategies_status", "strategies", ["status"])
    op.create_index("ix_strategies_feature_pack_id", "strategies", ["feature_pack_id"])

    # ── promotion_events ──────────────────────────────────────────────
    op.create_table(
        "promotion_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=False),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(100), nullable=False),
        sa.Column("approval_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_promotion_events_strategy_id", "promotion_events", ["strategy_id"])
    op.create_index("ix_promotion_events_created_at", "promotion_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_promotion_events_created_at", table_name="promotion_events")
    op.drop_index("ix_promotion_events_strategy_id", table_name="promotion_events")
    op.drop_table("promotion_events")

    op.drop_index("ix_strategies_feature_pack_id", table_name="strategies")
    op.drop_index("ix_strategies_status", table_name="strategies")
    op.drop_table("strategies")

    op.drop_index("ix_feature_packs_name", table_name="feature_packs")
    op.drop_table("feature_packs")

    op.drop_index("ix_indicators_status", table_name="indicators")
    op.drop_index("ix_indicators_name", table_name="indicators")
    op.drop_table("indicators")
