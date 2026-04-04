"""RI-1: Pipeline Shadow Runner Tests — pure shadow execution verification.

Tests the shadow pipeline runner for:
  - ShadowRunResult structure and immutability
  - Normal pipeline flow (QUALIFIED golden path)
  - Data rejection handling
  - Fail-closed behaviour
  - Shadow comparison logic (match, mismatch, insufficient)
  - Purity guarantees (no DB, no async, no side-effect)
  - Evidence separation (result vs evidence independence)

All tests are pure — no DB, no async, no mock patching of sealed assets.
"""

from datetime import datetime, timezone

import pytest

from app.models.asset import AssetClass, AssetSector
from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    FundamentalSnapshot,
    MarketDataSnapshot,
    SymbolMetadata,
)
from app.services.pipeline_shadow_runner import (
    ComparisonVerdict,
    ReasonComparisonDetail,
    ShadowComparisonInput,
    ShadowRunResult,
    _compute_input_fingerprint,
    compare_shadow_to_existing,
    run_shadow_pipeline,
)
from app.services.screening_qualification_pipeline import (
    PipelineOutput,
    PipelineVerdict,
)


# ── Fixtures ──────────────────────────────────────────────────────────

_NOW = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc)


def _make_market(
    symbol: str = "SOL/USDT",
    volume: float = 500_000_000.0,
    atr_pct: float = 5.0,
    adx: float = 30.0,
    price_vs_200ma: float = 1.05,
    market_cap: float = 50_000_000_000.0,
) -> MarketDataSnapshot:
    return MarketDataSnapshot(
        symbol=symbol,
        timestamp=_NOW,
        price_usd=150.0,
        market_cap_usd=market_cap,
        avg_daily_volume_usd=volume,
        spread_pct=0.05,
        atr_pct=atr_pct,
        adx=adx,
        price_vs_200ma=price_vs_200ma,
        quality=DataQuality.HIGH,
    )


def _make_backtest(
    symbol: str = "SOL/USDT",
    bars: int = 1000,
    sharpe: float = 1.5,
    missing: float = 1.0,
) -> BacktestReadiness:
    return BacktestReadiness(
        symbol=symbol,
        available_bars=bars,
        sharpe_ratio=sharpe,
        missing_data_pct=missing,
        quality=DataQuality.HIGH,
    )


# ═══════════════════════════════════════════════════════════════════════
# Test Classes
# ═══════════════════════════════════════════════════════════════════════


class TestShadowRunResult:
    """ShadowRunResult frozen dataclass structure tests."""

    def test_result_is_frozen(self):
        market = _make_market()
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        with pytest.raises(AttributeError):
            result.symbol = "BTC/USDT"  # type: ignore[misc]

    def test_result_has_required_fields(self):
        market = _make_market()
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert result.symbol == "SOL/USDT"
        assert isinstance(result.pipeline_output, PipelineOutput)
        assert result.shadow_timestamp == _NOW
        assert isinstance(result.input_fingerprint, str)
        assert len(result.input_fingerprint) == 16
        assert result.comparison_verdict is None

    def test_comparison_verdict_default_none(self):
        market = _make_market()
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert result.comparison_verdict is None


