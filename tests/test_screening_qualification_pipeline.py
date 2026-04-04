"""Stage 4A: Screening-Qualification Pipeline composition tests.

Covers:
  - PipelineVerdict enum
  - PipelineResult / PipelineEvidence / PipelineOutput invariants
  - _map_to_qualification_input field mapping
  - run_screening_qualification_pipeline: normal, reject, screen-fail, qualify-fail
  - Fail-closed chain (FC-1 through FC-5)
  - Evidence audit-only verification
  - Custom thresholds
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.asset import AssetClass, AssetSector
from app.services.data_provider import (
    BacktestReadiness,
    DataQualityDecision,
)
from app.services.screening_qualification_pipeline import (
    PipelineEvidence,
    PipelineOutput,
    PipelineResult,
    PipelineVerdict,
    _map_to_qualification_input,
    run_screening_qualification_pipeline,
)
from app.services.screening_transform import (
    TransformResult,
    _REJECT_DECISIONS,
    transform_provider_to_screening,
)
from app.services.symbol_screener import ScreeningInput, ScreeningThresholds
from app.services.backtest_qualification import QualificationThresholds
from tests.fixtures.qualification_fixtures import (
    QUAL_BACKTEST_AAPL_PASS,
    QUAL_BACKTEST_BTC_PASS,
    QUAL_BACKTEST_HIGH_MISSING,
    QUAL_BACKTEST_KR_PASS,
    QUAL_BACKTEST_LOW_BARS,
    QUAL_BACKTEST_NEGATIVE_SHARPE,
    QUAL_BACKTEST_SOL_PASS,
)
from tests.fixtures.screening_fixtures import (
    FIXTURE_OK_CRYPTO_BTC_BACKTEST,
    FIXTURE_OK_CRYPTO_BTC_MARKET,
    FIXTURE_OK_CRYPTO_BTC_METADATA,
    FIXTURE_OK_CRYPTO_SOL_BACKTEST,
    FIXTURE_OK_CRYPTO_SOL_MARKET,
    FIXTURE_OK_CRYPTO_SOL_METADATA,
    FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST,
    FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET,
    FIXTURE_OK_F9_DEGRADED_BACKTEST,
    FIXTURE_OK_F9_DEGRADED_MARKET,
    FIXTURE_OK_KR_005930_BACKTEST,
    FIXTURE_OK_KR_005930_MARKET,
    FIXTURE_OK_KR_005930_METADATA,
    FIXTURE_OK_US_AAPL_BACKTEST,
    FIXTURE_OK_US_AAPL_FUNDAMENTAL,
    FIXTURE_OK_US_AAPL_MARKET,
    FIXTURE_OK_US_AAPL_METADATA,
    FIXTURE_REJECT_F1_EMPTY_BACKTEST,
    FIXTURE_REJECT_F1_EMPTY_MARKET,
    FIXTURE_REJECT_F2_PARTIAL_BACKTEST,
    FIXTURE_REJECT_F2_PARTIAL_MARKET,
    FIXTURE_REJECT_F4_STALE_BACKTEST,
    FIXTURE_REJECT_F4_STALE_MARKET,
    FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
    FIXTURE_REJECT_F7_NAMESPACE_MARKET,
    FIXTURE_REJECT_F8_TIMEOUT_BACKTEST,
    FIXTURE_REJECT_F8_TIMEOUT_MARKET,
    NOW_UTC,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _transform(market, backtest, fundamental, metadata, asset_class, sector):
    """Shorthand for transform_provider_to_screening."""
    return transform_provider_to_screening(
        market,
        backtest,
        fundamental,
        metadata,
        asset_class,
        sector,
        NOW_UTC,
    )


# ── PipelineVerdict ─────────────────────────────────────────────────


class TestPipelineVerdict:
    def test_verdict_values(self):
        assert PipelineVerdict.DATA_REJECTED == "data_rejected"
        assert PipelineVerdict.SCREEN_FAILED == "screen_failed"
        assert PipelineVerdict.QUALIFY_FAILED == "qualify_failed"
        assert PipelineVerdict.QUALIFIED == "qualified"

    def test_verdict_is_string_enum(self):
        assert isinstance(PipelineVerdict.QUALIFIED, str)

    def test_verdict_exhaustive(self):
        assert len(PipelineVerdict) == 4

    def test_verdict_members(self):
        names = {v.name for v in PipelineVerdict}
        assert names == {"DATA_REJECTED", "SCREEN_FAILED", "QUALIFY_FAILED", "QUALIFIED"}


# ── PipelineResult ──────────────────────────────────────────────────


class TestPipelineResult:
    def test_frozen(self):
        r = PipelineResult(symbol="X", verdict=PipelineVerdict.QUALIFIED)
        with pytest.raises(AttributeError):
            r.verdict = PipelineVerdict.DATA_REJECTED  # type: ignore

    def test_reject_invariant(self):
        r = PipelineResult(symbol="X", verdict=PipelineVerdict.DATA_REJECTED)
        assert r.screening_output is None
        assert r.qualification_output is None

    def test_screen_failed_defaults(self):
        r = PipelineResult(symbol="X", verdict=PipelineVerdict.SCREEN_FAILED)
        assert r.qualification_output is None

    def test_defaults_none(self):
        r = PipelineResult(symbol="X", verdict=PipelineVerdict.QUALIFIED)
        assert r.screening_output is None
        assert r.qualification_output is None


# ── PipelineEvidence ────────────────────────────────────────────────


class TestPipelineEvidence:
    def test_frozen(self):
        e = PipelineEvidence(
            symbol="X",
            transform_decision=DataQualityDecision.OK,
        )
        with pytest.raises(AttributeError):
            e.symbol = "Y"  # type: ignore

    def test_defaults(self):
        e = PipelineEvidence(
            symbol="X",
            transform_decision=DataQualityDecision.OK,
        )
        assert e.screening_score is None
        assert e.screening_stage_count == 0
        assert e.qualification_status is None
        assert e.qualification_check_count == 0
        assert e.pipeline_timestamp is None

    def test_full_construction(self):
        e = PipelineEvidence(
            symbol="BTC/USDT",
            transform_decision=DataQualityDecision.OK,
            screening_score=0.85,
            screening_stage_count=5,
            qualification_status="pass",
            qualification_check_count=7,
            pipeline_timestamp=NOW_UTC,
        )
        assert e.screening_score == 0.85
        assert e.qualification_check_count == 7

    def test_audit_only(self):
        """Evidence differences don't change pipeline result."""
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out1 = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        out2 = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        assert out1.result.verdict == out2.result.verdict


