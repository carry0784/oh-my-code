"""Tests for Step 5 — Data Infrastructure Verification.

Covers:
  G2: FullCycleBacktester (SegmentSplitter, leakage, verdict)
  G3: HistoryDataManager (ingestion, coverage, replay contracts)

All tests use synthetic data — no DB or exchange connectivity required.
"""

from __future__ import annotations

import pytest
import numpy as np

# ═══════════════════════════════════════════════════════════════════════
# G2: FullCycleBacktester Verification
# ═══════════════════════════════════════════════════════════════════════


class TestSegmentSplitter:
    """SegmentSplitter is the core of B-1: 4-segment split + leakage check."""

    def _make_ohlcv(self, n=1000):
        """Generate synthetic OHLCV data."""
        ohlcv = []
        base = 100.0
        for i in range(n):
            ts = 1700000000000 + i * 3600000
            c = base + np.sin(i / 50) * 10 + i * 0.01
            ohlcv.append([ts, c - 0.5, c + 1.0, c - 1.0, c, 1000 + i])
        return ohlcv

    def test_split_produces_four_segments(self):
        from app.services.full_cycle_backtester import FullCycleConfig, SegmentSplitter

        ohlcv = self._make_ohlcv(1000)
        config = FullCycleConfig()
        segments = SegmentSplitter.split(ohlcv, config)
        assert set(segments.keys()) == {"train", "forward_1", "forward_2", "holdout"}

    def test_split_ratios(self):
        from app.services.full_cycle_backtester import FullCycleConfig, SegmentSplitter

        ohlcv = self._make_ohlcv(1000)
        config = FullCycleConfig()
        segments = SegmentSplitter.split(ohlcv, config)
        total = sum(len(v) for v in segments.values())
        assert total == 1000

    def test_split_no_overlap(self):
        from app.services.full_cycle_backtester import (
            FullCycleConfig,
            SegmentSplitter,
            SEGMENT_NAMES,
        )

        ohlcv = self._make_ohlcv(1000)
        config = FullCycleConfig()
        segments = SegmentSplitter.split(ohlcv, config)

        for i in range(len(SEGMENT_NAMES) - 1):
            curr = segments[SEGMENT_NAMES[i]]
            next_seg = segments[SEGMENT_NAMES[i + 1]]
            assert curr[-1][0] < next_seg[0][0], (
                f"{SEGMENT_NAMES[i]} last_ts >= {SEGMENT_NAMES[i + 1]} first_ts"
            )

    def test_split_empty_data_raises(self):
        from app.services.full_cycle_backtester import FullCycleConfig, SegmentSplitter

        config = FullCycleConfig()
        with pytest.raises(ValueError, match="Cannot split empty"):
            SegmentSplitter.split([], config)

    def test_split_too_small_data_raises(self):
        from app.services.full_cycle_backtester import FullCycleConfig, SegmentSplitter

        ohlcv = self._make_ohlcv(50)
        config = FullCycleConfig()
        with pytest.raises(ValueError, match="minimum is"):
            SegmentSplitter.split(ohlcv, config)

    def test_split_invalid_ratios_raises(self):
        from app.services.full_cycle_backtester import FullCycleConfig, SegmentSplitter

        config = FullCycleConfig(
            train_ratio=0.5, forward1_ratio=0.5, forward2_ratio=0.5, holdout_ratio=0.5
        )
        with pytest.raises(ValueError, match="sum to 1.0"):
            SegmentSplitter.split(self._make_ohlcv(1000), config)

    def test_leakage_check_pass(self):
        from app.services.full_cycle_backtester import FullCycleConfig, SegmentSplitter

        ohlcv = self._make_ohlcv(1000)
        config = FullCycleConfig()
        segments = SegmentSplitter.split(ohlcv, config)
        is_clean, violations = SegmentSplitter.validate_no_leakage(segments)
        assert is_clean
        assert violations == []

    def test_build_segment_results(self):
        from app.services.full_cycle_backtester import FullCycleConfig, SegmentSplitter

        ohlcv = self._make_ohlcv(1000)
        config = FullCycleConfig()
        segments = SegmentSplitter.split(ohlcv, config)
        results = SegmentSplitter.build_segment_results(segments, lookback=50)

        assert set(results.keys()) == {"train", "forward_1", "forward_2", "holdout"}
        assert results["train"].lookback_excluded_bars == 0
        assert results["forward_1"].lookback_excluded_bars == 50
        assert results["holdout"].bars > 0


