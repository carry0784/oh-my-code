"""
Agent Governance Tests — 13 tests across 3 axes.

Axis 1: Contract preservation (2)
Axis 2: Bypass prevention (8, including gate-none failure + exception evidence)
Axis 3: Record consistency (3)

All tests mock _call_llm — no real LLM calls.
"""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Prevent SQLAlchemy model import chain errors ──
# The Signal model uses 'metadata' (reserved by SQLAlchemy Declarative API).
# We stub problematic modules before importing app code.
_STUB_MODULES = [
    "app.models", "app.models.order", "app.models.signal",
    "app.models.position", "app.models.trade",
    "app.core.database",
    "app.services", "app.services.signal_service",
]
_saved = {}
for _mod_name in _STUB_MODULES:
    if _mod_name not in sys.modules:
        _stub = ModuleType(_mod_name)
        # Provide minimal stubs that downstream code expects
        if _mod_name == "app.core.database":
            _stub.Base = type("Base", (), {})
            _stub.get_db = MagicMock()
        if _mod_name == "app.models.signal":
            _stub.Signal = MagicMock()
        if _mod_name == "app.services.signal_service":
            _stub.SignalService = MagicMock()
        sys.modules[_mod_name] = _stub
        _saved[_mod_name] = _stub

from kdexter.ledger.forbidden_ledger import ForbiddenLedger, ForbiddenAction
from kdexter.audit.evidence_store import EvidenceStore
from kdexter.state_machine.security_state import SecurityStateContext, SecurityStateEnum

from app.agents.governance_gate import (
    GovernanceGate,
    DecisionCode,
    ReasonCode,
    PhaseCode,
    CheckStatus,
)
from app.schemas.agent import AgentTask, AgentResponse
from app.agents.orchestrator import AgentOrchestrator


