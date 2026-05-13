"""029: market_observation_receipts table — F5c DB persistence.

Creates the append-only `market_observation_receipts` table for Market
State API observation receipts. Additive only: no FK, no data backfill,
no existing-table modification.

Revision ID: 029_market_observation_receipt
Revises: 028_observation_chain
Create Date: 2026-05-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "029_market_observation_receipt"
down_revision: Union[str, None] = "028_observation_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_observation_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.String(64), nullable=False, unique=True),
        sa.Column("endpoint", sa.String(16), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "audit_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source_status", sa.String(24), nullable=False),
        sa.Column("validation_status", sa.String(24), nullable=False),
        sa.Column("freshness_status", sa.String(16), nullable=False),
        sa.Column("error_type", sa.String(64), nullable=True),
        sa.Column(
            "response_shape_version",
            sa.String(8),
            nullable=False,
            server_default=sa.text("'v1'"),
        ),
        sa.Column(
            "admissible_for_decision",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("rollback_note", sa.String(512), nullable=False),
        sa.Column("evidence_bundle_id", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_obs_endpoint",
        "market_observation_receipts",
        ["endpoint"],
        unique=False,
    )
    op.create_index(
        "ix_market_obs_symbol",
        "market_observation_receipts",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        "ix_market_obs_audit_created_at",
        "market_observation_receipts",
        ["audit_created_at"],
        unique=False,
    )
    op.create_index(
        "ix_market_obs_admissible_at",
        "market_observation_receipts",
        ["admissible_for_decision", "audit_created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_obs_admissible_at", table_name="market_observation_receipts")
    op.drop_index("ix_market_obs_audit_created_at", table_name="market_observation_receipts")
    op.drop_index("ix_market_obs_symbol", table_name="market_observation_receipts")
    op.drop_index("ix_market_obs_endpoint", table_name="market_observation_receipts")
    op.drop_table("market_observation_receipts")
