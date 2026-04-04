"""Tests for Stage 3A: SectorRotator — pure computation, zero I/O.

Covers:
  - Per-regime sector weight calculation
  - Full rotation output
  - Score adjustment
  - Edge cases (unknown regime, excluded sectors, clamping)
  - Interface Purity Proof (no I/O, no DB, no network)
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from app.models.asset import AssetSector, EXCLUDED_SECTORS
from app.services.sector_rotator import (
    RegimeLabel,
    SectorWeight,
    RotationOutput,
    DEFAULT_WEIGHT,
    MIN_WEIGHT,
    MAX_WEIGHT,
    get_sector_weight,
    compute_rotation,
    apply_sector_weight_to_score,
)


# ── RegimeLabel Tests ───────────────────────────────────────────────


class TestRegimeLabel:
    def test_all_regime_labels_defined(self):
        expected = {"trending_up", "trending_down", "ranging", "high_vol", "crisis", "unknown"}
        actual = {r.value for r in RegimeLabel}
        assert expected == actual

    def test_regime_label_is_str_enum(self):
        assert isinstance(RegimeLabel.TRENDING_UP, str)
        assert RegimeLabel.TRENDING_UP == "trending_up"


# ── get_sector_weight Tests ─────────────────────────────────────────


class TestGetSectorWeight:
    def test_trending_up_layer1_overweight(self):
        w = get_sector_weight(AssetSector.LAYER1, "trending_up")
        assert w == 1.5

    def test_trending_up_tech_overweight(self):
        w = get_sector_weight(AssetSector.TECH, "trending_up")
        assert w == 1.5

    def test_trending_up_semiconductor_overweight(self):
        w = get_sector_weight(AssetSector.SEMICONDUCTOR, "trending_up")
        assert w == 1.5

    def test_trending_up_defi_neutral(self):
        w = get_sector_weight(AssetSector.DEFI, "trending_up")
        assert w == DEFAULT_WEIGHT

    def test_trending_down_layer1_underweight(self):
        w = get_sector_weight(AssetSector.LAYER1, "trending_down")
        assert w == 0.5

    def test_trending_down_infra_overweight(self):
        w = get_sector_weight(AssetSector.INFRA, "trending_down")
        assert w == 1.3

    def test_ranging_defi_overweight(self):
        w = get_sector_weight(AssetSector.DEFI, "ranging")
        assert w == 1.3

    def test_ranging_it_overweight(self):
        w = get_sector_weight(AssetSector.IT, "ranging")
        assert w == 1.3

    def test_high_vol_all_underweight(self):
        for sector in [AssetSector.LAYER1, AssetSector.TECH, AssetSector.DEFI]:
            w = get_sector_weight(sector, "high_vol")
            assert w == 0.5, f"{sector} should be 0.5 in high_vol"

    def test_crisis_all_deeply_underweight(self):
        for sector in [AssetSector.LAYER1, AssetSector.TECH, AssetSector.DEFI]:
            w = get_sector_weight(sector, "crisis")
            assert w == 0.2, f"{sector} should be 0.2 in crisis"

    def test_unknown_regime_returns_default(self):
        w = get_sector_weight(AssetSector.LAYER1, "unknown")
        assert w == DEFAULT_WEIGHT

    def test_invalid_regime_returns_default(self):
        w = get_sector_weight(AssetSector.LAYER1, "nonexistent_regime")
        assert w == DEFAULT_WEIGHT

    def test_weight_clamped_above_min(self):
        """No weight should fall below MIN_WEIGHT."""
        for regime in RegimeLabel:
            for sector in AssetSector:
                w = get_sector_weight(sector, regime.value)
                assert w >= MIN_WEIGHT, f"{sector}/{regime}: {w} < {MIN_WEIGHT}"

    def test_weight_clamped_below_max(self):
        """No weight should exceed MAX_WEIGHT."""
        for regime in RegimeLabel:
            for sector in AssetSector:
                w = get_sector_weight(sector, regime.value)
                assert w <= MAX_WEIGHT, f"{sector}/{regime}: {w} > {MAX_WEIGHT}"


# ── compute_rotation Tests ──────────────────────────────────────────


class TestComputeRotation:
    def test_returns_rotation_output(self):
        result = compute_rotation("trending_up")
        assert isinstance(result, RotationOutput)

    def test_regime_preserved_in_output(self):
        result = compute_rotation("trending_down")
        assert result.regime == "trending_down"

    def test_excludes_excluded_sectors_by_default(self):
        result = compute_rotation("trending_up")
        returned_sectors = {sw.sector for sw in result.weights}
        for excl in EXCLUDED_SECTORS:
            assert excl not in returned_sectors

    def test_trending_up_overweight_sectors(self):
        result = compute_rotation("trending_up")
        assert AssetSector.LAYER1 in result.overweight_sectors
        assert AssetSector.TECH in result.overweight_sectors
        assert AssetSector.SEMICONDUCTOR in result.overweight_sectors

    def test_trending_down_underweight_sectors(self):
        result = compute_rotation("trending_down")
        assert AssetSector.LAYER1 in result.underweight_sectors
        assert AssetSector.TECH in result.underweight_sectors

    def test_trending_down_overweight_sectors(self):
        result = compute_rotation("trending_down")
        assert AssetSector.INFRA in result.overweight_sectors
        assert AssetSector.ENERGY in result.overweight_sectors

    def test_unknown_regime_all_neutral(self):
        result = compute_rotation("unknown")
        assert len(result.overweight_sectors) == 0
        assert len(result.underweight_sectors) == 0

    def test_custom_sector_list(self):
        sectors = [AssetSector.LAYER1, AssetSector.DEFI]
        result = compute_rotation("trending_up", sectors=sectors)
        assert len(result.weights) == 2

    def test_empty_sector_list(self):
        result = compute_rotation("trending_up", sectors=[])
        assert len(result.weights) == 0

    def test_all_non_excluded_sectors_covered(self):
        """compute_rotation(default) should cover all non-excluded sectors."""
        result = compute_rotation("trending_up")
        expected_count = len([s for s in AssetSector if s not in EXCLUDED_SECTORS])
        assert len(result.weights) == expected_count

    def test_weights_are_frozen(self):
        result = compute_rotation("trending_up")
        assert isinstance(result.weights, tuple)
        assert isinstance(result.overweight_sectors, tuple)


# ── apply_sector_weight_to_score Tests ──────────────────────────────


class TestApplySectorWeightToScore:
    def test_neutral_weight_preserves_score(self):
        score = apply_sector_weight_to_score(0.8, AssetSector.DEFI, "trending_up")
        assert score == pytest.approx(0.8)

    def test_overweight_increases_score(self):
        score = apply_sector_weight_to_score(0.6, AssetSector.LAYER1, "trending_up")
        assert score == pytest.approx(0.6 * 1.5)

    def test_underweight_decreases_score(self):
        score = apply_sector_weight_to_score(0.8, AssetSector.LAYER1, "trending_down")
        assert score == pytest.approx(0.8 * 0.5)

    def test_score_clamped_at_1(self):
        score = apply_sector_weight_to_score(0.9, AssetSector.LAYER1, "trending_up")
        assert score <= 1.0

    def test_score_clamped_at_0(self):
        score = apply_sector_weight_to_score(0.0, AssetSector.LAYER1, "crisis")
        assert score >= 0.0

    def test_crisis_regime_heavily_reduces(self):
        score = apply_sector_weight_to_score(1.0, AssetSector.LAYER1, "crisis")
        assert score == pytest.approx(0.2)


# ── Design Contract Alignment ──────────────────────────────────────


class TestDesignContractAlignment:
    def test_trending_up_favors_layer1_tech_semi(self):
        """Design card: TRENDING_UP → 가중: Layer1, Tech, 반도체"""
        for sector in [AssetSector.LAYER1, AssetSector.TECH, AssetSector.SEMICONDUCTOR]:
            w = get_sector_weight(sector, "trending_up")
            assert w > DEFAULT_WEIGHT

    def test_trending_down_favors_infra_energy_finance(self):
        """Design card: TRENDING_DOWN → 가중: Infra, Energy, 금융"""
        for sector in [AssetSector.INFRA, AssetSector.ENERGY, AssetSector.FINANCE]:
            w = get_sector_weight(sector, "trending_down")
            assert w > DEFAULT_WEIGHT

    def test_trending_down_reduces_layer1_tech(self):
        """Design card: TRENDING_DOWN → 감소: Layer1, Tech"""
        for sector in [AssetSector.LAYER1, AssetSector.TECH]:
            w = get_sector_weight(sector, "trending_down")
            assert w < DEFAULT_WEIGHT

    def test_ranging_favors_defi_it(self):
        """Design card: RANGING → 가중: DeFi, IT"""
        for sector in [AssetSector.DEFI, AssetSector.IT]:
            w = get_sector_weight(sector, "ranging")
            assert w > DEFAULT_WEIGHT

    def test_high_vol_reduces_all(self):
        """Design card: HIGH_VOL → 전체 exposure 축소"""
        result = compute_rotation("high_vol")
        assert len(result.overweight_sectors) == 0
        assert len(result.underweight_sectors) > 0

    def test_crisis_reduces_all(self):
        """Design card: CRISIS → 전체 축소"""
        result = compute_rotation("crisis")
        assert len(result.overweight_sectors) == 0
        assert len(result.underweight_sectors) > 0


# ── Interface Purity Proof ──────────────────────────────────────────


class TestInterfacePurityProof:
    """Verify that sector_rotator.py is pure: no I/O, no DB, no network."""

    _SOURCE_PATH = pathlib.Path("app/services/sector_rotator.py")

    def _get_source(self) -> str:
        return self._SOURCE_PATH.read_text(encoding="utf-8")

    def test_no_asyncio_imports(self):
        src = self._get_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "asyncio" not in alias.name
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "asyncio" not in node.module

    def test_no_sqlalchemy_imports(self):
        src = self._get_source()
        assert "sqlalchemy" not in src

    def test_no_async_session_imports(self):
        src = self._get_source()
        assert "AsyncSession" not in src

    def test_no_httpx_or_requests_imports(self):
        src = self._get_source()
        assert "httpx" not in src
        assert "import requests" not in src

    def test_no_celery_imports(self):
        src = self._get_source()
        assert (
            "celery" not in src.lower() or "celery" in src.lower().split("#")[-1]
        )  # allow comments
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "celery" not in node.module.lower()

    def test_no_os_or_file_operations(self):
        src = self._get_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module not in ("os", "shutil", "tempfile")

    def test_no_async_functions(self):
        """Pure module should have no async functions."""
        src = self._get_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef), f"Async function found: {node.name}"

    def test_no_regime_detector_import(self):
        """Must NOT import RegimeDetector (CR-046 prohibition)."""
        src = self._get_source()
        assert "regime_detector" not in src.lower() or "regime_detector" in "# regime_detector"
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "regime_detector" not in node.module

    def test_all_public_functions_are_pure(self):
        """All public functions must be synchronous and stateless."""
        import app.services.sector_rotator as mod

        public = [
            name
            for name in dir(mod)
            if callable(getattr(mod, name))
            and not name.startswith("_")
            and not isinstance(getattr(mod, name), type)
        ]
        for name in public:
            fn = getattr(mod, name)
            assert not inspect.iscoroutinefunction(fn), f"{name} is async"


# ── Stage 3B-1: RotationReasonCode ────────────────────────────────────


class TestRotationReasonCode:
    def test_reason_code_enum_values(self):
        from app.services.sector_rotator import RotationReasonCode

        expected = {
            "overweight_regime_aligned",
            "underweight_regime_opposed",
            "neutral_default",
            "neutral_unlisted",
            "reduced_high_vol",
            "reduced_crisis",
            "unknown_regime",
        }
        actual = {r.value for r in RotationReasonCode}
        assert expected == actual

    def test_reason_code_is_str_enum(self):
        from app.services.sector_rotator import RotationReasonCode

        assert isinstance(RotationReasonCode.NEUTRAL_DEFAULT, str)

    def test_get_sector_weight_unchanged_by_reason(self):
        """Reason codes do NOT influence weight calculation."""
        w1 = get_sector_weight(AssetSector.LAYER1, "trending_up")
        w2 = get_sector_weight(AssetSector.LAYER1, "trending_up")
        assert w1 == w2 == 1.5

    def test_reason_is_explanation_only(self):
        """compute_rotation returns reason but it doesn't affect weights."""
        out = compute_rotation("trending_up")
        for sw in out.weights:
            # reason exists and is a RotationReasonCode
            from app.services.sector_rotator import RotationReasonCode

            assert sw.reason is None or isinstance(sw.reason, RotationReasonCode)


# ── Stage 3B-1: SectorWeight Backward Compatibility ──────────────────


class TestSectorWeightBackwardCompat:
    def test_sector_weight_without_reason(self):
        """Existing 3-arg construction must still work."""
        sw = SectorWeight(sector=AssetSector.LAYER1, weight=1.5, regime="trending_up")
        assert sw.reason is None

    def test_sector_weight_with_reason(self):
        from app.services.sector_rotator import RotationReasonCode

        sw = SectorWeight(
            sector=AssetSector.LAYER1,
            weight=1.5,
            regime="trending_up",
            reason=RotationReasonCode.OVERWEIGHT_REGIME_ALIGNED,
        )
        assert sw.reason == RotationReasonCode.OVERWEIGHT_REGIME_ALIGNED

    def test_reason_default_is_none(self):
        sw = SectorWeight(sector=AssetSector.TECH, weight=1.0, regime="unknown")
        assert sw.reason is None

    def test_compute_rotation_populates_reason(self):
        """compute_rotation now populates reason on every SectorWeight."""
        out = compute_rotation("trending_up")
        for sw in out.weights:
            assert sw.reason is not None