class TestFullCycleConfig:
    def test_valid_default_config(self):
        from app.services.full_cycle_backtester import FullCycleConfig

        config = FullCycleConfig()
        errors = config.validate()
        assert errors == []

    def test_invalid_ratio_sum(self):
        from app.services.full_cycle_backtester import FullCycleConfig

        config = FullCycleConfig(train_ratio=0.3)
        errors = config.validate()
        assert any("sum to 1.0" in e for e in errors)

    def test_negative_ratio_rejected(self):
        from app.services.full_cycle_backtester import FullCycleConfig

        config = FullCycleConfig(
            train_ratio=-0.1, forward1_ratio=0.5, forward2_ratio=0.3, holdout_ratio=0.3
        )
        errors = config.validate()
        assert any("must be > 0" in e for e in errors)


class TestFullCycleResult:
    def test_summary_returns_dict(self):
        from app.services.full_cycle_backtester import FullCycleResult

        result = FullCycleResult()
        summary = result.summary()
        assert "verdict" in summary
        assert summary["verdict"] == "PENDING"

    def test_overall_fitness_computation(self):
        from app.services.full_cycle_backtester import FullCycleBacktester

        fitness = FullCycleBacktester._compute_overall_fitness(
            {
                "train": 0.5,
                "forward_1": 0.4,
                "forward_2": 0.3,
            }
        )
        # (0.40*0.5 + 0.35*0.4 + 0.25*0.3) / (0.40+0.35+0.25)
        expected = (0.20 + 0.14 + 0.075) / 1.0
        assert abs(fitness - expected) < 0.01


# ═══════════════════════════════════════════════════════════════════════
# G3: HistoryDataManager Contract Verification
# ═══════════════════════════════════════════════════════════════════════


class TestHistoryDataManagerContracts:
    """Verify public interface contracts without DB."""

    def test_ingestion_result_defaults(self):
        from app.services.history_data_manager import IngestionResult

        result = IngestionResult()
        assert result.candles_fetched == 0
        assert result.candles_inserted == 0

    def test_coverage_report_defaults(self):
        from app.services.history_data_manager import CoverageReport

        report = CoverageReport()
        assert report.coverage_pct == 0.0
        assert report.gap_count == 0

    def test_coverage_report_fields(self):
        from app.services.history_data_manager import CoverageReport

        report = CoverageReport(
            exchange="binance",
            symbol="SOL/USDT",
            timeframe="1h",
            total_candles=9600,
            expected_candles=9600,
            coverage_pct=100.0,
            days_covered=400.0,
        )
        assert report.coverage_pct == 100.0
        assert report.days_covered == 400.0

    def test_target_candle_constant(self):
        from app.services.history_data_manager import TARGET_CANDLES_1H

        assert TARGET_CANDLES_1H == 9600

    def test_timeframe_ms_map(self):
        from app.services.history_data_manager import TIMEFRAME_MS

        assert TIMEFRAME_MS["1h"] == 3_600_000
        assert TIMEFRAME_MS["1d"] == 86_400_000

    def test_manager_instantiation(self):
        from app.services.history_data_manager import HistoryDataManager

        mgr = HistoryDataManager()
        assert mgr is not None


