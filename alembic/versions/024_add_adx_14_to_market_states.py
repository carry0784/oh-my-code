"""024: CR-048 Follow-Up 2A P1 — add adx_14 to market_states.

Adds ADX(14) indicator column to existing market_states table.
Nullable, no default. Existing rows get NULL automatically.

Revision ID: 024_add_adx_14_to_market_states
Revises: 023_shadow_obs_is_archived
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "024_add_adx_14_to_market_states"
down_revision: Union[str, None] = "023_shadow_obs_is_archived"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "market_states",
        sa.Column("adx_14", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_states", "adx_14")
