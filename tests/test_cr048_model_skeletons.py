"""
CR-048 Model Skeleton Tests — L3 (limited) model verification.

Tests verify that the 4 control-plane models align with CR-048 design cards:
1. Enum values match design documents (UPPERCASE)
2. Required columns/fields exist
3. Default values and nullability are correct
4. Cross-model consistency (PromotionStatus states match design card)

All tests are pure unit tests — no DB session, no I/O.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

# ═══════════════════════════════════════════════════════════════════════
# Model imports
# ═══════════════════════════════════════════════════════════════════════

from app.models.indicator_registry import (
    Indicator,
    IndicatorCategory,
    IndicatorStatus,
)
from app.models.feature_pack import (
    FeaturePack,
    FeaturePackStatus,
)
from app.models.strategy_registry import (
    Strategy,
    AssetClass,
    PromotionStatus,
)
from app.models.promotion_state import PromotionEvent


# ═══════════════════════════════════════════════════════════════════════
# Design card constants (mirrors of test_cr048_design_contracts.py)
# ═══════════════════════════════════════════════════════════════════════

PROMOTION_STATES_10 = frozenset(
    {
        "DRAFT",
        "REGISTERED",
        "BACKTEST_PASS",
        "BACKTEST_FAIL",
        "PAPER_PASS",
        "QUARANTINE",
        "GUARDED_LIVE",
        "LIVE",
        "RETIRED",
        "BLOCKED",
    }
)

INDICATOR_CATEGORIES_5 = frozenset(
    {
        "MOMENTUM",
        "TREND",
        "VOLATILITY",
        "VOLUME",
        "OSCILLATOR",
    }
)

ASSET_CLASSES_3 = frozenset({"CRYPTO", "US_STOCK", "KR_STOCK"})


# ═══════════════════════════════════════════════════════════════════════
# 1. Indicator Model
# ═══════════════════════════════════════════════════════════════════════


class TestIndicatorModel:
    """Verify Indicator model aligns with design_indicator_registry.md v1.0."""

    def test_tablename(self):
        assert Indicator.__tablename__ == "indicators"

    def test_category_enum_values(self):
        values = {e.value for e in IndicatorCategory}
        assert values == INDICATOR_CATEGORIES_5

    def test_status_enum_values_uppercase(self):
        values = {e.value for e in IndicatorStatus}
        assert values == {"ACTIVE", "DEPRECATED", "BLOCKED"}
        # Verify UPPERCASE (not lowercase)
        for e in IndicatorStatus:
            assert e.value == e.value.upper()

    def test_has_category_column(self):
        cols = {c.name for c in Indicator.__table__.columns}
        assert "category" in cols

    def test_has_asset_classes_column(self):
        cols = {c.name for c in Indicator.__table__.columns}
        assert "asset_classes" in cols

    def test_has_timeframes_column(self):
        cols = {c.name for c in Indicator.__table__.columns}
        assert "timeframes" in cols

    def test_required_columns_present(self):
        cols = {c.name for c in Indicator.__table__.columns}
        required = {
            "id",
            "name",
            "version",
            "description",
            "category",
            "input_params",
            "output_fields",
            "asset_classes",
            "timeframes",
            "warmup_bars",
            "compute_module",
            "checksum",
            "status",
            "created_at",
            "updated_at",
        }
        assert required.issubset(cols)

    def test_category_nullable(self):
        col = Indicator.__table__.c.category
        assert col.nullable is True

    def test_name_unique(self):
        col = Indicator.__table__.c.name
        assert col.unique is True


# ═══════════════════════════════════════════════════════════════════════
# 2. Feature Pack Model
# ═══════════════════════════════════════════════════════════════════════


class TestFeaturePackModel:
    """Verify FeaturePack model aligns with design_feature_pack.md v1.0."""

    def test_tablename(self):
        assert FeaturePack.__tablename__ == "feature_packs"

    def test_status_enum_values_uppercase(self):
        values = {e.value for e in FeaturePackStatus}
        assert values == {"ACTIVE", "CHALLENGER", "DEPRECATED", "BLOCKED"}
        for e in FeaturePackStatus:
            assert e.value == e.value.upper()

    def test_has_champion_challenger_support(self):
        """FeaturePackStatus must include CHALLENGER for Champion/Challenger comparison."""
        assert "CHALLENGER" in {e.value for e in FeaturePackStatus}

    def test_has_description_column(self):
        cols = {c.name for c in FeaturePack.__table__.columns}
        assert "description" in cols

    def test_has_asset_classes_column(self):
        cols = {c.name for c in FeaturePack.__table__.columns}
        assert "asset_classes" in cols

    def test_has_timeframes_column(self):
        cols = {c.name for c in FeaturePack.__table__.columns}
        assert "timeframes" in cols

    def test_has_warmup_bars_column(self):
        cols = {c.name for c in FeaturePack.__table__.columns}
        assert "warmup_bars" in cols

    def test_has_champion_of_column(self):
        cols = {c.name for c in FeaturePack.__table__.columns}
        assert "champion_of" in cols

    def test_required_columns_present(self):
        cols = {c.name for c in FeaturePack.__table__.columns}
        required = {
            "id",
            "name",
            "version",
            "description",
            "indicator_ids",
            "weights",
            "asset_classes",
            "timeframes",
            "warmup_bars",
            "champion_of",
            "checksum",
            "status",
            "created_at",
            "updated_at",
        }
        assert required.issubset(cols)

    def test_name_unique(self):
        col = FeaturePack.__table__.c.name
        assert col.unique is True


# ═══════════════════════════════════════════════════════════════════════
# 3. Strategy Model
# ═══════════════════════════════════════════════════════════════════════


class TestStrategyModel:
    """Verify Strategy model aligns with design_strategy_registry.md v1.0."""

    def test_tablename(self):
        assert Strategy.__tablename__ == "strategies"

    def test_promotion_status_has_10_states(self):
        assert len(PromotionStatus) == 10

    def test_promotion_status_values_match_design(self):
        values = {e.value for e in PromotionStatus}
        assert values == PROMOTION_STATES_10

    def test_promotion_status_all_uppercase(self):
        for e in PromotionStatus:
            assert e.value == e.value.upper(), f"{e.name} value is not UPPERCASE: {e.value}"

    def test_backtest_fail_exists(self):
        """CR-048 design card requires BACKTEST_FAIL state."""
        assert hasattr(PromotionStatus, "BACKTEST_FAIL")
        assert PromotionStatus.BACKTEST_FAIL.value == "BACKTEST_FAIL"

    def test_asset_class_enum_values(self):
        values = {e.value for e in AssetClass}
        assert values == ASSET_CLASSES_3

    def test_asset_class_all_uppercase(self):
        for e in AssetClass:
            assert e.value == e.value.upper()

    def test_has_market_matrix_columns(self):
        cols = {c.name for c in Strategy.__table__.columns}
        matrix_cols = {
            "asset_classes",
            "exchanges",
            "sectors",
            "timeframes",
            "regimes",
            "max_symbols",
        }
        assert matrix_cols.issubset(cols)

    def test_has_champion_challenger_columns(self):
        cols = {c.name for c in Strategy.__table__.columns}
        assert "is_champion" in cols
        assert "champion_since" in cols

    def test_required_columns_present(self):
        cols = {c.name for c in Strategy.__table__.columns}
        required = {
            "id",
            "name",
            "version",
            "description",
            "feature_pack_id",
            "compute_module",
            "checksum",
            "asset_classes",
            "exchanges",
            "sectors",
            "timeframes",
            "regimes",
            "max_symbols",
            "status",
            "promoted_at",
            "promoted_by",
            "is_champion",
            "champion_since",
            "created_at",
            "updated_at",
        }
        assert required.issubset(cols)


# ═══════════════════════════════════════════════════════════════════════
# 4. PromotionEvent Model
# ═══════════════════════════════════════════════════════════════════════


class TestPromotionEventModel:
    """Verify PromotionEvent model aligns with design_promotion_state.md v1.0."""

    def test_tablename(self):
        assert PromotionEvent.__tablename__ == "promotion_events"

    def test_has_evidence_column(self):
        cols = {c.name for c in PromotionEvent.__table__.columns}
        assert "evidence" in cols

    def test_has_approved_by_column(self):
        cols = {c.name for c in PromotionEvent.__table__.columns}
        assert "approved_by" in cols

    def test_evidence_nullable(self):
        col = PromotionEvent.__table__.c.evidence
        assert col.nullable is True

    def test_approved_by_nullable(self):
        col = PromotionEvent.__table__.c.approved_by
        assert col.nullable is True

    def test_required_columns_present(self):
        cols = {c.name for c in PromotionEvent.__table__.columns}
        required = {
            "id",
            "strategy_id",
            "from_status",
            "to_status",
            "reason",
            "triggered_by",
            "approval_level",
            "evidence",
            "approved_by",
            "created_at",
        }
        assert required.issubset(cols)

    def test_strategy_id_indexed(self):
        """strategy_id should be indexed for efficient queries."""
        col = PromotionEvent.__table__.c.strategy_id
        assert col.index is True


# ═══════════════════════════════════════════════════════════════════════
# 5. Cross-Model Consistency
# ═══════════════════════════════════════════════════════════════════════


class TestCrossModelConsistency:
    """Verify consistency across all 4 control-plane models."""

    def test_strategy_status_uses_promotion_status(self):
        """Strategy.status column should reference PromotionStatus enum values."""
        # Get the enum type from the column
        col = Strategy.__table__.c.status
        # The column uses SQLAlchemy Enum with PromotionStatus
        enum_values = col.type.enums
        design_values = {e.value for e in PromotionStatus}
        assert set(enum_values) == design_values

    def test_all_models_have_id_primary_key(self):
        for model in (Indicator, FeaturePack, Strategy, PromotionEvent):
            pk_cols = [c.name for c in model.__table__.primary_key.columns]
            assert pk_cols == ["id"], f"{model.__tablename__} PK is {pk_cols}"

    def test_all_models_have_created_at(self):
        for model in (Indicator, FeaturePack, Strategy, PromotionEvent):
            cols = {c.name for c in model.__table__.columns}
            assert "created_at" in cols, f"{model.__tablename__} missing created_at"

    def test_registries_have_updated_at(self):
        """Registry models (not PromotionEvent which is append-only) have updated_at."""
        for model in (Indicator, FeaturePack, Strategy):
            cols = {c.name for c in model.__table__.columns}
            assert "updated_at" in cols, f"{model.__tablename__} missing updated_at"

    def test_promotion_event_is_append_only(self):
        """PromotionEvent should NOT have updated_at (append-only audit trail)."""
        cols = {c.name for c in PromotionEvent.__table__.columns}
        assert "updated_at" not in cols

    def test_indicator_status_is_subset_of_valid_states(self):
        """IndicatorStatus values should be a subset of reasonable lifecycle states."""
        ind_values = {e.value for e in IndicatorStatus}
        # All indicator states should exist as concepts in the broader system
        assert ind_values == {"ACTIVE", "DEPRECATED", "BLOCKED"}

    def test_feature_pack_status_has_challenger(self):
        """FeaturePack must support Champion/Challenger pattern."""
        fp_values = {e.value for e in FeaturePackStatus}
        assert "CHALLENGER" in fp_values
        assert "ACTIVE" in fp_values  # Champion is the ACTIVE one

    def test_all_id_columns_are_string_36(self):
        """All ID columns should be String(36) for UUID storage."""
        for model in (Indicator, FeaturePack, Strategy, PromotionEvent):
            col = model.__table__.c.id
            assert col.type.length == 36, f"{model.__tablename__}.id length={col.type.length}"