class TestOhlcvHistoryModel:
    """Verify OhlcvHistory model structure."""

    def test_tablename(self):
        from app.models.ohlcv_history import OhlcvHistory

        assert OhlcvHistory.__tablename__ == "ohlcv_history"

    def test_columns_present(self):
        from app.models.ohlcv_history import OhlcvHistory

        columns = {c.name for c in OhlcvHistory.__table__.columns}
        required = {
            "id",
            "exchange",
            "symbol",
            "timeframe",
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "event_week_flag",
            "macro_event_type",
            "high_volatility_flag",
            "ingested_at",
        }
        assert required.issubset(columns)

    def test_unique_constraint_exists(self):
        from app.models.ohlcv_history import OhlcvHistory

        constraint_names = [
            c.name for c in OhlcvHistory.__table__.constraints if hasattr(c, "name") and c.name
        ]
        assert "uq_ohlcv_canonical_slot" in constraint_names


# ═══════════════════════════════════════════════════════════════════════
# G4: Observation Chain Model & Service Verification
# ═══════════════════════════════════════════════════════════════════════


class TestObservationChainModel:
    """Verify ObservationChainEntry model structure."""

    def test_tablename(self):
        from app.models.observation_chain import ObservationChainEntry

        assert ObservationChainEntry.__tablename__ == "observation_chain"

    def test_columns_present(self):
        from app.models.observation_chain import ObservationChainEntry

        columns = {c.name for c in ObservationChainEntry.__table__.columns}
        required = {
            "id",
            "observed_at",
            "observation_type",
            "symbol",
            "exchange",
            "close_price",
            "regime_v1",
            "regime_v2",
            "realized_volatility",
            "choppiness_index",
            "active_strategy",
            "signal_count_24h",
            "consensus_ratio_24h",
            "ohlcv_coverage_pct",
            "shadow_task_healthy",
            "ppf_baseline_active",
            "novelty_detected",
            "anomaly_flag",
            "notes",
            "created_at",
        }
        assert required.issubset(columns)

    def test_indexes_defined(self):
        from app.models.observation_chain import ObservationChainEntry

        index_names = {idx.name for idx in ObservationChainEntry.__table__.indexes}
        assert "ix_obs_chain_symbol_ts" in index_names
        assert "ix_obs_chain_type" in index_names
        assert "ix_obs_chain_regime" in index_names

    def test_model_registered_in_init(self):
        from app.models import ObservationChainEntry

        assert ObservationChainEntry.__tablename__ == "observation_chain"


class TestObservationChainServiceContracts:
    """Verify ObservationChainService data contracts without DB."""

    def test_snapshot_defaults(self):
        from app.services.observation_chain_service import ObservationSnapshot

        snap = ObservationSnapshot()
        assert snap.symbol == ""
        assert snap.exchange == "binance"
        assert snap.observation_type == "hourly"
        assert snap.novelty_detected is False
        assert snap.close_price is None

    def test_snapshot_custom_values(self):
        from app.services.observation_chain_service import ObservationSnapshot

        snap = ObservationSnapshot(
            symbol="SOL/USDT",
            regime_v1="bull",
            regime_v2="trending",
            close_price=150.0,
            novelty_detected=True,
        )
        assert snap.symbol == "SOL/USDT"
        assert snap.regime_v1 == "bull"
        assert snap.close_price == 150.0
        assert snap.novelty_detected is True

    def test_trend_summary_defaults(self):
        from app.services.observation_chain_service import TrendSummary

        ts = TrendSummary()
        assert ts.observation_count == 0
        assert ts.regime_v1_distribution == {}
        assert ts.price_change_pct is None
        assert ts.novelty_count == 0
        assert ts.anomaly_flags == []
        assert ts.regime_transitions_v1 == 0

    def test_service_instantiation(self):
        from app.services.observation_chain_service import ObservationChainService

        svc = ObservationChainService()
        assert svc is not None


# ═══════════════════════════════════════════════════════════════════════
# G5: Case Accumulation Rules Verification
# ═══════════════════════════════════════════════════════════════════════


