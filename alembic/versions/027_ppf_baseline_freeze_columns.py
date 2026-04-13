"""027: PPF tables + baseline freeze/seal lifecycle columns

CR: PPF Phase A → Phase B infrastructure
Purpose:
  1. Create ppf_novelty_events table (FP accumulation tracking)
  2. Create ppf_backtest_baselines table (Phase A baseline storage)
     with freeze/seal lifecycle columns already included

Scope: Two new tables. No existing table changes.
"""

from alembic import op
import sqlalchemy as sa

revision = "027_ppf_baseline_freeze"
down_revision = "026_ohlcv_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ppf_novelty_events ──────────────────────────────────────────
    op.create_table(
        "ppf_novelty_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("event_ts", sa.DateTime(), nullable=False),
        sa.Column("deny_reason_code", sa.String(64), nullable=False),
        sa.Column("raw_gate_decision", sa.Boolean(), nullable=False),
        sa.Column("gate_allowed", sa.Boolean(), nullable=False),
        sa.Column("manifest_name", sa.String(32), nullable=False),
        sa.Column("observation_window_bars", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("observation_window_closed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("bars_elapsed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("judgment", sa.String(16), nullable=True),
        sa.Column("judgment_ts", sa.DateTime(), nullable=True),
        sa.Column("judgment_reason", sa.Text(), nullable=True),
        sa.Column("close_price_at_event", sa.Float(), nullable=True),
        sa.Column("close_price_at_window_end", sa.Float(), nullable=True),
        sa.Column("task_result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ppf_novelty_symbol_ts", "ppf_novelty_events", ["symbol", "event_ts"])
    op.create_index("ix_ppf_novelty_judgment", "ppf_novelty_events", ["judgment"])
    op.create_index("ix_ppf_novelty_window_closed", "ppf_novelty_events", ["observation_window_closed"])

    # ── ppf_backtest_baselines (with freeze/seal columns) ───────────
    op.create_table(
        "ppf_backtest_baselines",
        sa.Column("id", sa.String(36), primary_key=True),
        # Run identification
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False, server_default="1h"),
        # PPF config fingerprint
        sa.Column("ppf_params_hash", sa.String(64), nullable=False),
        # Aggregated metrics
        sa.Column("total_bars", sa.Integer(), nullable=False),
        sa.Column("evaluated_bars", sa.Integer(), nullable=False),
        sa.Column("deny_rate", sa.Float(), nullable=False),
        sa.Column("novelty_rate", sa.Float(), nullable=False),
        sa.Column("novelty_count", sa.Integer(), nullable=False),
        sa.Column("fpr", sa.Float(), nullable=False),
        sa.Column("allow_count", sa.Integer(), nullable=False),
        sa.Column("deny_count", sa.Integer(), nullable=False),
        # Distribution snapshots (JSON)
        sa.Column("deny_reason_distribution", sa.Text(), nullable=True),
        sa.Column("state_distribution", sa.Text(), nullable=True),
        # Full result blob
        sa.Column("result_json", sa.Text(), nullable=False),
        # Freeze/Seal lifecycle
        sa.Column("frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("frozen_at", sa.DateTime(), nullable=True),
        sa.Column("frozen_by", sa.String(100), nullable=True),
        sa.Column("seal_hash", sa.String(64), nullable=True),
        sa.Column("preflight_hash", sa.String(64), nullable=True),
        sa.Column("phase_b_started", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("phase_b_started_at", sa.DateTime(), nullable=True),
        sa.Column("invalidated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("invalidated_reason", sa.String(500), nullable=True),
        # Metadata
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ppf_baseline_symbol_exchange_tf", "ppf_backtest_baselines", ["symbol", "exchange", "timeframe"])
    op.create_index("ix_ppf_baseline_params_hash", "ppf_backtest_baselines", ["ppf_params_hash"])


def downgrade() -> None:
    op.drop_table("ppf_backtest_baselines")
    op.drop_table("ppf_novelty_events")
