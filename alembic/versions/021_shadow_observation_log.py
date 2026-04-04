"""021: RI-2A-2a — shadow_observation_log table.

Creates the shadow_observation_log table (append-only observation record).
No existing tables modified. FK: ZERO. UNIQUE: ZERO.

This table is NOT a business decision source.
DML contract: INSERT only (UPDATE/DELETE prohibited).

Revision ID: 021_shadow_observation_log
Revises: 020_stage2a_asset_metadata
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "021_shadow_observation_log"
down_revision: Union[str, None] = "020_stage2a_asset_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shadow_observation_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # 관찰 대상
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("asset_class", sa.String(16), nullable=False),
        sa.Column("asset_sector", sa.String(32), nullable=False),
        # Shadow 결과
        sa.Column("shadow_verdict", sa.String(32), nullable=False),
        sa.Column("shadow_screening_passed", sa.Boolean(), nullable=True),
        sa.Column("shadow_qualification_passed", sa.Boolean(), nullable=True),
        # 비교 결과
        sa.Column("comparison_verdict", sa.String(32), nullable=False),
        sa.Column("existing_screening_passed", sa.Boolean(), nullable=True),
        sa.Column("existing_qualification_passed", sa.Boolean(), nullable=True),
        # Reason-level
        sa.Column("reason_comparison_json", sa.Text(), nullable=True),
        # Read-through metadata
        sa.Column("readthrough_failure_code", sa.String(48), nullable=True),
        sa.Column("existing_screening_result_id", sa.String(64), nullable=True),
        sa.Column("existing_qualification_result_id", sa.String(64), nullable=True),
        # 재현성
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        # 시각
        sa.Column("shadow_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_shadow_obs_symbol", "shadow_observation_log", ["symbol"])
    op.create_index("ix_shadow_obs_created_at", "shadow_observation_log", ["created_at"])
    op.create_index(
        "ix_shadow_obs_verdict",
        "shadow_observation_log",
        ["comparison_verdict", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_shadow_obs_verdict", table_name="shadow_observation_log")
    op.drop_index("ix_shadow_obs_created_at", table_name="shadow_observation_log")
    op.drop_index("ix_shadow_obs_symbol", table_name="shadow_observation_log")
    op.drop_table("shadow_observation_log")