class TestRunShadowPipelineNormal:
    """Golden path: all stages pass → QUALIFIED."""

    def test_qualified_golden_path(self):
        market = _make_market()
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert result.pipeline_output.result.verdict == PipelineVerdict.QUALIFIED

    def test_symbol_matches_market_input(self):
        market = _make_market(symbol="BTC/USDT")
        backtest = _make_backtest(symbol="BTC/USDT")
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert result.symbol == "BTC/USDT"

    def test_fingerprint_deterministic(self):
        market = _make_market()
        backtest = _make_backtest()
        r1 = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        r2 = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert r1.input_fingerprint == r2.input_fingerprint

    def test_fingerprint_changes_with_input(self):
        market1 = _make_market(volume=500_000_000.0)
        market2 = _make_market(volume=100_000_000.0)
        backtest = _make_backtest()
        r1 = run_shadow_pipeline(
            market1,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        r2 = run_shadow_pipeline(
            market2,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert r1.input_fingerprint != r2.input_fingerprint

    def test_evidence_populated(self):
        market = _make_market()
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        evidence = result.pipeline_output.evidence
        assert evidence.symbol == "SOL/USDT"
        assert evidence.pipeline_timestamp == _NOW

    def test_with_optional_params(self):
        """Shadow pipeline works with all optional params provided."""
        market = _make_market()
        backtest = _make_backtest()
        fundamental = FundamentalSnapshot(
            symbol="SOL/USDT",
            quality=DataQuality.HIGH,
        )
        metadata = SymbolMetadata(
            symbol="SOL/USDT",
            market="crypto",
            listing_age_days=365,
        )
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            fundamental=fundamental,
            metadata=metadata,
            strategy_id="smc_v1",
            timeframe="1h",
            now_utc=_NOW,
        )
        assert result.pipeline_output.result.verdict == PipelineVerdict.QUALIFIED


class TestRunShadowPipelineReject:
    """Data quality rejection → DATA_REJECTED."""

    def test_unavailable_market_data(self):
        market = MarketDataSnapshot(
            symbol="SOL/USDT",
            quality=DataQuality.UNAVAILABLE,
        )
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert result.pipeline_output.result.verdict == PipelineVerdict.DATA_REJECTED

    def test_stale_market_data(self):
        """Stale data with no timestamp → STALE_REJECT → DATA_REJECTED."""
        market = MarketDataSnapshot(
            symbol="SOL/USDT",
            timestamp=None,
            quality=DataQuality.STALE,
        )
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        # Stale with no timestamp triggers stale_reject in transform
        assert result.pipeline_output.result.verdict == PipelineVerdict.DATA_REJECTED


class TestRunShadowPipelineFailClosed:
    """Fail-closed: screening or qualification failure."""

    def test_screen_fail_low_volume(self):
        """Volume below threshold → SCREEN_FAILED."""
        market = _make_market(volume=1.0)  # Extremely low volume
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        verdict = result.pipeline_output.result.verdict
        assert verdict in (
            PipelineVerdict.SCREEN_FAILED,
            PipelineVerdict.DATA_REJECTED,
        )

    def test_qualify_fail_low_bars(self):
        """Insufficient bars → QUALIFY_FAILED (if screening passes)."""
        market = _make_market()
        backtest = _make_backtest(bars=10, sharpe=0.0, missing=50.0)
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        verdict = result.pipeline_output.result.verdict
        # With 10 bars and 50% missing, may fail at screening or qualification
        assert verdict in (
            PipelineVerdict.SCREEN_FAILED,
            PipelineVerdict.QUALIFY_FAILED,
        )

    def test_no_exception_on_edge_data(self):
        """Shadow runner must not raise on unusual but valid inputs."""
        market = _make_market(volume=0.0, atr_pct=0.0, adx=0.0)
        backtest = _make_backtest(bars=0, sharpe=-5.0, missing=100.0)
        # Must not raise — fail-closed returns a verdict, never an exception
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert isinstance(result, ShadowRunResult)
        assert result.pipeline_output.result.verdict in PipelineVerdict


class TestShadowComparison:
    """compare_shadow_to_existing — pure comparison logic."""

    def _qualified_result(self) -> ShadowRunResult:
        market = _make_market()
        backtest = _make_backtest()
        return run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )

    def test_match_qualified(self):
        shadow = self._qualified_result()
        assert shadow.pipeline_output.result.verdict == PipelineVerdict.QUALIFIED
        existing = ShadowComparisonInput(
            existing_screening_passed=True,
            existing_qualification_passed=True,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.MATCH

    def test_screening_verdict_mismatch(self):
        shadow = self._qualified_result()
        existing = ShadowComparisonInput(
            existing_screening_passed=False,  # shadow says pass, existing says fail
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.VERDICT_MISMATCH

    def test_qualification_verdict_mismatch(self):
        shadow = self._qualified_result()
        existing = ShadowComparisonInput(
            existing_screening_passed=True,
            existing_qualification_passed=False,  # shadow qualified, existing not
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.VERDICT_MISMATCH

    def test_insufficient_operational(self):
        """No existing data → INSUFFICIENT_OPERATIONAL."""
        shadow = self._qualified_result()
        existing = ShadowComparisonInput()  # All None
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.INSUFFICIENT_OPERATIONAL

    def test_data_rejected_insufficient_structural(self):
        """DATA_REJECTED → INSUFFICIENT_STRUCTURAL."""
        market = MarketDataSnapshot(
            symbol="SOL/USDT",
            quality=DataQuality.UNAVAILABLE,
        )
        backtest = _make_backtest()
        shadow = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert shadow.pipeline_output.result.verdict == PipelineVerdict.DATA_REJECTED
        existing = ShadowComparisonInput(
            existing_screening_passed=True,
            existing_qualification_passed=True,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.INSUFFICIENT_STRUCTURAL

    def test_comparison_preserves_original_fields(self):
        """compare_shadow_to_existing must NOT mutate original result fields."""
        shadow = self._qualified_result()
        existing = ShadowComparisonInput(
            existing_screening_passed=True,
            existing_qualification_passed=True,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.symbol == shadow.symbol
        assert compared.pipeline_output is shadow.pipeline_output
        assert compared.shadow_timestamp == shadow.shadow_timestamp
        assert compared.input_fingerprint == shadow.input_fingerprint

    def test_comparison_result_is_frozen(self):
        shadow = self._qualified_result()
        existing = ShadowComparisonInput(
            existing_screening_passed=True,
            existing_qualification_passed=True,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        with pytest.raises(AttributeError):
            compared.comparison_verdict = ComparisonVerdict.MATCH  # type: ignore[misc]


class TestShadowPurity:
    """Verify shadow runner has zero side-effects and is a pure function."""

    def test_no_state_mutation(self):
        """Two identical calls produce identical results — no hidden state."""
        market = _make_market()
        backtest = _make_backtest()
        r1 = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        r2 = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        assert r1.symbol == r2.symbol
        assert r1.input_fingerprint == r2.input_fingerprint
        assert r1.pipeline_output.result.verdict == r2.pipeline_output.result.verdict

    def test_now_utc_is_not_fetched(self):
        """When now_utc is provided, shadow_timestamp matches exactly."""
        fixed = datetime(2020, 1, 1, tzinfo=timezone.utc)
        market = _make_market()
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=fixed,
        )
        assert result.shadow_timestamp == fixed

    def test_default_now_utc_is_utc(self):
        """When now_utc is None, shadow uses UTC."""
        market = _make_market()
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert result.shadow_timestamp.tzinfo is not None


class TestShadowEvidence:
    """Evidence schema separation: result vs evidence independence."""

    def test_evidence_does_not_influence_verdict(self):
        """PipelineOutput.result.verdict is independent of evidence fields."""
        market = _make_market()
        backtest = _make_backtest()
        result = run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        # evidence exists but verdict is determined by result, not evidence
        assert result.pipeline_output.result.verdict == PipelineVerdict.QUALIFIED
        assert result.pipeline_output.evidence is not None

    def test_fingerprint_independent_of_verdict(self):
        """input_fingerprint depends on input data, not on pipeline outcome."""
        market_pass = _make_market()
        market_fail = _make_market(volume=0.0, atr_pct=0.0)
        backtest = _make_backtest()

        fp_pass = _compute_input_fingerprint(
            market_pass,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        fp_fail = _compute_input_fingerprint(
            market_fail,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        # Different inputs → different fingerprints, regardless of verdict
        assert fp_pass != fp_fail

    def test_fingerprint_is_hex_string(self):
        market = _make_market()
        backtest = _make_backtest()
        fp = _compute_input_fingerprint(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert len(fp) == 16
        int(fp, 16)  # Must be valid hex, raises ValueError otherwise


# ── RI-2A-1: INSUFFICIENT Split Tests ────────────────────────────────


class TestInsufficientSplit:
    """Verify INSUFFICIENT_STRUCTURAL vs INSUFFICIENT_OPERATIONAL classification."""

    def _qualified_result(self) -> ShadowRunResult:
        return run_shadow_pipeline(
            _make_market(),
            _make_backtest(),
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )

    def test_structural_when_data_rejected(self):
        """DATA_REJECTED shadow → INSUFFICIENT_STRUCTURAL regardless of existing."""
        market = MarketDataSnapshot(
            symbol="SOL/USDT",
            quality=DataQuality.UNAVAILABLE,
        )
        shadow = run_shadow_pipeline(
            market,
            _make_backtest(),
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        existing = ShadowComparisonInput(
            existing_screening_passed=True,
            existing_qualification_passed=True,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.INSUFFICIENT_STRUCTURAL

    def test_operational_when_no_existing(self):
        """No existing data → INSUFFICIENT_OPERATIONAL."""
        shadow = self._qualified_result()
        existing = ShadowComparisonInput()  # All None
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.INSUFFICIENT_OPERATIONAL

    def test_structural_and_operational_never_overlap(self):
        """DATA_REJECTED + no existing → INSUFFICIENT_OPERATIONAL (existing check first)."""
        market = MarketDataSnapshot(
            symbol="SOL/USDT",
            quality=DataQuality.UNAVAILABLE,
        )
        shadow = run_shadow_pipeline(
            market,
            _make_backtest(),
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        existing = ShadowComparisonInput()  # No existing
        compared = compare_shadow_to_existing(shadow, existing)
        # Operational check happens first (existing_screening_passed is None)
        assert compared.comparison_verdict == ComparisonVerdict.INSUFFICIENT_OPERATIONAL

    def test_structural_not_confused_with_match(self):
        """DATA_REJECTED is never classified as MATCH."""
        market = MarketDataSnapshot(
            symbol="SOL/USDT",
            quality=DataQuality.UNAVAILABLE,
        )
        shadow = run_shadow_pipeline(
            market,
            _make_backtest(),
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        existing = ShadowComparisonInput(
            existing_screening_passed=False,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.INSUFFICIENT_STRUCTURAL


# ── RI-2A-1: Reason-level Comparison Tests ───────────────────────────


class TestReasonLevelComparison:
    """Verify reason-level comparison between shadow and existing fail reasons."""

    def _screen_failed_result(self) -> ShadowRunResult:
        """Create a shadow result that fails screening (low volume, low ADX)."""
        market = _make_market(volume=1000.0, adx=5.0, atr_pct=0.5, market_cap=1e6)
        backtest = _make_backtest(bars=100, sharpe=-0.5, missing=20.0)
        return run_shadow_pipeline(
            market,
            backtest,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )

    def test_same_fail_stages_is_match(self):
        """Both fail screening at same stages → MATCH."""
        shadow = self._screen_failed_result()
        # Extract shadow's actual fail stages to mirror them
        screening = shadow.pipeline_output.result.screening_output
        assert screening is not None
        shadow_fails = frozenset(f"stage{sr.stage}" for sr in screening.stages if not sr.passed)
        assert len(shadow_fails) > 0  # Ensure we have fail stages

        existing = ShadowComparisonInput(
            existing_screening_passed=False,
            existing_screening_fail_stages=shadow_fails,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.MATCH

    def test_different_fail_stages_is_reason_mismatch(self):
        """Both fail screening but at different stages → REASON_MISMATCH."""
        shadow = self._screen_failed_result()

        existing = ShadowComparisonInput(
            existing_screening_passed=False,
            existing_screening_fail_stages=frozenset({"stage5"}),  # Different
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.REASON_MISMATCH

    def test_reason_detail_populated_on_mismatch(self):
        """ReasonComparisonDetail is populated when reason comparison occurs."""
        shadow = self._screen_failed_result()

        existing = ShadowComparisonInput(
            existing_screening_passed=False,
            existing_screening_fail_stages=frozenset({"stage5"}),
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.reason_comparison is not None
        assert isinstance(compared.reason_comparison, ReasonComparisonDetail)
        assert compared.reason_comparison.screening_reasons_match is False

    def test_reason_detail_on_match(self):
        """ReasonComparisonDetail is populated on MATCH too (when reason data exists)."""
        shadow = self._screen_failed_result()
        screening = shadow.pipeline_output.result.screening_output
        shadow_fails = frozenset(f"stage{sr.stage}" for sr in screening.stages if not sr.passed)
        existing = ShadowComparisonInput(
            existing_screening_passed=False,
            existing_screening_fail_stages=shadow_fails,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.MATCH
        assert compared.reason_comparison is not None
        assert compared.reason_comparison.screening_reasons_match is True

    def test_no_reason_comparison_when_both_pass(self):
        """No reason comparison when both pass screening (nothing to compare)."""
        shadow = run_shadow_pipeline(
            _make_market(),
            _make_backtest(),
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
            now_utc=_NOW,
        )
        existing = ShadowComparisonInput(
            existing_screening_passed=True,
            existing_qualification_passed=True,
        )
        compared = compare_shadow_to_existing(shadow, existing)
        assert compared.comparison_verdict == ComparisonVerdict.MATCH
        # No reason detail when both pass (no fail reasons to compare)
        assert compared.reason_comparison is None

    def test_missing_existing_reasons_skips_reason_compare(self):
        """When existing has no fail_stages data, reason comparison is skipped."""
        shadow = self._screen_failed_result()
        existing = ShadowComparisonInput(
            existing_screening_passed=False,
            existing_screening_fail_stages=None,  # No reason data
        )
        compared = compare_shadow_to_existing(shadow, existing)
        # Verdict matches (both fail) but no reason comparison possible
        assert compared.comparison_verdict == ComparisonVerdict.MATCH
        # reason_comparison is None because existing has no reason data
        assert compared.reason_comparison is None
