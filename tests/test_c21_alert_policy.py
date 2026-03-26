"""
Card C-21: Alert Policy / Escalation Rules — Tests

검수 범위:
  C21-1: 모듈 구조 및 데이터 모델
  C21-2: Duplicate suppression
  C21-3: Degraded escalation
  C21-4: Clear de-escalation (resolve)
  C21-5: Urgency markers
  C21-6: Fail-closed fallthrough
  C21-7: 기존 router 보존
  C21-8: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from app.core.alert_policy import (
    AlertPolicy,
    PolicyDecision,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_ESCALATION_THRESHOLD,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = PROJECT_ROOT / "app" / "core" / "alert_policy.py"
ROUTER_PATH = PROJECT_ROOT / "app" / "core" / "alert_router.py"


# ===========================================================================
# C21-1: 모듈 구조
# ===========================================================================
class TestC21ModuleStructure:

    def test_module_exists(self):
        assert POLICY_PATH.exists()

    def test_policy_decision_dataclass(self):
        d = PolicyDecision(action="send", channels=["console"], severity_tier="high")
        assert d.action == "send"
        assert d.channels == ["console"]
        assert d.urgent is False
        assert d.suppressed is False

    def test_alert_policy_class_exists(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "class AlertPolicy" in content

    def test_evaluate_method_exists(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "def evaluate" in content

    def test_default_cooldown(self):
        assert DEFAULT_COOLDOWN_SECONDS == 300

    def test_default_escalation_threshold(self):
        assert DEFAULT_ESCALATION_THRESHOLD == 3


# ===========================================================================
# C21-2: Duplicate suppression
# ===========================================================================
class TestC21DuplicateSuppression:

    def test_first_send_not_suppressed(self):
        policy = AlertPolicy()
        routing = {"channels": ["console", "snapshot"], "severity_tier": "high", "reason": "test"}
        result = policy.evaluate(routing, {"highest_incident": "WORK_FAILED"})
        assert result.action == "send"
        assert result.suppressed is False

    def test_duplicate_within_cooldown_suppressed(self):
        policy = AlertPolicy()
        routing = {"channels": ["console", "snapshot"], "severity_tier": "high", "reason": "test"}
        snapshot = {"highest_incident": "WORK_FAILED"}
        policy.evaluate(routing, snapshot)  # first
        result = policy.evaluate(routing, snapshot)  # duplicate
        assert result.action == "suppress"
        assert result.suppressed is True
        assert result.channels == []

    def test_different_incident_not_suppressed(self):
        policy = AlertPolicy()
        r1 = {"channels": ["console"], "severity_tier": "high", "reason": "a"}
        r2 = {"channels": ["console"], "severity_tier": "high", "reason": "b"}
        policy.evaluate(r1, {"highest_incident": "WORK_FAILED"})
        result = policy.evaluate(r2, {"highest_incident": "LOOP_CRITICAL"})
        assert result.action == "send"

    def test_different_severity_not_suppressed(self):
        policy = AlertPolicy()
        r1 = {"channels": ["console"], "severity_tier": "high", "reason": "a"}
        r2 = {"channels": ["console", "external"], "severity_tier": "critical", "reason": "b"}
        policy.evaluate(r1, {"highest_incident": "X"})
        result = policy.evaluate(r2, {"highest_incident": "X"})
        assert result.action == "send"


# ===========================================================================
# C21-3: Degraded escalation
# ===========================================================================
class TestC21DegradedEscalation:

    def test_single_degraded_stays_low(self):
        policy = AlertPolicy(escalation_threshold=3)
        routing = {"channels": ["snapshot"], "severity_tier": "low", "reason": "degraded"}
        result = policy.evaluate(routing, {"highest_incident": "NONE"})
        assert result.severity_tier == "low"
        assert result.action == "send"

    def test_consecutive_degraded_escalates(self):
        policy = AlertPolicy(escalation_threshold=3, cooldown_seconds=0)
        routing = {"channels": ["snapshot"], "severity_tier": "low", "reason": "degraded"}
        snapshot = {"highest_incident": "DOCTRINE_VIOLATION_x1"}
        policy.evaluate(routing, snapshot)
        policy.evaluate(routing, snapshot)
        result = policy.evaluate(routing, snapshot)  # 3rd consecutive
        assert result.action == "escalate"
        assert result.severity_tier == "high"
        assert "external" in result.channels

    def test_escalation_resets_counter(self):
        policy = AlertPolicy(escalation_threshold=2, cooldown_seconds=0)
        routing = {"channels": ["snapshot"], "severity_tier": "low", "reason": "degraded"}
        snapshot = {"highest_incident": "X"}
        policy.evaluate(routing, snapshot)
        policy.evaluate(routing, snapshot)  # escalates
        # After escalation, counter resets — next low should be "send" not escalate
        result = policy.evaluate(routing, snapshot)
        assert result.action == "send"


# ===========================================================================
# C21-4: Clear de-escalation
# ===========================================================================
class TestC21ClearDeescalation:

    def test_clear_after_incident_sends_resolve(self):
        policy = AlertPolicy()
        # First: active incident
        policy.evaluate(
            {"channels": ["console", "snapshot"], "severity_tier": "high", "reason": "test"},
            {"highest_incident": "WORK_FAILED"},
        )
        # Then: clear
        result = policy.evaluate(
            {"channels": [], "severity_tier": "clear", "reason": "no incidents"},
            {"highest_incident": "NONE"},
        )
        assert result.action == "resolve"
        assert "resolved" in result.reason

    def test_clear_without_prior_incident_suppressed(self):
        policy = AlertPolicy()
        result = policy.evaluate(
            {"channels": [], "severity_tier": "clear", "reason": "no incidents"},
            {"highest_incident": "NONE"},
        )
        assert result.action == "suppress"
        assert result.suppressed is True

    def test_resolve_only_sent_once(self):
        policy = AlertPolicy()
        policy.evaluate(
            {"channels": ["console"], "severity_tier": "high", "reason": "test"},
            {"highest_incident": "X"},
        )
        policy.evaluate(
            {"channels": [], "severity_tier": "clear", "reason": ""},
            {"highest_incident": "NONE"},
        )  # resolve
        result = policy.evaluate(
            {"channels": [], "severity_tier": "clear", "reason": ""},
            {"highest_incident": "NONE"},
        )  # second clear
        assert result.action == "suppress"


# ===========================================================================
# C21-5: Urgency markers
# ===========================================================================
class TestC21Urgency:

    def test_critical_is_urgent(self):
        policy = AlertPolicy()
        routing = {"channels": ["console", "snapshot", "external"], "severity_tier": "critical", "reason": "lockdown"}
        result = policy.evaluate(routing, {"highest_incident": "LOCKDOWN"})
        assert result.urgent is True

    def test_high_is_not_urgent(self):
        policy = AlertPolicy()
        routing = {"channels": ["console", "snapshot"], "severity_tier": "high", "reason": "test"}
        result = policy.evaluate(routing, {"highest_incident": "X"})
        assert result.urgent is False

    def test_low_is_not_urgent(self):
        policy = AlertPolicy()
        routing = {"channels": ["snapshot"], "severity_tier": "low", "reason": "test"}
        result = policy.evaluate(routing, {"highest_incident": "X"})
        assert result.urgent is False


# ===========================================================================
# C21-6: Fail-closed
# ===========================================================================
class TestC21FailClosed:

    def test_malformed_routing_returns_fallthrough(self):
        policy = AlertPolicy()
        result = policy.evaluate({}, None)
        assert result.action in ("send", "suppress")

    def test_reset_clears_state(self):
        policy = AlertPolicy()
        policy.evaluate(
            {"channels": ["console"], "severity_tier": "high", "reason": "x"},
            {"highest_incident": "X"},
        )
        policy.reset()
        # After reset, clear should suppress (no prior incident)
        result = policy.evaluate(
            {"channels": [], "severity_tier": "clear", "reason": ""},
            {"highest_incident": "NONE"},
        )
        assert result.action == "suppress"


# ===========================================================================
# C21-7: 기존 router 보존
# ===========================================================================
class TestC21RouterPreserved:

    def test_router_unchanged(self):
        content = ROUTER_PATH.read_text(encoding="utf-8")
        assert "def route_snapshot" in content
        assert "_CRITICAL_INCIDENTS" in content
        assert "_HIGH_INCIDENTS" in content

    def test_router_does_not_import_policy(self):
        """Router는 policy를 import하지 않는다 (분리 유지)."""
        content = ROUTER_PATH.read_text(encoding="utf-8")
        assert "alert_policy" not in content


# ===========================================================================
# C21-8: 금지 조항
# ===========================================================================
class TestC21Forbidden:

    def test_no_forbidden_strings(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_transport_logic(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content
        assert "urllib" not in content
        assert "requests" not in content

    def test_no_state_persistence(self):
        content = POLICY_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content
        assert "sqlalchemy" not in content
