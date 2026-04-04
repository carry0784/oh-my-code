"""CR-048 Phase 2: Asset Registry tables (symbols + screening_results)

Revision ID: 008_asset_tables
Revises: 007_drift_processed
Create Date: 2026-04-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_asset_tables"
down_revision: Union[str, None] = "007_drift_processed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── symbols table ────────────────────────────────────────────────
    op.create_table(
        "symbols",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "asset_class",
            sa.Enum("crypto", "us_stock", "kr_stock", name="assetclass"),
            nullable=False,
        ),
        sa.Column(
            "sector",
            sa.Enum(
                "layer1",
                "defi",
                "ai",
                "infra",
                "meme",
                "gamefi",
                "low_liquidity_new_token",
                "tech",
                "healthcare",
                "energy",
                "finance",
                "high_valuation_pure_sw",
                "weak_consumer_beta",
                "semiconductor",
                "it",
                "kr_finance",
                "automotive",
                "oil_sensitive",
                "low_liquidity_theme",
                name="assetsector",
            ),
            nullable=False,
        ),
        sa.Column(
            "theme",
            sa.Enum(
                "ai_semiconductor",
                "cloud",
                "ev",
                "renewable_energy",
                "defi_yield",
                "l1_scaling",
                "biotech",
                "none",
                name="assettheme",
            ),
            nullable=False,
            server_default="none",
        ),
        sa.Column("exchanges", sa.Text(), nullable=False),
        sa.Column("market_cap_usd", sa.Float(), nullable=True),
        sa.Column("avg_daily_volume", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("core", "watch", "excluded", name="symbolstatus"),
            nullable=False,
            server_default="watch",
        ),
        sa.Column("status_reason_code", sa.String(60), nullable=True),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("screening_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("regime_allow", sa.Text(), nullable=True),
        sa.Column("candidate_expire_at", sa.DateTime(), nullable=True),
        sa.Column("paper_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("live_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("override_by", sa.String(100), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("override_at", sa.DateTime(), nullable=True),
        sa.Column("broker_policy", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_symbols_symbol", "symbols", ["symbol"])
    op.create_index("ix_symbols_status", "symbols", ["status"])
    op.create_index("ix_symbols_asset_class", "symbols", ["asset_class"])

    # ── screening_results table ──────────────────────────────────────
    op.create_table(
        "screening_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol_id", sa.String(36), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("stage1_exclusion", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stage2_liquidity", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stage3_technical", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stage4_fundamental", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stage5_backtest", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("all_passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stage_reason_code", sa.String(60), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "resulting_status",
            sa.Enum("core", "watch", "excluded", name="symbolstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("screened_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_screening_results_symbol_id", "screening_results", ["symbol_id"])
    op.create_index("ix_screening_results_symbol", "screening_results", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_screening_results_symbol", table_name="screening_results")
    op.drop_index("ix_screening_results_symbol_id", table_name="screening_results")
    op.drop_table("screening_results")

    op.drop_index("ix_symbols_asset_class", table_name="symbols")
    op.drop_index("ix_symbols_status", table_name="symbols")
    op.drop_index("ix_symbols_symbol", table_name="symbols")
    op.drop_table("symbols")

    # Drop enums created by this migration
    op.execute("DROP TYPE IF EXISTS assetsector")
    op.execute("DROP TYPE IF EXISTS assettheme")
    op.execute("DROP TYPE IF EXISTS symbolstatus")
