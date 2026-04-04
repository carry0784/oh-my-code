"""023: RI-2A-2b — add is_archived to shadow_observation_log.

Adds retention support column. Default False. No data loss.
Existing rows get is_archived=False automatically.

Purge execution is NOT implemented. This is planner support only.

Revision ID: 023_shadow_obs_is_archived
Revises: 022_shadow_write_receipt
Create Date: 2026-04-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "023_shadow_obs_is_archived"
down_revision: Union[str, None] = "022_shadow_write_receipt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shadow_observation_log",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("shadow_observation_log", "is_archived")