class TestCaseAccumulationEnums:
    """Verify enum definitions and values."""

    def test_case_types(self):
        from app.services.case_accumulation import CaseType

        assert set(CaseType) == {
            CaseType.NOVELTY,
            CaseType.REGIME_SHIFT,
            CaseType.SIGNAL_CLUSTER,
            CaseType.ANOMALY,
        }

    def test_case_statuses(self):
        from app.services.case_accumulation import CaseStatus

        assert set(CaseStatus) == {
            CaseStatus.OPEN,
            CaseStatus.ACCUMULATING,
            CaseStatus.RESOLVED,
            CaseStatus.CLOSED,
        }

    def test_case_resolutions(self):
        from app.services.case_accumulation import CaseResolution

        assert CaseResolution.TRUE_POSITIVE.value == "TP"
        assert CaseResolution.FALSE_POSITIVE.value == "FP"
        assert CaseResolution.CONFIRMED.value == "CONFIRMED"
        assert CaseResolution.REVERTED.value == "REVERTED"


class TestAccumulationRules:
    """Verify accumulation rule registry."""

    def test_all_case_types_have_rules(self):
        from app.services.case_accumulation import CaseType, ACCUMULATION_RULES

        for ct in CaseType:
            assert ct in ACCUMULATION_RULES, f"Missing rule for {ct}"

    def test_novelty_rule(self):
        from app.services.case_accumulation import CaseType, ACCUMULATION_RULES

        rule = ACCUMULATION_RULES[CaseType.NOVELTY]
        assert rule.observation_window_bars == 20
        assert rule.auto_resolve is True
        assert rule.resolution_method == "window_expiry"

    def test_regime_shift_rule(self):
        from app.services.case_accumulation import CaseType, ACCUMULATION_RULES

        rule = ACCUMULATION_RULES[CaseType.REGIME_SHIFT]
        assert rule.observation_window_bars == 48
        assert rule.min_evidence_count == 3

    def test_anomaly_rule_manual(self):
        from app.services.case_accumulation import CaseType, ACCUMULATION_RULES

        rule = ACCUMULATION_RULES[CaseType.ANOMALY]
        assert rule.auto_resolve is False
        assert rule.resolution_method == "manual"

    def test_get_rule_valid(self):
        from app.services.case_accumulation import CaseType, get_rule

        rule = get_rule(CaseType.SIGNAL_CLUSTER)
        assert rule.observation_window_bars == 24

    def test_get_rule_invalid_raises(self):
        from app.services.case_accumulation import get_rule

        with pytest.raises(ValueError, match="No accumulation rule"):
            get_rule("NONEXISTENT")


class TestCaseRecord:
    """Verify CaseRecord lifecycle methods."""

    def test_defaults(self):
        from app.services.case_accumulation import CaseRecord, CaseStatus

        rec = CaseRecord()
        assert rec.status == CaseStatus.OPEN
        assert rec.bars_elapsed == 0
        assert rec.evidence == []

    def test_window_not_complete(self):
        from app.services.case_accumulation import CaseRecord

        rec = CaseRecord(observation_window_bars=20, bars_elapsed=10)
        assert rec.is_window_complete() is False

    def test_window_complete(self):
        from app.services.case_accumulation import CaseRecord

        rec = CaseRecord(observation_window_bars=20, bars_elapsed=20)
        assert rec.is_window_complete() is True

    def test_can_auto_resolve_novelty(self):
        from app.services.case_accumulation import CaseRecord, CaseType

        rec = CaseRecord(
            case_type=CaseType.NOVELTY,
            observation_window_bars=20,
            bars_elapsed=20,
        )
        assert rec.can_auto_resolve() is True

    def test_cannot_auto_resolve_anomaly(self):
        from app.services.case_accumulation import CaseRecord, CaseType

        rec = CaseRecord(
            case_type=CaseType.ANOMALY,
            observation_window_bars=72,
            bars_elapsed=72,
        )
        assert rec.can_auto_resolve() is False


