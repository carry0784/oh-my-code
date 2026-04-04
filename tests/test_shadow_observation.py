"""RI-2A-2a: Shadow Observation Log Tests — append-only INSERT.

Tests:
  - Model: fields, tablename, import safety
  - Record: INSERT normal, field mapping, timestamp, enum→str, JSON
  - Append-only: db.add only, no merge/delete/execute(UPDATE)
  - Insert failure isolation: failure → None, no propagation
  - Input validation: None inputs → None
  - Duplicate: same input 2x → 2 rows
  - Reason serialization: frozenset → JSON, None handling
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from app.models.asset import AssetClass, AssetSector
from app.models.shadow_observation import ShadowObservationLog
from app.services.data_provider import DataQuality, MarketDataSnapshot, BacktestReadiness
from app.services.pipeline_shadow_runner import (
    ComparisonVerdict,
    ReasonComparisonDetail,
    ReadthroughFailureCode,
    ShadowRunResult,
    run_shadow_pipeline,
)
from app.services.shadow_observation_service import (
    _serialize_reason_comparison,
    record_shadow_observation,
)
from app.services.shadow_readthrough import (
    ExistingResultSource,
    ReadthroughComparisonResult,
)


# ── Fixtures ──────────────────────────────────────────────────────

_NOW = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc)


def _make_market(symbol="SOL/USDT", volume=500_000_000.0) -> MarketDataSnapshot:
    return MarketDataSnapshot(
        symbol=symbol,
        timestamp=_NOW,
        price_usd=150.0,
        market_cap_usd=50e9,
        avg_daily_volume_usd=volume,
        spread_pct=0.05,
        atr_pct=5.0,
        adx=30.0,
        price_vs_200ma=1.05,
        quality=DataQuality.HIGH,
    )


def _make_backtest(symbol="SOL/USDT") -> BacktestReadiness:
    return BacktestReadiness(
        symbol=symbol,
        available_bars=1000,
        sharpe_ratio=1.5,
        missing_data_pct=1.0,
        quality=DataQuality.HIGH,
    )


def _shadow_qualified(symbol="SOL/USDT") -> ShadowRunResult:
    return run_shadow_pipeline(
        _make_market(symbol=symbol),
        _make_backtest(symbol=symbol),
        AssetClass.CRYPTO,
        AssetSector.LAYER1,
        now_utc=_NOW,
    )


def _make_readthrough_result(
    symbol="SOL/USDT",
    shadow_result=None,
    comparison_verdict=ComparisonVerdict.MATCH,
    reason_comparison=None,
    failure_code=None,
    screening_result_id="sr-001",
    qualification_result_id="qr-001",
) -> ReadthroughComparisonResult:
    if shadow_result is None:
        shadow_result = _shadow_qualified(symbol)
    source = ExistingResultSource(
        screening_result_id=screening_result_id,
        qualification_result_id=qualification_result_id,
        failure_code=failure_code,
    )
    return ReadthroughComparisonResult(
        symbol=symbol,
        shadow_result=shadow_result,
        comparison_verdict=comparison_verdict,
        reason_comparison=reason_comparison,
        existing_source=source,
    )


def _mock_db():
    """Create a mock AsyncSession that tracks add/flush calls."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


# ── TestShadowObservationModel ──────────────────────────────────


class TestShadowObservationModel:
    def test_tablename(self):
        assert ShadowObservationLog.__tablename__ == "shadow_observation_log"

    def test_required_fields(self):
        cols = {c.name for c in ShadowObservationLog.__table__.columns}
        required = {
            "id",
            "symbol",
            "asset_class",
            "asset_sector",
            "shadow_verdict",
            "comparison_verdict",
            "input_fingerprint",
            "shadow_timestamp",
            "created_at",
        }
        assert required.issubset(cols)

    def test_nullable_fields(self):
        col_map = {c.name: c for c in ShadowObservationLog.__table__.columns}
        nullable_fields = [
            "shadow_screening_passed",
            "shadow_qualification_passed",
            "existing_screening_passed",
            "existing_qualification_passed",
            "reason_comparison_json",
            "readthrough_failure_code",
            "existing_screening_result_id",
            "existing_qualification_result_id",
        ]
        for name in nullable_fields:
            assert col_map[name].nullable is True, f"{name} should be nullable"

    def test_import_from_models_init(self):
        from app.models import ShadowObservationLog as Imported

        assert Imported is ShadowObservationLog


# ── TestRecordObservation ───────────────────────────────────────