# ── _map_to_qualification_input ─────────────────────────────────────


class TestMapToQualificationInput:
    def _make_input(self):
        return ScreeningInput(
            symbol="BTC/USDT",
            asset_class=AssetClass.CRYPTO,
            sector=AssetSector.LAYER1,
            avg_daily_volume_usd=35e9,
            atr_pct=3.2,
            adx=28.0,
        )

    def test_symbol_copied(self):
        qi = _map_to_qualification_input(
            self._make_input(),
            QUAL_BACKTEST_BTC_PASS,
            "strat1",
            "1h",
        )
        assert qi.symbol == "BTC/USDT"

    def test_asset_class_to_string(self):
        qi = _map_to_qualification_input(
            self._make_input(),
            QUAL_BACKTEST_BTC_PASS,
            "strat1",
            "1h",
        )
        assert qi.symbol_asset_class == AssetClass.CRYPTO.value

    def test_total_bars_from_backtest(self):
        qi = _map_to_qualification_input(
            self._make_input(),
            QUAL_BACKTEST_BTC_PASS,
            "strat1",
            "1h",
        )
        assert qi.total_bars == 2000

    def test_none_bars_to_zero(self):
        bt = BacktestReadiness(symbol="X")
        qi = _map_to_qualification_input(
            self._make_input(),
            bt,
            "strat1",
            "1h",
        )
        assert qi.total_bars == 0

    def test_missing_data_mapped(self):
        qi = _map_to_qualification_input(
            self._make_input(),
            QUAL_BACKTEST_BTC_PASS,
            "strat1",
            "1h",
        )
        assert qi.missing_data_pct == 0.3

    def test_sharpe_passthrough(self):
        qi = _map_to_qualification_input(
            self._make_input(),
            QUAL_BACKTEST_BTC_PASS,
            "strat1",
            "1h",
        )
        assert qi.sharpe_ratio == 0.85

    def test_strategy_id_passed(self):
        qi = _map_to_qualification_input(
            self._make_input(),
            QUAL_BACKTEST_BTC_PASS,
            "my_strat",
            "4h",
        )
        assert qi.strategy_id == "my_strat"
        assert qi.timeframe == "4h"


# ── Normal pipeline (golden set) ────────────────────────────────────


