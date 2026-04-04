"""019: CR-048 design card alignment — add missing columns to control plane tables.

Aligns the 4 control-plane models (indicators, feature_packs, strategies,
promotion_events) with CR-048 Phase 1 design cards v1.0.

Changes:
  indicators:        +category, +asset_classes, +timeframes
  feature_packs:     +description, +asset_classes, +timeframes, +warmup_bars, +champion_of
  strategies:        (status server_default updated conceptually; enum values now UPPERCASE in ORM)
  promotion_events:  +evidence, +approved_by

Note: Enum value case migration (lowercase→UPPERCASE) is handled at ORM level
via values_callable. Existing DB rows with lowercase values are valid — new
rows will be written in UPPERCASE. A future data-migration can normalise
historical rows if needed.

Revision ID: 019_cr048_design_card
Revises: 018_enum_contract_unification
Create Date: 2026-04-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "019_cr048_design_card"
down_revision: Union[str, None] = "018_enum_contract_unification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── indicators: +category, +asset_classes, +timeframes ────────────
    op.add_column("indicators", sa.Column("category", sa.String(30), nullable=True))
    op.add_column("indicators", sa.Column("asset_classes", sa.Text(), nullable=True))
    op.add_column("indicators", sa.Column("timeframes", sa.Text(), nullable=True))
    op.create_index("ix_indicators_category", "indicators", ["category"])

    # ── feature_packs: +description, +asset_classes, +timeframes,
    #                    +warmup_bars, +champion_of ────────────────────
    op.add_column("feature_packs", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("feature_packs", sa.Column("asset_classes", sa.Text(), nullable=True))
    op.add_column("feature_packs", sa.Column("timeframes", sa.Text(), nullable=True))
    op.add_column(
        "feature_packs",
        sa.Column("warmup_bars", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("feature_packs", sa.Column("champion_of", sa.String(36), nullable=True))

    # ── promotion_events: +evidence, +approved_by ─────────────────────
    op.add_column("promotion_events", sa.Column("evidence", sa.Text(), nullable=True))
    op.add_column("promotion_events", sa.Column("approved_by", sa.String(100), nullable=True))


def downgrade() -> None:
    # ── promotion_events ──────────────────────────────────────────────
    op.drop_column("promotion_events", "approved_by")
    op.drop_column("promotion_events", "evidence")

    # ── feature_packs ─────────────────────────────────────────────────
    op.drop_column("feature_packs", "champion_of")
    op.drop_column("feature_packs", "warmup_bars")
    op.drop_column("feature_packs", "timeframes")
    op.drop_column("feature_packs", "asset_classes")
    op.drop_column("feature_packs", "description")

    # ── indicators ────────────────────────────────────────────────────
    op.drop_index("ix_indicators_category", table_name="indicators")
    op.drop_column("indicators", "timeframes")
    op.drop_column("indicators", "asset_classes")
    op.drop_column("indicators", "category")