# ─────────────────────────────────────────────────────────────────────────── #
# Fixtures
# ─────────────────────────────────────────────────────────────────────────── #

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset GovernanceGate singleton before and after every test."""
    GovernanceGate._reset_for_testing()
    yield
    GovernanceGate._reset_for_testing()


@pytest.fixture
def governance_components():
    """Create fresh governance components for each test."""
    ledger = ForbiddenLedger()
    store = EvidenceStore()
    security_ctx = SecurityStateContext()
    return ledger, store, security_ctx


@pytest.fixture
def gate(governance_components):
    ledger, store, security_ctx = governance_components
    return GovernanceGate(
        forbidden_ledger=ledger,
        evidence_store=store,
        security_ctx=security_ctx,
    )


@pytest.fixture
def valid_task():
    return AgentTask(
        task_type="validate_signal",
        symbol="BTC/USDT",
        exchange="binance",
        context={"price": 50000},
    )


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_orchestrator(db, gate):
    """Create orchestrator with governance gate, patching governance_enabled."""
    with patch("app.agents.orchestrator.settings") as mock_settings:
        mock_settings.governance_enabled = True
        return AgentOrchestrator(db=db, governance_gate=gate)


def _mock_llm_result():
    """Standard mock LLM result for signal validation."""
    return {
        "approved": True,
        "confidence": 0.85,
        "reasoning": "Signal looks valid based on technical analysis",
    }


# ═══════════════════════════════════════════════════════════════════════════ #
# AXIS 1: CONTRACT PRESERVATION (2 tests)
# ═══════════════════════════════════════════════════════════════════════════ #

class TestContractPreservation:
    """Ensure AgentResponse API contract is preserved."""

    def test_api_contract_unchanged(self):
        """governance_evidence_id=None serialization works (backward compat)."""
        response = AgentResponse(
            success=True,
            task_type="validate_signal",
            result={"data": "test"},
            reasoning="test",
            confidence=0.9,
        )
        data = response.model_dump()
        assert data["governance_evidence_id"] is None
        assert data["success"] is True
        assert data["task_type"] == "validate_signal"

    def test_response_with_evidence_id(self):
        """governance_evidence_id included in serialization when set."""
        response = AgentResponse(
            success=True,
            task_type="validate_signal",
            result={"data": "test"},
            governance_evidence_id="ev-12345",
        )
        data = response.model_dump()
        assert data["governance_evidence_id"] == "ev-12345"


# ═══════════════════════════════════════════════════════════════════════════ #
# AXIS 2: BYPASS PREVENTION (8 tests)
# ═══════════════════════════════════════════════════════════════════════════ #

class TestBypassPrevention:
    """Ensure governance cannot be bypassed."""

    @pytest.mark.asyncio
    async def test_normal_path_requires_pre_check(self, gate, valid_task, mock_db):
        """Normal execution path must go through pre_check."""
        orchestrator = _make_orchestrator(mock_db, gate)

        with patch.object(gate, "pre_check", wraps=gate.pre_check) as spy:
            with patch(
                "app.agents.signal_validator.SignalValidatorAgent.execute",
                new_callable=AsyncMock,
                return_value=_mock_llm_result(),
            ):
                await orchestrator.analyze(valid_task)
                spy.assert_called_once()

    @pytest.mark.asyncio
    async def test_pre_check_failure_prevents_llm_call(self, gate, mock_db):
        """When pre_check fails, _call_llm must never be invoked."""
        task = AgentTask(
            task_type="validate_signal",
            symbol=None,  # Missing symbol → mandatory check fails
            exchange="binance",
        )
        orchestrator = _make_orchestrator(mock_db, gate)

        with patch(
            "app.agents.signal_validator.SignalValidatorAgent.execute",
            new_callable=AsyncMock,
        ) as mock_execute:
            result = await orchestrator.analyze(task)
            assert result.success is False
            assert result.governance_evidence_id is not None
            mock_execute.assert_not_called()

    def test_forbidden_action_blocks(self, gate):
        """FA-AGENT-001 pattern match → blocked."""
        task = MagicMock()
        task.task_type = "DIRECT_EXCHANGE_CALL"
        task.symbol = "BTC/USDT"
        task.exchange = "binance"

        # Register a forbidden action that matches
        gate.forbidden_ledger.register(ForbiddenAction(
            action_id="FA-TEST-FORBIDDEN",
            description="Test forbidden action",
            severity="LOCKDOWN",
            pattern="AGENT_DIRECT_EXCHANGE_CALL",
            registered_by="test",
        ))

        passed, decision, reason, eid = gate.pre_check(task)
        assert passed is False
        assert decision == DecisionCode.BLOCKED.value
        assert reason == ReasonCode.FORBIDDEN_ACTION.value

    def test_missing_symbol_fails_mandatory(self, gate):
        """symbol=None → mandatory check fails."""
        task = AgentTask(
            task_type="validate_signal",
            symbol=None,
            exchange="binance",
        )
        passed, decision, reason, eid = gate.pre_check(task)
        assert passed is False
        assert decision == DecisionCode.BLOCKED.value
        assert reason == ReasonCode.MISSING_SYMBOL.value
        assert eid  # evidence must exist even on failure

    def test_global_lockdown_blocks(self, governance_components):
        """SecurityState=LOCKDOWN → immediate block."""
        ledger, store, security_ctx = governance_components
        security_ctx.escalate(SecurityStateEnum.LOCKDOWN, "test-trigger")

        gate = GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
        )

        task = AgentTask(
            task_type="validate_signal",
            symbol="BTC/USDT",
            exchange="binance",
        )
        passed, decision, reason, eid = gate.pre_check(task)
        assert passed is False
        assert decision == DecisionCode.BLOCKED.value
        assert reason == ReasonCode.LOCKDOWN_BLOCK.value

    def test_no_bypass_without_disabled_flag(self, gate, valid_task, mock_db):
        """governance_enabled=True → no bypass path exists."""
        with patch("app.agents.orchestrator.settings") as mock_settings:
            mock_settings.governance_enabled = True
            orchestrator = AgentOrchestrator(db=mock_db, governance_gate=gate)
            # Gate is connected, no bypass
            assert orchestrator.governance_gate is not None

    def test_enabled_true_gate_none_fails(self, mock_db):
        """governance_enabled=True + gate=None → RuntimeError."""
        with patch("app.agents.orchestrator.settings") as mock_settings:
            mock_settings.governance_enabled = True
            with pytest.raises(RuntimeError, match="governance_gate is None"):
                AgentOrchestrator(db=mock_db, governance_gate=None)

    @pytest.mark.asyncio
    async def test_llm_exception_records_error_evidence(self, gate, valid_task, mock_db):
        """LLM exception → error evidence is produced via post_record_error."""
        orchestrator = _make_orchestrator(mock_db, gate)

        with patch(
            "app.agents.signal_validator.SignalValidatorAgent.execute",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM connection failed"),
        ):
            result = await orchestrator.analyze(valid_task)
            assert result.success is False
            assert result.governance_evidence_id is not None

            # Verify error evidence exists in store
            all_bundles = gate.evidence_store.list_all()
            error_bundles = [
                b for b in all_bundles
                if b.artifacts and isinstance(b.artifacts[0], dict)
                and b.artifacts[0].get("phase") == PhaseCode.ERROR.value
            ]
            assert len(error_bundles) >= 1
            error_art = error_bundles[0].artifacts[0]
            assert error_art["decision_code"] == DecisionCode.FAILED.value
            assert error_art["reason_code"] == ReasonCode.POST_EXCEPTION.value
            assert error_art["error_severity"] == "CRITICAL"

    # ── execute() 경로 거버넌스 흐름 테스트 (T-01 해소) ────────────────── #

    @pytest.mark.asyncio
    async def test_execute_requires_pre_check(self, gate, mock_db):
        """execute() 경로도 반드시 pre_check를 경유한다."""
        orchestrator = _make_orchestrator(mock_db, gate)
        # signal_id 없는 task → signal_validator.validate() 호출되지 않음, risk_manager.execute()만 호출
        with patch.object(gate, "pre_check", wraps=gate.pre_check) as spy:
            with patch(
                "app.agents.risk_manager.RiskManagerAgent.execute",
                new_callable=AsyncMock,
                return_value={"approved": True, "confidence": 0.8, "position_size": 100},
            ):
                task = AgentTask(
                    task_type="execute_trade",
                    symbol="BTC/USDT",
                    exchange="binance",
                    context={"price": 50000},
                )
                await orchestrator.execute(task)
                spy.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_pre_check_failure_prevents_execution(self, gate, mock_db):
        """execute() pre_check 실패 시 LLM 에이전트 미호출."""
        task = AgentTask(
            task_type="execute_trade",
            symbol=None,  # Missing symbol → mandatory check fails
            exchange="binance",
        )
        orchestrator = _make_orchestrator(mock_db, gate)
        with patch(
            "app.agents.risk_manager.RiskManagerAgent.execute",
            new_callable=AsyncMock,
        ) as mock_risk:
            result = await orchestrator.execute(task)
            assert result.success is False
            assert result.governance_evidence_id is not None
            mock_risk.assert_not_called()

    # ── execute() evidence 의미 무결성 테스트 (F-04/T-08 해소) ─────────── #

    @pytest.mark.asyncio
    async def test_execute_risk_rejection_evidence_not_allowed(self, gate, mock_db):
        """execute() risk 거부 시 evidence가 ALLOWED로 기록되지 않아야 한다."""
        orchestrator = _make_orchestrator(mock_db, gate)
        with patch(
            "app.agents.risk_manager.RiskManagerAgent.execute",
            new_callable=AsyncMock,
            return_value={"approved": False, "reasoning": "Risk too high", "confidence": 0.3},
        ):
            task = AgentTask(
                task_type="execute_trade",
                symbol="BTC/USDT",
                exchange="binance",
                context={"price": 50000},
            )
            result = await orchestrator.execute(task)
            assert result.success is False
            assert result.governance_evidence_id is not None

            # governance_evidence_id와 1:1 일치하는 evidence를 직접 조회
            eid = result.governance_evidence_id
            target_bundle = gate.evidence_store.get(eid)
            assert target_bundle is not None, \
                f"POST evidence {eid} must exist for risk rejection path"
            # bundle 내부에서 phase==POST artifact를 명시적으로 찾음
            post_arts = [
                a for a in target_bundle.artifacts
                if isinstance(a, dict) and a.get("phase") == PhaseCode.POST.value
            ]
            assert len(post_arts) == 1, \
                f"Expected exactly 1 POST artifact in bundle {eid}, got {len(post_arts)}"
            post_art = post_arts[0]
            # F-04: ALLOWED로 기록되면 의미 오염
            assert post_art["decision_code"] != DecisionCode.ALLOWED.value, \
                "Risk rejection should not record decision_code=ALLOWED"

    @pytest.mark.asyncio
    async def test_execute_validation_rejection_evidence_not_allowed(self, gate, mock_db):
        """execute() validation 거부 시 evidence가 ALLOWED로 기록되지 않아야 한다."""
        orchestrator = _make_orchestrator(mock_db, gate)

        # signal_id가 있어야 validation 경로 진입
        task = AgentTask(
            task_type="execute_trade",
            symbol="BTC/USDT",
            exchange="binance",
            context={"price": 50000},
            signal_id="test-signal-123",
        )

        mock_signal = MagicMock()
        mock_signal.symbol = "BTC/USDT"
        mock_signal.exchange = "binance"
        mock_signal.signal_type.value = "long"
        mock_signal.entry_price = 50000
        mock_signal.stop_loss = 49000
        mock_signal.take_profit = 52000
        mock_signal.confidence = 0.7
        mock_signal.signal_metadata = {}
        mock_signal.id = "test-signal-123"

        # Create a mock SignalService instance with async get_signal
        mock_signal_service_instance = MagicMock()
        mock_signal_service_instance.get_signal = AsyncMock(return_value=mock_signal)
        mock_signal_service_cls = MagicMock(return_value=mock_signal_service_instance)

        with patch(
            "app.services.signal_service.SignalService",
            mock_signal_service_cls,
        ):
            with patch(
                "app.agents.signal_validator.SignalValidatorAgent.validate",
                new_callable=AsyncMock,
                return_value={"approved": False, "reasoning": "Signal quality too low", "confidence": 0.2},
            ):
                with patch(
                    "app.agents.risk_manager.RiskManagerAgent.execute",
                    new_callable=AsyncMock,
                ) as mock_risk:
                    result = await orchestrator.execute(task)
                    assert result.success is False
                    assert result.governance_evidence_id is not None

                    # validation 거부 후 risk 단계로 내려가면 안 됨 (short-circuit 검증)
                    mock_risk.assert_not_called()

                    # governance_evidence_id와 1:1 일치하는 evidence를 직접 조회
                    eid = result.governance_evidence_id
                    target_bundle = gate.evidence_store.get(eid)
                    assert target_bundle is not None, \
                        f"POST evidence {eid} must exist for validation rejection path"
                    # bundle 내부에서 phase==POST artifact를 명시적으로 찾음
                    post_arts = [
                        a for a in target_bundle.artifacts
                        if isinstance(a, dict) and a.get("phase") == PhaseCode.POST.value
                    ]
                    assert len(post_arts) == 1, \
                        f"Expected exactly 1 POST artifact in bundle {eid}, got {len(post_arts)}"
                    post_art = post_arts[0]
                    assert post_art["decision_code"] != DecisionCode.ALLOWED.value, \
                        "Validation rejection should not record decision_code=ALLOWED"


# ═══════════════════════════════════════════════════════════════════════════ #
# AXIS 3: RECORD CONSISTENCY (3 tests)
# ═══════════════════════════════════════════════════════════════════════════ #

class TestRecordConsistency:
    """Ensure evidence bundles are produced and linked correctly."""

    @pytest.mark.asyncio
    async def test_evidence_produced_on_approval(self, gate, valid_task, mock_db):
        """Approved execution produces EvidenceBundle."""
        orchestrator = _make_orchestrator(mock_db, gate)

        with patch(
            "app.agents.signal_validator.SignalValidatorAgent.execute",
            new_callable=AsyncMock,
            return_value=_mock_llm_result(),
        ):
            result = await orchestrator.analyze(valid_task)
            assert result.success is True
            assert result.governance_evidence_id is not None
            assert gate.evidence_store.count() >= 2  # pre + post

    @pytest.mark.asyncio
    async def test_evidence_produced_on_rejection(self, gate, mock_db):
        """Rejected execution (mandatory fail) still produces EvidenceBundle."""
        task = AgentTask(
            task_type="validate_signal",
            symbol=None,
            exchange="binance",
        )
        orchestrator = _make_orchestrator(mock_db, gate)

        result = await orchestrator.analyze(task)
        assert result.success is False
        assert result.governance_evidence_id is not None
        assert gate.evidence_store.count() >= 1  # at least pre evidence

    @pytest.mark.asyncio
    async def test_evidence_links_and_coverage_meta(self, gate, valid_task, mock_db):
        """Post evidence links to pre evidence + coverage meta is dynamically computed."""
        orchestrator = _make_orchestrator(mock_db, gate)

        with patch(
            "app.agents.signal_validator.SignalValidatorAgent.execute",
            new_callable=AsyncMock,
            return_value=_mock_llm_result(),
        ):
            await orchestrator.analyze(valid_task)

        all_bundles = gate.evidence_store.list_all()

        # Find PRE and POST bundles
        pre_bundles = [
            b for b in all_bundles
            if b.artifacts and isinstance(b.artifacts[0], dict)
            and b.artifacts[0].get("phase") == PhaseCode.PRE.value
        ]
        post_bundles = [
            b for b in all_bundles
            if b.artifacts and isinstance(b.artifacts[0], dict)
            and b.artifacts[0].get("phase") == PhaseCode.POST.value
        ]

        assert len(pre_bundles) >= 1
        assert len(post_bundles) >= 1

        # Post links to pre
        post_art = post_bundles[0].artifacts[0]
        assert post_art["pre_evidence_id"] == pre_bundles[0].bundle_id

        # Coverage meta is dynamically computed (not hardcoded)
        pre_art = pre_bundles[0].artifacts[0]
        coverage = pre_art["coverage_meta"]
        assert coverage["total_checks"] == 10
        total_classified = (
            coverage["executed_checks"]
            + coverage["not_applicable_checks"]
            + coverage["deferred_checks"]
            + coverage.get("unimplemented_checks", 0)
        )
        assert total_classified == coverage["total_checks"]
        assert coverage["executed_checks"] >= 1  # at least FORBIDDEN_CHECK ran

        # No orphans: every pre has a corresponding post
        pre_ids = {b.bundle_id for b in pre_bundles}
        linked_pre_ids = {
            b.artifacts[0]["pre_evidence_id"]
            for b in post_bundles
            if b.artifacts and isinstance(b.artifacts[0], dict)
        }
        orphan_count = len(pre_ids - linked_pre_ids)
        assert orphan_count == 0


# ═══════════════════════════════════════════════════════════════════════════ #
# AXIS 4: SINGLETON SAFETY (B-06) — 5 tests
# ═══════════════════════════════════════════════════════════════════════════ #

class TestSingletonSafety:
    """B-06: GovernanceGate singleton enforcement and operational safety."""

    def test_singleton_enforced(self, governance_components):
        """Second GovernanceGate creation raises RuntimeError."""
        ledger, store, security_ctx = governance_components
        # First creation succeeds
        gate1 = GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
        )
        assert gate1.gate_id is not None

        # Second creation must fail
        ledger2 = ForbiddenLedger()
        store2 = EvidenceStore()
        ctx2 = SecurityStateContext()
        with pytest.raises(RuntimeError, match="singleton already exists"):
            GovernanceGate(
                forbidden_ledger=ledger2,
                evidence_store=store2,
                security_ctx=ctx2,
            )

    def test_duplicate_lifespan_blocked(self, governance_components):
        """_create_governance_gate() blocks when GovernanceGate._instance exists."""
        ledger, store, security_ctx = governance_components
        # Create first gate
        GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
        )
        # Simulate duplicate lifespan call
        with patch("app.main.settings") as mock_settings:
            mock_settings.governance_enabled = True
            from app.main import _create_governance_gate
            with pytest.raises(RuntimeError, match="duplicate lifespan"):
                _create_governance_gate()

    def test_security_state_thread_safe(self):
        """Concurrent escalate calls from 10 threads converge to LOCKDOWN."""
        import threading

        ctx = SecurityStateContext()
        barrier = threading.Barrier(10)

        def escalate_to_lockdown():
            barrier.wait()
            ctx.escalate(SecurityStateEnum.LOCKDOWN, "thread-test")

        threads = [threading.Thread(target=escalate_to_lockdown) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert ctx.current == SecurityStateEnum.LOCKDOWN
        assert ctx.previous is not None

    def test_gate_id_in_evidence(self, gate, valid_task):
        """gate_id is propagated to PRE and POST evidence artifacts."""
        passed, decision, reason, eid = gate.pre_check(valid_task)
        assert passed is True

        # Check PRE evidence
        pre_bundle = gate.evidence_store.get(eid)
        assert pre_bundle is not None
        pre_art = pre_bundle.artifacts[0]
        assert pre_art["gate_id"] == gate.gate_id
        assert pre_art["gate_generation"] == gate.gate_generation
        assert "gate_created_at" in pre_art

        # Record POST evidence
        post_eid = gate.post_record(
            valid_task,
            {"approved": True, "confidence": 0.9, "reasoning": "ok"},
            eid,
        )
        post_bundle = gate.evidence_store.get(post_eid)
        assert post_bundle is not None
        post_art = post_bundle.artifacts[0]
        assert post_art["gate_id"] == gate.gate_id
        assert post_art["gate_generation"] == gate.gate_generation

    def test_reset_for_testing_production_blocked(self, governance_components):
        """_reset_for_testing() raises RuntimeError when APP_ENV=production."""
        ledger, store, security_ctx = governance_components
        GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
        )
        with patch.dict("os.environ", {"APP_ENV": "production"}):
            with pytest.raises(RuntimeError, match="forbidden in production"):
                GovernanceGate._reset_for_testing()


# ═════════════════��══════════════════��══════════════════════════════════════ #
# AXIS 5: BUDGET CONTROL (M-08 / G-22) — 4 tests
# ═══��═══════════════════════════════════���═══════════════════════════════���═══ #

class TestBudgetControl:
    """M-08/G-22: CostController integration with GovernanceGate."""

    def test_budget_check_passed_when_under_limit(self, governance_components, valid_task):
        """BUDGET_CHECK = passed when resource_usage_ratio <= 1.0."""
        from kdexter.engines.cost_controller import CostController

        ledger, store, security_ctx = governance_components
        cc = CostController()
        cc.set_budget("API_CALLS", limit=100)
        cc.set_budget("LLM_TOKENS", limit=10000)
        cc.record_usage("API_CALLS", 10)
        cc.record_usage("LLM_TOKENS", 500)

        gate = GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
            cost_controller=cc,
        )

        passed, decision, reason, eid = gate.pre_check(valid_task)
        assert passed is True

        # Verify BUDGET_CHECK is now "passed", not "deferred"
        bundle = gate.evidence_store.get(eid)
        check_matrix = bundle.artifacts[0]["check_matrix"]
        assert check_matrix["BUDGET_CHECK"]["status"] == CheckStatus.PASSED.value

    def test_budget_check_blocks_when_exceeded(self, governance_components, valid_task):
        """BUDGET_CHECK = failed when resource_usage_ratio > 1.0."""
        from kdexter.engines.cost_controller import CostController

        ledger, store, security_ctx = governance_components
        cc = CostController()
        cc.set_budget("API_CALLS", limit=10)
        cc.record_usage("API_CALLS", 15)  # 150% = exceeded

        gate = GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
            cost_controller=cc,
        )

        passed, decision, reason, eid = gate.pre_check(valid_task)
        assert passed is False
        assert decision == DecisionCode.BLOCKED.value
        assert reason == ReasonCode.BUDGET_EXCEEDED.value

        bundle = gate.evidence_store.get(eid)
        check_matrix = bundle.artifacts[0]["check_matrix"]
        assert check_matrix["BUDGET_CHECK"]["status"] == CheckStatus.FAILED.value

    def test_budget_deferred_when_no_controller(self, gate, valid_task):
        """BUDGET_CHECK = deferred when CostController is not connected."""
        assert gate.cost_controller is None
        passed, decision, reason, eid = gate.pre_check(valid_task)
        assert passed is True

        bundle = gate.evidence_store.get(eid)
        check_matrix = bundle.artifacts[0]["check_matrix"]
        assert check_matrix["BUDGET_CHECK"]["status"] == CheckStatus.DEFERRED.value

    @pytest.mark.asyncio
    async def test_post_record_records_token_usage(self, governance_components, valid_task, mock_db):
        """post_record records LLM token usage to CostController."""
        from kdexter.engines.cost_controller import CostController

        ledger, store, security_ctx = governance_components
        cc = CostController()
        cc.set_budget("API_CALLS", limit=1000)
        cc.set_budget("LLM_TOKENS", limit=500000)

        gate = GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
            cost_controller=cc,
        )

        orchestrator = _make_orchestrator(mock_db, gate)

        with patch(
            "app.agents.signal_validator.SignalValidatorAgent.execute",
            new_callable=AsyncMock,
            return_value=_mock_llm_result(),
        ):
            # Simulate last_usage being set by BaseAgent
            orchestrator.signal_validator.last_usage = {
                "input_tokens": 100,
                "output_tokens": 200,
            }
            await orchestrator.analyze(valid_task)

        # Verify CostController recorded the usage
        api_budget = cc.get_budget("API_CALLS")
        token_budget = cc.get_budget("LLM_TOKENS")
        assert api_budget.current == 1  # 1 API call
        assert token_budget.current == 300  # 100 + 200 tokens


# ═══════════════════════════════════════════════════════════════════════════ #
# AXIS 6: FAILURE PATTERN MEMORY (M-13 / G-21) — 3 tests
# ═══════════════════════════════════════════════════════════════════════════ #

class TestFailurePatternMemory:
    """M-13/G-21: FailurePatternMemory integration with GovernanceGate."""

    def test_pattern_check_passed_when_no_history(self, governance_components, valid_task):
        """PATTERN_CHECK = passed when no failure history."""
        from kdexter.engines.failure_router import FailurePatternMemory

        ledger, store, security_ctx = governance_components
        pm = FailurePatternMemory()

        gate = GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
            pattern_memory=pm,
        )

        passed, decision, reason, eid = gate.pre_check(valid_task)
        assert passed is True

        bundle = gate.evidence_store.get(eid)
        check_matrix = bundle.artifacts[0]["check_matrix"]
        assert check_matrix["PATTERN_CHECK"]["status"] == CheckStatus.PASSED.value

    def test_pattern_check_blocks_recurring_failure(self, governance_components, valid_task):
        """PATTERN_CHECK = failed when recurring failure pattern detected."""
        from kdexter.engines.failure_router import FailurePatternMemory

        ledger, store, security_ctx = governance_components
        pm = FailurePatternMemory()

        # Record 3 prior failures for this task type → PATTERN recurrence
        pm.record("AGENT_VALIDATE_SIGNAL")
        pm.record("AGENT_VALIDATE_SIGNAL")
        pm.record("AGENT_VALIDATE_SIGNAL")

        gate = GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
            pattern_memory=pm,
        )

        passed, decision, reason, eid = gate.pre_check(valid_task)
        assert passed is False
        assert decision == DecisionCode.BLOCKED.value
        assert reason == ReasonCode.PATTERN_DETECTED.value

        bundle = gate.evidence_store.get(eid)
        check_matrix = bundle.artifacts[0]["check_matrix"]
        assert check_matrix["PATTERN_CHECK"]["status"] == CheckStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_error_records_failure_to_pattern_memory(self, governance_components, valid_task, mock_db):
        """LLM exception records failure to FailurePatternMemory."""
        from kdexter.engines.failure_router import FailurePatternMemory

        ledger, store, security_ctx = governance_components
        pm = FailurePatternMemory()

        gate = GovernanceGate(
            forbidden_ledger=ledger,
            evidence_store=store,
            security_ctx=security_ctx,
            pattern_memory=pm,
        )

        orchestrator = _make_orchestrator(mock_db, gate)

        with patch(
            "app.agents.signal_validator.SignalValidatorAgent.execute",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM connection failed"),
        ):
            await orchestrator.analyze(valid_task)

        # Verify failure was recorded
        assert pm.count("AGENT_VALIDATE_SIGNAL") == 1
