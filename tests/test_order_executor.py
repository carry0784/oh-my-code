"""
K-Dexter Order Executor Tests

Tests the External Caller (OrderExecutor) layer:
  AXIS 1: Execute Flow (dry_run, result recording, lineage)
  AXIS 2: Safety Checks (submit_ready, exchange allowlist, idempotency)
  AXIS 3: Error Handling (timeout, exchange error, error recording)
  AXIS 4: Boundary (no ledger write, append-only, no delete)
  AXIS 5: Audit Trail (history, order lookup, lineage trace)

Run: pytest tests/test_order_executor.py -v
"""

import sys
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# -- Helpers ---------------------------------------------------------------- #


def _make_executor():
    from app.services.order_executor import OrderExecutor

    return OrderExecutor(default_timeout=5.0)


def _make_submit_proposal(
    submit_ready=True,
    proposal_id="SP-test-001",
    execution_proposal_id="EP-test-001",
    agent_proposal_id="AP-test-001",
    exchange="binance",
    symbol="BTC/USDT",
    status="SUBMIT_RECEIPTED",
    position_size=5000,
):
    """Create a mock submit proposal with required attributes."""
    mock = MagicMock()
    mock.submit_ready = submit_ready
    mock.proposal_id = proposal_id
    mock.execution_proposal_id = execution_proposal_id
    mock.agent_proposal_id = agent_proposal_id
    mock.exchange = exchange
    mock.symbol = symbol
    mock.status = status
    mock.risk_result_summary = {"position_size": position_size}
    return mock


# -- AXIS 1: Execute Flow ------------------------------------------------- #


