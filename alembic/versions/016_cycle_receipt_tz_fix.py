"""016: cycle_receipt timestamps timezone-aware.

Fix asyncpg offset-naive vs offset-aware datetime mismatch.
Convert started_at and completed_at from DateTime to DateTime(timezone=True).
"""

from alembic import op
import sqlalchemy as sa

revision = "016_cycle_receipt_tz_fix"
down_revision = "015_cycle_receipt_hardening"
branch_labels = None
depends_on = None


def upgrade():
    # ALTER COLUMN ... TYPE TIMESTAMPTZ preserves existing data
    op.alter_column(
        "cycle_receipts",
        "started_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=False,
    )
    op.alter_column(
        "cycle_receipts",
        "completed_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "cycle_receipts",
        "started_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "cycle_receipts",
        "completed_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