class TestRecordObservation:
    @pytest.mark.asyncio
    async def test_insert_returns_row(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result is not None
        assert isinstance(result, ShadowObservationLog)
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_field_mapping(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            existing_screening_passed=True,
        )

        assert result.symbol == "SOL/USDT"
        assert result.asset_class == "CRYPTO"
        assert result.asset_sector == AssetSector.LAYER1.value
        assert result.shadow_verdict == "qualified"
        assert result.comparison_verdict == "match"
        assert result.input_fingerprint == shadow.input_fingerprint
        assert result.existing_screening_passed is True

    @pytest.mark.asyncio
    async def test_shadow_timestamp_utc(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result.shadow_timestamp == _NOW
        assert result.shadow_timestamp.tzinfo is not None

    @pytest.mark.asyncio
    async def test_enum_to_str_conversion(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(
            shadow_result=shadow,
            comparison_verdict=ComparisonVerdict.VERDICT_MISMATCH,
        )

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result.comparison_verdict == "verdict_mismatch"
        assert result.asset_class == "CRYPTO"

    @pytest.mark.asyncio
    async def test_readthrough_failure_code_recorded(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(
            shadow_result=shadow,
            comparison_verdict=ComparisonVerdict.INSUFFICIENT_OPERATIONAL,
            failure_code=ReadthroughFailureCode.READTHROUGH_RESULT_NOT_FOUND,
            screening_result_id=None,
            qualification_result_id=None,
        )

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result.readthrough_failure_code == "readthrough_result_not_found"


# ── TestAppendOnlyGuarantee ─────────────────────────────────────


class TestAppendOnlyGuarantee:
    @pytest.mark.asyncio
    async def test_only_add_called(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_merge_called(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        db.merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_delete_called(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        db.delete.assert_not_called()

    def test_service_has_no_update_delete_methods(self):
        import app.services.shadow_observation_service as svc

        public_funcs = [
            name for name in dir(svc) if not name.startswith("_") and callable(getattr(svc, name))
        ]
        for name in public_funcs:
            assert "update" not in name.lower(), f"Found update method: {name}"
            assert "delete" not in name.lower(), f"Found delete method: {name}"
            assert "remove" not in name.lower(), f"Found remove method: {name}"


# ── TestInsertFailureIsolation ──────────────────────────────────


class TestInsertFailureIsolation:
    @pytest.mark.asyncio
    async def test_flush_failure_returns_none(self):
        db = _mock_db()
        db.flush = AsyncMock(side_effect=Exception("DB connection lost"))
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result is None  # No exception propagated

    @pytest.mark.asyncio
    async def test_add_failure_returns_none(self):
        db = _mock_db()
        db.add = MagicMock(side_effect=Exception("Constraint violation"))
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_failure_does_not_raise(self):
        db = _mock_db()
        db.flush = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        # Should NOT raise
        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert result is None


# ── TestInputValidation ─────────────────────────────────────────


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_shadow_result_none(self):
        db = _mock_db()
        readthrough = _make_readthrough_result()

        result = await record_shadow_observation(
            db,
            None,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result is None
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_readthrough_result_none(self):
        db = _mock_db()
        shadow = _shadow_qualified()

        result = await record_shadow_observation(
            db,
            shadow,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result is None
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_input_succeeds(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result is not None


# ── TestDuplicateAllowed ────────────────────────────────────────


class TestDuplicateAllowed:
    @pytest.mark.asyncio
    async def test_same_input_twice_produces_two_adds(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough_result(shadow_result=shadow)

        r1 = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        r2 = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert r1 is not None
        assert r2 is not None
        assert db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_no_unique_constraint_on_table(self):
        """Verify no UNIQUE constraints exist on the table (append-only)."""
        table = ShadowObservationLog.__table__
        unique_constraints = [
            c
            for c in table.constraints
            if hasattr(c, "columns") and getattr(c, "_pending_colargs", None) is None
        ]
        # Only PK constraint should exist
        from sqlalchemy import PrimaryKeyConstraint

        non_pk = [c for c in unique_constraints if not isinstance(c, PrimaryKeyConstraint)]
        assert len(non_pk) == 0, f"Found non-PK unique constraints: {non_pk}"


# ── TestReasonComparisonSerialization ───────────────────────────


class TestReasonComparisonSerialization:
    def test_none_returns_none(self):
        assert _serialize_reason_comparison(None) is None

    def test_frozenset_converted_to_list(self):
        detail = ReasonComparisonDetail(
            screening_reasons_match=False,
            shadow_screening_fail_stages=frozenset({"stage2", "stage3"}),
            existing_screening_fail_stages=frozenset({"stage3"}),
        )
        result = _serialize_reason_comparison(detail)
        parsed = json.loads(result)
        assert isinstance(parsed["shadow_screening_fail_stages"], list)
        assert sorted(parsed["shadow_screening_fail_stages"]) == ["stage2", "stage3"]

    @pytest.mark.asyncio
    async def test_reason_json_recorded_in_observation(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        detail = ReasonComparisonDetail(
            screening_reasons_match=True,
            shadow_screening_fail_stages=frozenset({"stage2"}),
            existing_screening_fail_stages=frozenset({"stage2"}),
        )
        readthrough = _make_readthrough_result(
            shadow_result=shadow,
            reason_comparison=detail,
        )

        result = await record_shadow_observation(
            db,
            shadow,
            readthrough,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

        assert result.reason_comparison_json is not None
        parsed = json.loads(result.reason_comparison_json)
        assert parsed["screening_reasons_match"] is True
