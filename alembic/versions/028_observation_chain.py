"""028: Create observation_chain table for long-term time-series state tracking.

Revision ID: 028_observation_chain
Revises: 027_ppf_baseline_freeze
"""

from alembic import op
import sqlalchemy as sa

revision = "028_observation_chain"
down_revision = "027_ppf_baseline_freeze"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "observation_chain",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        # Observation identity
        sa.Column("observed_at", sa.DateTime, nullable=False),
        sa.Column("observation_type", sa.String(32), nullable=False, server_default="hourly"),
        # Market snapshot
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("close_price", sa.Float, nullable=True),
        sa.Column("regime_v1", sa.String(32), nullable=True),
        sa.Column("regime_v2", sa.String(32), nullable=True),
        sa.Column("realized_volatility", sa.Float, nullable=True),
        sa.Column("choppiness_index", sa.Float, nullable=True),
        # Strategy snapshot
        sa.Column("active_strategy", sa.String(64), nullable=True),
        sa.Column("signal_count_24h", sa.Integer, nullable=True),
        sa.Column("consensus_ratio_24h", sa.Float, nullable=True),
        # Infrastructure snapshot
        sa.Column("ohlcv_coverage_pct", sa.Float, nullable=True),
        sa.Column("shadow_task_healthy", sa.Boolean, nullable=True),
        sa.Column("ppf_baseline_active", sa.Boolean, nullable=True),
        # Novelty / anomaly
        sa.Column("novelty_detected", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("anomaly_flag", sa.String(64), nullable=True),
        # Metadata
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_index("ix_obs_chain_symbol_ts", "observation_chain", ["symbol", "observed_at"])
    op.create_index("ix_obs_chain_type", "observation_chain", ["observation_type"])
    op.create_index("ix_obs_chain_regime", "observation_chain", ["regime_v1", "regime_v2"])


def downgrade():
    op.drop_index("ix_obs_chain_regime", "observation_chain")
    op.drop_index("ix_obs_chain_type", "observation_chain")
    op.drop_index("ix_obs_chain_symbol_ts", "observation_chain")
    op.drop_table("observation_chain")