class TestRunPipelineNormal:
    def test_btc_qualified(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.QUALIFIED
        assert out.result.screening_output is not None
        assert out.result.qualification_output is not None
        assert out.result.screening_output.all_passed is True
        assert out.result.qualification_output.all_passed is True

    def test_sol_qualified(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_SOL_MARKET,
            FIXTURE_OK_CRYPTO_SOL_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_SOL_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_SOL_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.QUALIFIED

    def test_aapl_qualified(self):
        tr = _transform(
            FIXTURE_OK_US_AAPL_MARKET,
            FIXTURE_OK_US_AAPL_BACKTEST,
            FIXTURE_OK_US_AAPL_FUNDAMENTAL,
            FIXTURE_OK_US_AAPL_METADATA,
            AssetClass.US_STOCK,
            AssetSector.TECH,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_AAPL_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.QUALIFIED

    def test_kr_005930_qualified(self):
        tr = _transform(
            FIXTURE_OK_KR_005930_MARKET,
            FIXTURE_OK_KR_005930_BACKTEST,
            None,
            FIXTURE_OK_KR_005930_METADATA,
            AssetClass.KR_STOCK,
            AssetSector.SEMICONDUCTOR,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_KR_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.QUALIFIED


# ── Reject pipeline (FC-1/FC-2) ────────────────────────────────────


class TestRunPipelineReject:
    def test_f1_empty_data_rejected(self):
        tr = _transform(
            FIXTURE_REJECT_F1_EMPTY_MARKET,
            FIXTURE_REJECT_F1_EMPTY_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.DATA_REJECTED
        assert out.result.screening_output is None
        assert out.result.qualification_output is None

    def test_f2_partial_mandatory_rejected(self):
        tr = _transform(
            FIXTURE_REJECT_F2_PARTIAL_MARKET,
            FIXTURE_REJECT_F2_PARTIAL_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.DATA_REJECTED

    def test_f4_stale_data_rejected(self):
        tr = _transform(
            FIXTURE_REJECT_F4_STALE_MARKET,
            FIXTURE_REJECT_F4_STALE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.DATA_REJECTED

    def test_f7_namespace_data_rejected(self):
        tr = _transform(
            FIXTURE_REJECT_F7_NAMESPACE_MARKET,
            FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.DATA_REJECTED

    def test_f8_timeout_data_rejected(self):
        tr = _transform(
            FIXTURE_REJECT_F8_TIMEOUT_MARKET,
            FIXTURE_REJECT_F8_TIMEOUT_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.DATA_REJECTED

    def test_none_input_data_rejected(self):
        """FC-2: TransformResult with decision=OK but screening_input=None."""
        tr = TransformResult(decision=DataQualityDecision.OK)
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.DATA_REJECTED


# ── Screen-failed pipeline (FC-3) ──────────────────────────────────


class TestRunPipelineScreenFailed:
    def _make_screen_fail_transform(self):
        """OK transform but screening will fail due to low ADX."""
        from app.services.data_provider import MarketDataSnapshot
        from datetime import timedelta

        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            timestamp=NOW_UTC - timedelta(minutes=10),
            avg_daily_volume_usd=35e9,
            atr_pct=3.2,
            adx=5.0,  # below threshold 15
            market_cap_usd=1_340_000_000_000,
            spread_pct=0.01,
            price_vs_200ma=1.08,
        )
        bt = BacktestReadiness(
            symbol="BTC/USDT",
            available_bars=2000,
            sharpe_ratio=0.85,
            missing_data_pct=0.3,
        )
        return _transform(
            market,
            bt,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )

    def test_low_adx_screen_failed(self):
        tr = self._make_screen_fail_transform()
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.SCREEN_FAILED

    def test_screen_failed_has_screening_output(self):
        tr = self._make_screen_fail_transform()
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.screening_output is not None
        assert out.result.qualification_output is None

    def test_screen_failed_screening_not_all_passed(self):
        tr = self._make_screen_fail_transform()
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.screening_output.all_passed is False


# ── Qualify-failed pipeline (FC-4) ──────────────────────────────────


class TestRunPipelineQualifyFailed:
    def test_negative_sharpe_qualify_failed(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_NEGATIVE_SHARPE,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.QUALIFY_FAILED

    def test_qualify_failed_has_both_outputs(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_NEGATIVE_SHARPE,
            now_utc=NOW_UTC,
        )
        assert out.result.screening_output is not None
        assert out.result.qualification_output is not None

    def test_qualify_failed_screening_passed(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_NEGATIVE_SHARPE,
            now_utc=NOW_UTC,
        )
        assert out.result.screening_output.all_passed is True

    def test_high_missing_qualify_failed(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_HIGH_MISSING,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.QUALIFY_FAILED


# ── Fail-closed chain ───────────────────────────────────────────────


class TestFailClosedChain:
    def test_reject_never_reaches_screen(self):
        tr = _transform(
            FIXTURE_REJECT_F7_NAMESPACE_MARKET,
            FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.screening_output is None

    def test_screen_fail_never_reaches_qualify(self):
        from app.services.data_provider import MarketDataSnapshot
        from datetime import timedelta

        market = MarketDataSnapshot(
            symbol="BTC/USDT",
            timestamp=NOW_UTC - timedelta(minutes=10),
            avg_daily_volume_usd=35e9,
            atr_pct=3.2,
            adx=5.0,
            market_cap_usd=1_340_000_000_000,
        )
        bt = BacktestReadiness(
            symbol="BTC/USDT",
            available_bars=2000,
            sharpe_ratio=0.85,
        )
        tr = _transform(market, bt, None, None, AssetClass.CRYPTO, AssetSector.LAYER1)
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.qualification_output is None

    def test_f3_partial_usable_continues(self):
        tr = _transform(
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_MARKET,
            FIXTURE_OK_F3_PARTIAL_OPTIONAL_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        assert tr.decision == DataQualityDecision.PARTIAL_USABLE
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        # Should not be DATA_REJECTED (PARTIAL_USABLE is not a reject)
        assert out.result.verdict != PipelineVerdict.DATA_REJECTED

    def test_f9_degraded_continues(self):
        tr = _transform(
            FIXTURE_OK_F9_DEGRADED_MARKET,
            FIXTURE_OK_F9_DEGRADED_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict != PipelineVerdict.DATA_REJECTED

    def test_symbol_consistency(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.symbol == out.evidence.symbol


# ── Evidence recording ──────────────────────────────────────────────


class TestPipelineEvidenceRecording:
    def test_evidence_records_transform_decision(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.evidence.transform_decision == DataQualityDecision.OK

    def test_evidence_records_screening_score(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.evidence.screening_score is not None

    def test_evidence_records_timestamp(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.evidence.pipeline_timestamp == NOW_UTC

    def test_reject_evidence_has_no_screening(self):
        tr = _transform(
            FIXTURE_REJECT_F7_NAMESPACE_MARKET,
            FIXTURE_REJECT_F7_NAMESPACE_BACKTEST,
            None,
            None,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.evidence.screening_score is None
        assert out.evidence.screening_stage_count == 0


# ── Custom thresholds ───────────────────────────────────────────────


class TestPipelineCustomThresholds:
    def test_custom_screening_thresholds(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        custom = ScreeningThresholds(min_adx=50.0)  # very high → screen fail
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            screening_thresholds=custom,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.SCREEN_FAILED

    def test_custom_qualification_thresholds(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        custom = QualificationThresholds(min_sharpe=5.0)  # very high → qualify fail
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            qualification_thresholds=custom,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.QUALIFY_FAILED

    def test_default_thresholds_used(self):
        tr = _transform(
            FIXTURE_OK_CRYPTO_BTC_MARKET,
            FIXTURE_OK_CRYPTO_BTC_BACKTEST,
            None,
            FIXTURE_OK_CRYPTO_BTC_METADATA,
            AssetClass.CRYPTO,
            AssetSector.LAYER1,
        )
        out = run_screening_qualification_pipeline(
            tr,
            QUAL_BACKTEST_BTC_PASS,
            now_utc=NOW_UTC,
        )
        assert out.result.verdict == PipelineVerdict.QUALIFIED


# ── Unknown decision fail-fast (FC-0) ─────────────────────────────


class TestUnknownDecisionFailFast:
    """Criterion #7: unknown DataQualityDecision raises ValueError."""

    def test_unknown_decision_raises_valueerror(self):
        """A fabricated decision not in REJECT or PROCEED sets → ValueError."""
        from enum import Enum

        # Create a fake decision that looks like DataQualityDecision but isn't
        class FakeDecision(str, Enum):
            UNKNOWN_NEW = "unknown_new"

        tr = TransformResult(decision=FakeDecision.UNKNOWN_NEW)
        with pytest.raises(ValueError, match="Unknown DataQualityDecision"):
            run_screening_qualification_pipeline(
                tr,
                QUAL_BACKTEST_BTC_PASS,
                now_utc=NOW_UTC,
            )

    def test_all_known_decisions_covered(self):
        """Every DataQualityDecision member is in REJECT or PROCEED sets."""
        from app.services.screening_qualification_pipeline import (
            _PROCEED_DECISIONS,
        )
        from app.services.screening_transform import _REJECT_DECISIONS

        all_known = _REJECT_DECISIONS | _PROCEED_DECISIONS
        for member in DataQualityDecision:
            assert member in all_known, (
                f"{member} is not in REJECT or PROCEED — pipeline would ValueError"
            )
