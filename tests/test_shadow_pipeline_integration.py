"""CR-048 Follow-Up 2A P2 — ShadowPipelineOrchestrator integration tests.

Pure unit tests with mocks. No DB fixtures, no ORM mapper initialization.
Tests the orchestration flow: adapter → shadow pipeline → observation → write eval.

Controlling spec: CR-048 2A P2 ONLY GO

Invariants verified:
  - execute_bounded_write is NEVER called
  - rollback_bounded_write is NEVER called
  - Per-symbol failure does NOT block next symbol
  - Quality gate: STALE → SKIP_STALE, UNAVAILABLE → SKIP_UNAVAILABLE
  - adx_14 absence (PR #59 not merged) does not break orchestration
  - Result normalization: WOULD_WRITE / NOOP / SKIP_* / ERROR_INTERNAL
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.asset import AssetClass, AssetSector
from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    MarketDataSnapshot,
)
from app.services.pipeline_shadow_runner import (
    ComparisonVerdict,
    ShadowRunResult,
)
from app.services.data_provider import DataQualityDecision
from app.services.screening_qualification_pipeline import (
    PipelineEvidence,
    PipelineOutput,
    PipelineResult,
    PipelineVerdict,
)
from app.services.shadow_pipeline_orchestrator import (
    OrchestratorOutcome,
    OrchestrationResult,
    ShadowPipelineOrchestrator,
)


# ── Test fixtures ────────────────────────────────────────────────


def _make_market(
    symbol: str = "SOL/USDT",
    quality: DataQuality = DataQuality.HIGH,
    price: float = 150.0,
    adx: float | None = 25.0,
) -> MarketDataSnapshot:
    return MarketDataSnapshot(
        symbol=symbol,
        timestamp=datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc),
        price_usd=price,
        avg_daily_volume_usd=5_000_000.0,
        spread_pct=0.05,
        atr_pct=0.03,
        adx=adx,
        price_vs_200ma=1.05,
        quality=quality,
    )


def _make_backtest(
    symbol: str = "SOL/USDT",
    quality: DataQuality = DataQuality.HIGH,
) -> BacktestReadiness:
    return BacktestReadiness(
        symbol=symbol,
        available_bars=1500,
        sharpe_ratio=1.0,
        missing_data_pct=1.0,
        quality=quality,
    )


def _make_shadow_result(
    symbol: str = "SOL/USDT",
    verdict: PipelineVerdict = PipelineVerdict.QUALIFIED,
) -> ShadowRunResult:
    pipeline_result = PipelineResult(symbol=symbol, verdict=verdict)
    pipeline_evidence = PipelineEvidence(symbol=symbol, transform_decision=DataQualityDecision.OK)
    return ShadowRunResult(
        symbol=symbol,
        pipeline_output=PipelineOutput(result=pipeline_result, evidence=pipeline_evidence),
        shadow_timestamp=datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc),
        input_fingerprint="abcd1234abcd1234",
    )


def _make_mock_receipt(
    verdict: str = "would_write",
    intended_value: str = "pass",
) -> MagicMock:
    receipt = MagicMock()
    receipt.verdict = verdict
    receipt.intended_value = intended_value
    receipt.receipt_id = str(uuid.uuid4())
    return receipt


# ── Quality Gate Tests ───────────────────────────────────────────


class TestQualityGate:
    """Verify fail-closed quality gating before pipeline execution."""

    @pytest.mark.asyncio
    async def test_unavailable_market_skips(self):
        """UNAVAILABLE market data → SKIP_UNAVAILABLE, pipeline NOT called."""
        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(
            return_value=_make_market(quality=DataQuality.UNAVAILABLE)
        )
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        db = AsyncMock()

        result = await orch.run_single(db, "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.SKIP_UNAVAILABLE
        assert result.shadow_result is None

    @pytest.mark.asyncio
    async def test_unavailable_backtest_skips(self):
        """UNAVAILABLE backtest → SKIP_UNAVAILABLE."""
        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(return_value=_make_market())
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest(quality=DataQuality.UNAVAILABLE))

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        db = AsyncMock()

        result = await orch.run_single(db, "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.SKIP_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_stale_market_skips(self):
        """STALE market data → SKIP_STALE."""
        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(return_value=_make_market(quality=DataQuality.STALE))
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        db = AsyncMock()

        result = await orch.run_single(db, "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.SKIP_STALE

    @pytest.mark.asyncio
    async def test_high_quality_proceeds(self):
        """HIGH quality on both inputs → pipeline proceeds (not skipped)."""
        outcome = ShadowPipelineOrchestrator._check_quality_gate(
            _make_market(quality=DataQuality.HIGH),
            _make_backtest(quality=DataQuality.HIGH),
        )
        assert outcome is None  # None means proceed


# ── Happy Path Tests ─────────────────────────────────────────────


class TestHappyPath:
    """Verify full orchestration produces expected outcomes."""

    @pytest.mark.asyncio
    @patch("app.services.shadow_pipeline_orchestrator.evaluate_shadow_write")
    @patch("app.services.shadow_pipeline_orchestrator.record_shadow_observation")
    @patch("app.services.shadow_pipeline_orchestrator.fetch_existing_for_comparison")
    @patch("app.services.shadow_pipeline_orchestrator.compare_shadow_to_existing")
    @patch("app.services.shadow_pipeline_orchestrator.run_shadow_pipeline")
    async def test_would_write_outcome(
        self,
        mock_run,
        mock_compare,
        mock_fetch_existing,
        mock_record_obs,
        mock_eval_write,
    ):
        """Qualified shadow + would_write verdict → WOULD_WRITE outcome."""
        shadow = _make_shadow_result(verdict=PipelineVerdict.QUALIFIED)
        compared = ShadowRunResult(
            symbol="SOL/USDT",
            pipeline_output=shadow.pipeline_output,
            shadow_timestamp=shadow.shadow_timestamp,
            input_fingerprint=shadow.input_fingerprint,
            comparison_verdict=ComparisonVerdict.INSUFFICIENT_OPERATIONAL,
        )

        mock_run.return_value = shadow
        mock_compare.return_value = compared
        mock_fetch_existing.return_value = (MagicMock(), MagicMock())
        mock_record_obs.return_value = MagicMock(id=42)
        mock_eval_write.return_value = _make_mock_receipt(
            verdict="would_write", intended_value="pass"
        )

        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(return_value=_make_market())
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        db = AsyncMock()

        result = await orch.run_single(db, "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.WOULD_WRITE
        assert result.observation_id == 42
        assert result.receipt_id is not None
        assert result.intended_value == "pass"

    @pytest.mark.asyncio
    @patch("app.services.shadow_pipeline_orchestrator.evaluate_shadow_write")
    @patch("app.services.shadow_pipeline_orchestrator.record_shadow_observation")
    @patch("app.services.shadow_pipeline_orchestrator.fetch_existing_for_comparison")
    @patch("app.services.shadow_pipeline_orchestrator.compare_shadow_to_existing")
    @patch("app.services.shadow_pipeline_orchestrator.run_shadow_pipeline")
    async def test_noop_outcome_already_matched(
        self,
        mock_run,
        mock_compare,
        mock_fetch_existing,
        mock_record_obs,
        mock_eval_write,
    ):
        """Already-matched write → NOOP outcome."""
        shadow = _make_shadow_result()
        mock_run.return_value = shadow
        mock_compare.return_value = shadow
        mock_fetch_existing.return_value = (MagicMock(), MagicMock())
        mock_record_obs.return_value = MagicMock(id=99)
        mock_eval_write.return_value = _make_mock_receipt(
            verdict="would_skip", intended_value="pass"
        )

        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(return_value=_make_market())
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        result = await orch.run_single(AsyncMock(), "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.NOOP

    @pytest.mark.asyncio
    @patch("app.services.shadow_pipeline_orchestrator.evaluate_shadow_write")
    @patch("app.services.shadow_pipeline_orchestrator.record_shadow_observation")
    @patch("app.services.shadow_pipeline_orchestrator.fetch_existing_for_comparison")
    @patch("app.services.shadow_pipeline_orchestrator.compare_shadow_to_existing")
    @patch("app.services.shadow_pipeline_orchestrator.run_shadow_pipeline")
    async def test_blocked_write_is_noop(
        self,
        mock_run,
        mock_compare,
        mock_fetch_existing,
        mock_record_obs,
        mock_eval_write,
    ):
        """Blocked write verdict → NOOP (not ERROR)."""
        shadow = _make_shadow_result()
        mock_run.return_value = shadow
        mock_compare.return_value = shadow
        mock_fetch_existing.return_value = (MagicMock(), MagicMock())
        mock_record_obs.return_value = MagicMock(id=1)
        mock_eval_write.return_value = _make_mock_receipt(verdict="blocked")

        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(return_value=_make_market())
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        result = await orch.run_single(AsyncMock(), "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.NOOP


# ── Error Handling Tests ─────────────────────────────────────────


class TestErrorHandling:
    """Verify fail-closed behavior on exceptions."""

    @pytest.mark.asyncio
    async def test_adapter_exception_returns_error(self):
        """Adapter raising → ERROR_INTERNAL, not propagated."""
        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(side_effect=RuntimeError("DB down"))
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        result = await orch.run_single(AsyncMock(), "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.ERROR_INTERNAL
        assert "RuntimeError" in result.error_detail

    @pytest.mark.asyncio
    @patch("app.services.shadow_pipeline_orchestrator.run_shadow_pipeline")
    async def test_pipeline_exception_returns_error(self, mock_run):
        """Shadow pipeline raising → ERROR_INTERNAL."""
        mock_run.side_effect = ValueError("bad input")

        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(return_value=_make_market())
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        result = await orch.run_single(AsyncMock(), "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.ERROR_INTERNAL
        assert "ValueError" in result.error_detail

    @pytest.mark.asyncio
    @patch("app.services.shadow_pipeline_orchestrator.evaluate_shadow_write")
    @patch("app.services.shadow_pipeline_orchestrator.record_shadow_observation")
    @patch("app.services.shadow_pipeline_orchestrator.fetch_existing_for_comparison")
    @patch("app.services.shadow_pipeline_orchestrator.compare_shadow_to_existing")
    @patch("app.services.shadow_pipeline_orchestrator.run_shadow_pipeline")
    async def test_null_receipt_returns_error(
        self,
        mock_run,
        mock_compare,
        mock_fetch_existing,
        mock_record_obs,
        mock_eval_write,
    ):
        """evaluate_shadow_write returning None → ERROR_INTERNAL."""
        shadow = _make_shadow_result()
        mock_run.return_value = shadow
        mock_compare.return_value = shadow
        mock_fetch_existing.return_value = (MagicMock(), MagicMock())
        mock_record_obs.return_value = MagicMock(id=1)
        mock_eval_write.return_value = None  # receipt creation failed

        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(return_value=_make_market())
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        result = await orch.run_single(AsyncMock(), "SOL/USDT")

        assert result.outcome == OrchestratorOutcome.ERROR_INTERNAL


# ── Per-Symbol Isolation Tests ───────────────────────────────────


class TestPerSymbolIsolation:
    """Verify per-symbol failure does NOT block next symbol."""

    @pytest.mark.asyncio
    async def test_batch_first_fails_second_succeeds(self):
        """First symbol errors, second symbol proceeds independently."""
        call_count = 0

        async def _mock_get_market_data(_db: Any, symbol: str, _now: Any = None):
            nonlocal call_count
            call_count += 1
            if symbol == "FAIL/USDT":
                raise RuntimeError("simulated failure")
            return _make_market(symbol=symbol)

        adapter = AsyncMock()
        adapter.get_market_data = _mock_get_market_data
        stub = MagicMock()
        stub.get_readiness = MagicMock(side_effect=lambda s: _make_backtest(symbol=s))

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        db = AsyncMock()

        results = await orch.run_batch(db, ["FAIL/USDT", "SOL/USDT"])

        assert len(results) == 2
        assert results[0].symbol == "FAIL/USDT"
        assert results[0].outcome == OrchestratorOutcome.ERROR_INTERNAL
        # SOL/USDT was NOT blocked by FAIL/USDT
        assert results[1].symbol == "SOL/USDT"
        assert results[1].outcome != OrchestratorOutcome.ERROR_INTERNAL

    @pytest.mark.asyncio
    async def test_batch_all_unavailable(self):
        """All symbols unavailable → all SKIP, no crash."""
        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(
            return_value=_make_market(quality=DataQuality.UNAVAILABLE)
        )
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        results = await orch.run_batch(AsyncMock(), ["SOL/USDT", "BTC/USDT"])

        assert all(r.outcome == OrchestratorOutcome.SKIP_UNAVAILABLE for r in results)

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty(self):
        """Empty symbol list → empty results, no error."""
        orch = ShadowPipelineOrchestrator()
        results = await orch.run_batch(AsyncMock(), [])
        assert results == []


# ── ADX PR #59 Independence Tests ────────────────────────────────


class TestADXIndependence:
    """Verify orchestrator works when adx_14 persistence (PR #59) is NOT merged."""

    @pytest.mark.asyncio
    async def test_adx_none_does_not_crash(self):
        """adx=None in market data → quality gate proceeds, no crash."""
        adapter = AsyncMock()
        adapter.get_market_data = AsyncMock(return_value=_make_market(adx=None))
        stub = MagicMock()
        stub.get_readiness = MagicMock(return_value=_make_backtest())

        orch = ShadowPipelineOrchestrator(market_adapter=adapter, backtest_stub=stub)
        result = await orch.run_single(AsyncMock(), "SOL/USDT")

        # Should NOT be SKIP (quality is still HIGH)
        # Might be ERROR_INTERNAL due to downstream pipeline handling adx=None
        # but orchestrator itself must not crash
        assert result.outcome in (
            OrchestratorOutcome.WOULD_WRITE,
            OrchestratorOutcome.NOOP,
            OrchestratorOutcome.ERROR_INTERNAL,
        )

    def test_market_snapshot_accepts_none_adx(self):
        """MarketDataSnapshot with adx=None is valid (PR #59 not needed)."""
        snap = _make_market(adx=None)
        assert snap.adx is None
        assert snap.quality == DataQuality.HIGH


# ── Outcome Normalization Tests ──────────────────────────────────


class TestOutcomeNormalization:
    """Verify _normalise_outcome mapping correctness."""

    def test_would_write(self):
        from app.services.shadow_write_service import WriteVerdict

        assert (
            ShadowPipelineOrchestrator._normalise_outcome(WriteVerdict.WOULD_WRITE)
            == OrchestratorOutcome.WOULD_WRITE
        )

    def test_would_skip(self):
        from app.services.shadow_write_service import WriteVerdict

        assert (
            ShadowPipelineOrchestrator._normalise_outcome(WriteVerdict.WOULD_SKIP)
            == OrchestratorOutcome.NOOP
        )

    def test_blocked(self):
        from app.services.shadow_write_service import WriteVerdict

        assert (
            ShadowPipelineOrchestrator._normalise_outcome(WriteVerdict.BLOCKED)
            == OrchestratorOutcome.NOOP
        )

    def test_none_verdict(self):
        assert (
            ShadowPipelineOrchestrator._normalise_outcome(None)
            == OrchestratorOutcome.ERROR_INTERNAL
        )


# ── Enum Completeness Tests ──────────────────────────────────────


class TestOrchestratorOutcomeEnum:
    """Verify P2 result enum covers all required values."""

    def test_all_values_present(self):
        expected = {"would_write", "noop", "skip_stale", "skip_unavailable", "error_internal"}
        actual = {v.value for v in OrchestratorOutcome}
        assert actual == expected

    def test_count(self):
        assert len(OrchestratorOutcome) == 5


# ── No Execute / No Rollback Verification ────────────────────────


class TestNoExecuteNoRollback:
    """Verify execute_bounded_write and rollback_bounded_write are NOT used."""

    def test_no_execute_import(self):
        """execute_bounded_write is not callable from orchestrator module."""
        import app.services.shadow_pipeline_orchestrator as mod

        assert not hasattr(mod, "execute_bounded_write")

    def test_no_rollback_import(self):
        """rollback_bounded_write is not callable from orchestrator module."""
        import app.services.shadow_pipeline_orchestrator as mod

        assert not hasattr(mod, "rollback_bounded_write")


# ── OrchestrationResult Contract Tests ───────────────────────────


class TestOrchestrationResultContract:
    """Verify OrchestrationResult is frozen and carries expected fields."""

    def test_frozen(self):
        result = OrchestrationResult(symbol="SOL/USDT", outcome=OrchestratorOutcome.NOOP)
        with pytest.raises(AttributeError):
            result.symbol = "BTC/USDT"  # type: ignore[misc]

    def test_defaults(self):
        result = OrchestrationResult(
            symbol="SOL/USDT", outcome=OrchestratorOutcome.SKIP_UNAVAILABLE
        )
        assert result.shadow_result is None
        assert result.write_verdict is None
        assert result.intended_value is None
        assert result.observation_id is None
        assert result.receipt_id is None
        assert result.error_detail is None

    def test_error_has_detail(self):
        result = OrchestrationResult(
            symbol="SOL/USDT",
            outcome=OrchestratorOutcome.ERROR_INTERNAL,
            error_detail="RuntimeError: boom",
        )
        assert "RuntimeError" in result.error_detail
