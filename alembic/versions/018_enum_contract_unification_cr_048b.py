"""018: Enum contract unification (CR-048B)

Fixes enum value mismatches across Signal, Position, and MarketState models.

1. Signal: SQLEnum was missing values_callable → sent .name (UPPERCASE) instead
   of .value (lowercase). Fixed in ORM; no DB change needed (DB already lowercase).

2. Position: Same issue as Signal. Fixed in ORM; no DB change needed.

3. MarketState.regime: DB enum 'marketregime' was created with UPPERCASE labels
   (TRENDING_UP, etc.) by migration 017, but Python enum values and all
   application code use lowercase. This migration converts DB enum labels
   to lowercase and updates existing data.

Revision ID: 018_enum_contract_unification
Revises: 66dd1bc7be70
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "018_enum_contract_unification"
down_revision: Union[str, None] = "66dd1bc7be70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# MarketRegime enum label mapping: UPPERCASE → lowercase
_REGIME_RENAME = [
    ("TRENDING_UP", "trending_up"),
    ("TRENDING_DOWN", "trending_down"),
    ("RANGING", "ranging"),
    ("HIGH_VOLATILITY", "high_volatility"),
    ("CRISIS", "crisis"),
    ("UNKNOWN", "unknown"),
]


def upgrade() -> None:
    # Rename each marketregime enum label from UPPERCASE to lowercase.
    # PostgreSQL ALTER TYPE ... RENAME VALUE is available since PG 10.
    for old_label, new_label in _REGIME_RENAME:
        op.execute(f"ALTER TYPE marketregime RENAME VALUE '{old_label}' TO '{new_label}'")


def downgrade() -> None:
    # Reverse: lowercase → UPPERCASE
    for old_label, new_label in _REGIME_RENAME:
        op.execute(f"ALTER TYPE marketregime RENAME VALUE '{new_label}' TO '{old_label}'")