class TestExecuteFlow:
    """Dry run, result recording, lineage."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_filled(self):
        executor = _make_executor()
        proposal = _make_submit_proposal()
        result = await executor.execute_order(proposal, side="buy", dry_run=True)
        assert result.status == "FILLED"
        assert result.dry_run is True
        assert result.exchange_order_id.startswith("DRY-")

    @pytest.mark.asyncio
    async def test_dry_run_records_history(self):
        executor = _make_executor()
        proposal = _make_submit_proposal()
        await executor.execute_order(proposal, side="buy", dry_run=True)
        assert executor.count == 1

    @pytest.mark.asyncio
    async def test_result_contains_lineage_ids(self):
        executor = _make_executor()
        proposal = _make_submit_proposal()
        result = await executor.execute_order(proposal, side="buy", dry_run=True)
        assert result.submit_proposal_id == "SP-test-001"
        assert result.execution_proposal_id == "EP-test-001"
        assert result.agent_proposal_id == "AP-test-001"

    @pytest.mark.asyncio
    async def test_order_id_format(self):
        executor = _make_executor()
        proposal = _make_submit_proposal()
        result = await executor.execute_order(proposal, side="buy", dry_run=True)
        assert result.order_id.startswith("OX-")

    @pytest.mark.asyncio
    async def test_executed_at_populated(self):
        executor = _make_executor()
        proposal = _make_submit_proposal()
        result = await executor.execute_order(proposal, side="buy", dry_run=True)
        assert result.executed_at != ""
        assert result.created_at != ""

    @pytest.mark.asyncio
    async def test_result_to_dict_serializable(self):
        executor = _make_executor()
        proposal = _make_submit_proposal()
        result = await executor.execute_order(proposal, side="buy", dry_run=True)
        serialized = json.dumps(result.to_dict())
        assert "OX-" in serialized


# -- AXIS 2: Safety Checks ------------------------------------------------ #


class TestSafetyChecks:
    """submit_ready, exchange allowlist, idempotency."""

    @pytest.mark.asyncio
    async def test_submit_ready_false_raises_denied(self):
        from app.services.order_executor import ExecutionDeniedError

        executor = _make_executor()
        proposal = _make_submit_proposal(submit_ready=False, status="SUBMIT_GUARDED")
        with pytest.raises(ExecutionDeniedError, match="submit_ready is False"):
            await executor.execute_order(proposal, side="buy")

    @pytest.mark.asyncio
    async def test_submit_ready_missing_raises_denied(self):
        from app.services.order_executor import ExecutionDeniedError

        executor = _make_executor()
        proposal = MagicMock(spec=[])  # no submit_ready attribute
        proposal.proposal_id = "SP-none"
        with pytest.raises(ExecutionDeniedError):
            await executor.execute_order(proposal, side="buy")

    @pytest.mark.asyncio
    async def test_exchange_unsupported_returns_error(self):
        executor = _make_executor()
        proposal = _make_submit_proposal(exchange="okx")
        result = await executor.execute_order(proposal, side="buy", dry_run=True)
        assert result.status == "ERROR"
        assert "Unsupported exchange" in result.error_detail
        assert "okx" in result.error_detail

    @pytest.mark.asyncio
    async def test_idempotent_same_proposal_returns_cached(self):
        executor = _make_executor()
        proposal = _make_submit_proposal()
        r1 = await executor.execute_order(proposal, side="buy", dry_run=True)
        r2 = await executor.execute_order(proposal, side="buy", dry_run=True)
        assert r1.order_id == r2.order_id
        assert executor.count == 1  # only one entry

    @pytest.mark.asyncio
    async def test_exchange_none_returns_error(self):
        executor = _make_executor()
        proposal = _make_submit_proposal(exchange=None)
        result = await executor.execute_order(proposal, side="buy", dry_run=True)
        assert result.status == "ERROR"


# -- AXIS 3: Error Handling ------------------------------------------------ #


class TestErrorHandling:
    """Timeout, exchange error, error recording."""

    @pytest.mark.asyncio
    async def test_exchange_exception_returns_error(self):
        executor = _make_executor()
        proposal = _make_submit_proposal(proposal_id="SP-err-001")

        mock_exchange = AsyncMock()
        mock_exchange.create_order.side_effect = ConnectionError("Network failure")

        with patch("exchanges.factory.ExchangeFactory") as mock_factory:
            mock_factory.create.return_value = mock_exchange
            result = await executor.execute_order(proposal, side="buy", dry_run=False)

        assert result.status == "ERROR"
        assert "ConnectionError" in result.error_detail
        assert result.dry_run is False

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_status(self):
        executor = OrderExecutorWithShortTimeout()
        proposal = _make_submit_proposal(proposal_id="SP-timeout-001")

        mock_exchange = AsyncMock()

        async def slow_order(**kwargs):
            await asyncio.sleep(10)
            return {}

        mock_exchange.create_order = slow_order

        with patch("exchanges.factory.ExchangeFactory") as mock_factory:
            mock_factory.create.return_value = mock_exchange
            result = await executor.execute_order(proposal, side="buy", dry_run=False)

        assert result.status == "TIMEOUT"
        assert "timeout" in result.error_detail.lower()

    @pytest.mark.asyncio
    async def test_error_detail_populated(self):
        executor = _make_executor()
        proposal = _make_submit_proposal(proposal_id="SP-detail-001")

        mock_exchange = AsyncMock()
        mock_exchange.create_order.side_effect = ValueError("Invalid symbol")

        with patch("exchanges.factory.ExchangeFactory") as mock_factory:
            mock_factory.create.return_value = mock_exchange
            result = await executor.execute_order(proposal, side="sell", dry_run=False)

        assert result.error_detail is not None
        assert "Invalid symbol" in result.error_detail

    @pytest.mark.asyncio
    async def test_error_still_recorded_in_history(self):
        executor = _make_executor()
        proposal = _make_submit_proposal(proposal_id="SP-hist-001")

        mock_exchange = AsyncMock()
        mock_exchange.create_order.side_effect = RuntimeError("Crash")

        with patch("exchanges.factory.ExchangeFactory") as mock_factory:
            mock_factory.create.return_value = mock_exchange
            result = await executor.execute_order(proposal, side="buy", dry_run=False)

        assert executor.count == 1
        assert result.status == "ERROR"


class OrderExecutorWithShortTimeout:
    """Helper: OrderExecutor with very short timeout for testing."""

    def __new__(cls):
        from app.services.order_executor import OrderExecutor

        return OrderExecutor(default_timeout=0.1)


# -- AXIS 4: Boundary ----------------------------------------------------- #


class TestBoundary:
    """No ledger write, append-only, no delete."""

    def test_no_ledger_write_methods(self):
        executor = _make_executor()
        # OrderExecutor must not have methods that write to ledgers
        assert not hasattr(executor, "record_receipt")
        assert not hasattr(executor, "propose_and_guard")
        assert not hasattr(executor, "transition_to")

    def test_history_append_only(self):
        executor = _make_executor()
        assert not hasattr(executor, "delete")
        assert not hasattr(executor, "remove")
        assert not hasattr(executor, "clear_history")
        assert not hasattr(executor, "clear_orders")

    def test_no_delete_method(self):
        executor = _make_executor()
        assert not hasattr(executor, "delete_order")
        assert not hasattr(executor, "remove_order")

    def test_executor_source_no_ledger_write(self):
        """OrderExecutor source must not write to any ledger."""
        import importlib

        source = importlib.util.find_spec("app.services.order_executor")
        if source and source.origin:
            content = Path(source.origin).read_text(encoding="utf-8")
            # Must not call ledger write methods
            assert "record_receipt" not in content
            assert "propose_and_guard" not in content
            assert "transition_to" not in content
            assert "record_failure" not in content


# -- AXIS 5: Audit Trail -------------------------------------------------- #


class TestAuditTrail:
    """History, order lookup, lineage trace."""

    @pytest.mark.asyncio
    async def test_get_history_returns_all(self):
        executor = _make_executor()
        p1 = _make_submit_proposal(proposal_id="SP-h1")
        p2 = _make_submit_proposal(proposal_id="SP-h2", symbol="ETH/USDT")
        await executor.execute_order(p1, side="buy", dry_run=True)
        await executor.execute_order(p2, side="sell", dry_run=True)
        history = executor.get_history()
        assert len(history) == 2
        assert all(isinstance(h, dict) for h in history)

    @pytest.mark.asyncio
    async def test_get_order_by_id(self):
        executor = _make_executor()
        proposal = _make_submit_proposal()
        result = await executor.execute_order(proposal, side="buy", dry_run=True)
        found = executor.get_order(result.order_id)
        assert found is not None
        assert found.order_id == result.order_id

    @pytest.mark.asyncio
    async def test_get_order_by_proposal_id(self):
        executor = _make_executor()
        proposal = _make_submit_proposal(proposal_id="SP-lookup-001")
        await executor.execute_order(proposal, side="buy", dry_run=True)
        found = executor.get_order_by_proposal("SP-lookup-001")
        assert found is not None
        assert found.submit_proposal_id == "SP-lookup-001"

    @pytest.mark.asyncio
    async def test_history_count_increments(self):
        executor = _make_executor()
        assert executor.count == 0
        p1 = _make_submit_proposal(proposal_id="SP-cnt-1")
        await executor.execute_order(p1, side="buy", dry_run=True)
        assert executor.count == 1
        p2 = _make_submit_proposal(proposal_id="SP-cnt-2", symbol="ETH")
        await executor.execute_order(p2, side="sell", dry_run=True)
        assert executor.count == 2
