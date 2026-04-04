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