class TestCaseEvaluator:
    """Verify case evaluation logic."""

    def test_evaluate_novelty_tp(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseResolution,
            CaseEvaluator,
        )

        rec = CaseRecord(
            case_type=CaseType.NOVELTY,
            trigger_price=100.0,
            resolution_price=104.0,
        )
        resolution, reason = CaseEvaluator.evaluate_novelty(rec)
        assert resolution == CaseResolution.TRUE_POSITIVE
        assert "4.00%" in reason

    def test_evaluate_novelty_fp(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseResolution,
            CaseEvaluator,
        )

        rec = CaseRecord(
            case_type=CaseType.NOVELTY,
            trigger_price=100.0,
            resolution_price=101.0,
        )
        resolution, reason = CaseEvaluator.evaluate_novelty(rec)
        assert resolution == CaseResolution.FALSE_POSITIVE

    def test_evaluate_novelty_missing_price(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseResolution,
            CaseEvaluator,
        )

        rec = CaseRecord(case_type=CaseType.NOVELTY, trigger_price=None)
        resolution, _ = CaseEvaluator.evaluate_novelty(rec)
        assert resolution == CaseResolution.UNRESOLVED

    def test_evaluate_regime_shift_confirmed(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseResolution,
            CaseEvaluator,
        )

        rec = CaseRecord(
            case_type=CaseType.REGIME_SHIFT,
            trigger_reason="bull",
            evidence=[
                {"regime": "bull"},
                {"regime": "bull"},
                {"regime": "bull"},
                {"regime": "bear"},
                {"regime": "bull"},
            ],
        )
        resolution, reason = CaseEvaluator.evaluate_regime_shift(rec)
        assert resolution == CaseResolution.CONFIRMED
        assert "persisted" in reason

    def test_evaluate_regime_shift_reverted(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseResolution,
            CaseEvaluator,
        )

        rec = CaseRecord(
            case_type=CaseType.REGIME_SHIFT,
            trigger_reason="bull",
            evidence=[
                {"regime": "bear"},
                {"regime": "bear"},
                {"regime": "bear"},
                {"regime": "bull"},
                {"regime": "bear"},
            ],
        )
        resolution, _ = CaseEvaluator.evaluate_regime_shift(rec)
        assert resolution == CaseResolution.REVERTED

    def test_evaluate_signal_cluster_positive(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseResolution,
            CaseEvaluator,
        )

        rec = CaseRecord(
            case_type=CaseType.SIGNAL_CLUSTER,
            evidence=[{"pnl": 0.05}, {"pnl": -0.02}, {"pnl": 0.03}],
        )
        resolution, _ = CaseEvaluator.evaluate_signal_cluster(rec)
        assert resolution == CaseResolution.TRUE_POSITIVE

    def test_evaluate_signal_cluster_negative(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseResolution,
            CaseEvaluator,
        )

        rec = CaseRecord(
            case_type=CaseType.SIGNAL_CLUSTER,
            evidence=[{"pnl": -0.05}, {"pnl": -0.02}],
        )
        resolution, _ = CaseEvaluator.evaluate_signal_cluster(rec)
        assert resolution == CaseResolution.FALSE_POSITIVE

    def test_resolve_auto(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseStatus,
            CaseResolution,
            CaseEvaluator,
        )

        rec = CaseRecord(
            case_type=CaseType.NOVELTY,
            observation_window_bars=20,
            bars_elapsed=20,
            trigger_price=100.0,
            resolution_price=95.0,
        )
        evaluator = CaseEvaluator()
        resolved = evaluator.resolve(rec)
        assert resolved.status == CaseStatus.RESOLVED
        assert resolved.resolution == CaseResolution.TRUE_POSITIVE
        assert resolved.resolution_ts is not None

    def test_resolve_skips_incomplete_window(self):
        from app.services.case_accumulation import (
            CaseRecord,
            CaseType,
            CaseStatus,
            CaseEvaluator,
        )

        rec = CaseRecord(
            case_type=CaseType.NOVELTY,
            observation_window_bars=20,
            bars_elapsed=5,
        )
        evaluator = CaseEvaluator()
        result = evaluator.resolve(rec)
        assert result.status == CaseStatus.OPEN
