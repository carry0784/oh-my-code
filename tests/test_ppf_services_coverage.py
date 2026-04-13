"""Baseline coverage tests for PPF service modules.

Covers import, instantiation, and core judgment logic to ensure
coverage threshold is met. All tests are offline (no DB, no network).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# NoveltyJudgmentEngine
# ---------------------------------------------------------------------------


class TestNoveltyJudgmentEngine:
    """Tests for app.services.ppf_novelty_judgment.NoveltyJudgmentEngine."""

    def test_import(self):
        from app.services.ppf_novelty_judgment import (
            NoveltyJudgment,
            NoveltyJudgmentEngine,
            NoveltyJudgmentReport,
        )

        assert NoveltyJudgment is not None
        assert NoveltyJudgmentReport is not None
        assert NoveltyJudgmentEngine is not None

    def test_instantiation_defaults(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        engine = NoveltyJudgmentEngine()
        assert engine._window_bars == 20
        assert engine._disruption_threshold_pct == 3.0

    def test_instantiation_custom(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        engine = NoveltyJudgmentEngine(window_bars=10, disruption_threshold_pct=5.0)
        assert engine._window_bars == 10
        assert engine._disruption_threshold_pct == 5.0

    def test_invalid_window_bars(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        with pytest.raises(ValueError, match="window_bars must be > 0"):
            NoveltyJudgmentEngine(window_bars=0)

    def test_invalid_threshold(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        with pytest.raises(ValueError, match="disruption_threshold_pct must be > 0"):
            NoveltyJudgmentEngine(disruption_threshold_pct=-1.0)

    def test_judge_single_tp(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        engine = NoveltyJudgmentEngine(disruption_threshold_pct=3.0)
        judgment, reason = engine.judge_single(
            close_at_event=100.0,
            close_at_window_end=104.0,  # +4% > 3% threshold
            window_complete=True,
        )
        assert judgment == "TP"
        assert "TP" in reason

    def test_judge_single_fp(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        engine = NoveltyJudgmentEngine(disruption_threshold_pct=3.0)
        judgment, reason = engine.judge_single(
            close_at_event=100.0,
            close_at_window_end=101.0,  # +1% < 3% threshold
            window_complete=True,
        )
        assert judgment == "FP"
        assert "FP" in reason

    def test_judge_single_unresolved_no_window(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        engine = NoveltyJudgmentEngine()
        judgment, reason = engine.judge_single(
            close_at_event=100.0,
            close_at_window_end=105.0,
            window_complete=False,
        )
        assert judgment == "UNRESOLVED"
        assert "UR-C3" in reason

    def test_judge_single_unresolved_none_end(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        engine = NoveltyJudgmentEngine()
        judgment, reason = engine.judge_single(
            close_at_event=100.0,
            close_at_window_end=None,
            window_complete=True,
        )
        assert judgment == "UNRESOLVED"
        assert "UR-C1" in reason

    def test_judge_single_unresolved_invalid_price(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        engine = NoveltyJudgmentEngine()
        judgment, reason = engine.judge_single(
            close_at_event=0.0,
            close_at_window_end=100.0,
            window_complete=True,
        )
        assert judgment == "UNRESOLVED"
        assert "UR-C1" in reason

    def test_judge_single_negative_change_tp(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentEngine

        engine = NoveltyJudgmentEngine(disruption_threshold_pct=3.0)
        judgment, _ = engine.judge_single(
            close_at_event=100.0,
            close_at_window_end=96.0,  # -4% > 3% threshold (absolute)
            window_complete=True,
        )
        assert judgment == "TP"

    def test_novelty_judgment_dataclass(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgment

        j = NoveltyJudgment(
            event_bar_index=5,
            event_timestamp_ms=1000000,
            close_at_event=100.0,
            close_at_window_end=104.0,
            window_bars=20,
            price_change_pct=4.0,
            judgment="TP",
            judgment_reason="test",
        )
        assert j.judgment == "TP"
        assert j.event_bar_index == 5

    def test_novelty_judgment_report_defaults(self):
        from app.services.ppf_novelty_judgment import NoveltyJudgmentReport

        report = NoveltyJudgmentReport()
        assert report.total_events == 0
        assert report.fpr == 0.0
        assert report.judgments == []


# ---------------------------------------------------------------------------
# PPFReplayEngine
# ---------------------------------------------------------------------------


class TestPPFReplayEngine:
    """Tests for app.services.ppf_replay_engine.PPFReplayEngine."""

    def test_import(self):
        from app.services.ppf_replay_engine import (
            PPFBarResult,
            PPFReplayEngine,
            PPFReplayResult,
        )

        assert PPFBarResult is not None
        assert PPFReplayResult is not None
        assert PPFReplayEngine is not None

    def test_instantiation_defaults(self):
        from app.services.ppf_replay_engine import PPFReplayEngine

        engine = PPFReplayEngine()
        assert engine._params is not None
        assert engine.MIN_WARMUP_BARS == 43

    def test_replay_result_defaults(self):
        from app.services.ppf_replay_engine import PPFReplayResult

        result = PPFReplayResult()
        assert result.total_bars == 0
        assert result.deny_rate == 0.0
        assert result.novelty_events == []

    def test_bar_result_creation(self):
        from app.services.ppf_replay_engine import PPFBarResult

        bar = PPFBarResult(
            bar_index=0,
            timestamp_ms=1000000,
            ppf_state="IDLE",
            allow_entry=False,
            deny_reason_code="CONSTITUTION_DEACTIVATED",
            regime_novelty_flag=False,
            observation_snapshot={},
            interpretation_snapshot={},
            close_price=100.0,
        )
        assert bar.bar_index == 0
        assert not bar.allow_entry


# ---------------------------------------------------------------------------
# PPFBacktestComparator
# ---------------------------------------------------------------------------


class TestPPFBacktestComparator:
    """Tests for app.services.ppf_backtest_comparator."""

    def test_import(self):
        from app.services.ppf_backtest_comparator import (
            ComparisonMetric,
            PPFBacktestComparator,
            PPFComparisonReport,
        )

        assert ComparisonMetric is not None
        assert PPFComparisonReport is not None
        assert PPFBacktestComparator is not None

    def test_comparison_metric_creation(self):
        from app.services.ppf_backtest_comparator import ComparisonMetric

        m = ComparisonMetric(
            metric_name="fpr",
            backtest_value=0.2,
            live_value=0.25,
            delta_abs=0.05,
            delta_pct=25.0,
            within_tolerance=True,
            tolerance_pct=0.1,
        )
        assert m.metric_name == "fpr"
        assert m.within_tolerance


# ---------------------------------------------------------------------------
# PPFBaselineManager
# ---------------------------------------------------------------------------


class TestPPFBaselineManager:
    """Tests for app.services.ppf_baseline_manager."""

    def test_import(self):
        from app.services.ppf_baseline_manager import (
            PPFBacktestBaseline,
            PPFBaselineManager,
        )

        assert PPFBacktestBaseline is not None
        assert PPFBaselineManager is not None


# ---------------------------------------------------------------------------
# PPFIntegratedBacktester
# ---------------------------------------------------------------------------


class TestPPFIntegratedBacktester:
    """Tests for app.services.ppf_integrated_backtester."""

    def test_import(self):
        from app.services.ppf_integrated_backtester import (
            PPFIntegratedBacktester,
        )

        assert PPFIntegratedBacktester is not None
