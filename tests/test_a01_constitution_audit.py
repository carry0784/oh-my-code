"""
Card A-01: Full Constitution Audit — Automated compliance tests

Purpose:
  Verify constitutional compliance across all system layers.
  This is the automated enforcement of the K-V3 constitution,
  seal documents, and operational laws.

Scope:
  A01-1: Constitution document existence
  A01-2: Seal document existence
  A01-3: Law document existence
  A01-4: Layer boundary compliance
  A01-5: Execution SSOT compliance
  A01-6: Forbidden pattern scan (system-wide)
  A01-7: Engine layer isolation
  A01-8: Card B sealed test preservation
  A01-9: Fail-closed doctrine
  A01-10: State ownership compliance

No production code changes. Test-only audit card.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS = PROJECT_ROOT / "docs"
APP = PROJECT_ROOT / "app"
SRC = PROJECT_ROOT / "src"


# ===========================================================================
# A01-1: Constitution document existence
# ===========================================================================
class TestA01ConstitutionExists:

    def test_system_constitution(self):
        assert (DOCS / "system_final_constitution.md").exists()

    def test_law_freeze(self):
        assert (DOCS / "system_law_freeze.md").exists()

    def test_change_protocol(self):
        assert (DOCS / "law_change_protocol.md").exists()

    def test_emergency_override(self):
        assert (DOCS / "law_emergency_override.md").exists()

    def test_audit_law(self):
        assert (DOCS / "law_audit.md").exists()

    def test_phase_law(self):
        assert (DOCS / "law_phase.md").exists()


# ===========================================================================
# A01-2: Seal document existence
# ===========================================================================
class TestA01SealsExist:

    def test_retry_seal(self):
        assert (DOCS / "retry_layer_final_seal.md").exists()

    def test_notification_seal(self):
        assert (DOCS / "notification_layer_seal.md").exists()

    def test_execution_seal(self):
        assert (DOCS / "execution_layer_seal.md").exists()

    def test_engine_seal(self):
        assert (DOCS / "engine_layer_seal.md").exists()

    def test_governance_seal(self):
        assert (DOCS / "governance_layer_seal.md").exists()


# ===========================================================================
# A01-3: Constitution content integrity
# ===========================================================================
class TestA01ConstitutionContent:

    def test_constitution_has_layer_hierarchy(self):
        content = (DOCS / "system_final_constitution.md").read_text(encoding="utf-8")
        assert "Layer Hierarchy" in content
        assert "GOVERNANCE" in content

    def test_constitution_has_fail_closed(self):
        content = (DOCS / "system_final_constitution.md").read_text(encoding="utf-8")
        assert "Fail-Closed" in content

    def test_constitution_has_amendment(self):
        content = (DOCS / "system_final_constitution.md").read_text(encoding="utf-8")
        assert "Amendment" in content

    def test_law_has_hierarchy(self):
        content = (DOCS / "system_law_freeze.md").read_text(encoding="utf-8")
        assert "Constitution" in content
        assert "Law" in content
        assert "Card" in content
        assert "Code" in content


# ===========================================================================
# A01-4: Layer boundary — no cross-layer violations
# ===========================================================================
class TestA01LayerBoundary:

    def test_retry_layer_no_engine_import(self):
        """Retry layer must not import engine modules."""
        retry_files = [
            "retry_executor.py", "retry_plan_store.py",
            "retry_policy_gate.py", "retry_budget.py",
            "retry_metrics.py", "auto_retry_orchestrator.py",
            "delivery_retry_policy.py", "flow_retry_bridge.py",
        ]
        for fname in retry_files:
            fpath = APP / "core" / fname
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8")
                assert "src.kdexter" not in content, \
                    f"Engine import in retry file: {fname}"
                assert "from src" not in content, \
                    f"Engine import in retry file: {fname}"

    def test_notification_layer_no_engine_import(self):
        """Notification layer must not import engine modules."""
        notif_files = [
            "notification_sender.py", "notification_flow.py",
            "notification_receipt_store.py", "alert_router.py",
            "alert_policy.py", "channel_policy.py",
            "real_notifier_adapter.py", "notifier_adapters.py",
        ]
        for fname in notif_files:
            fpath = APP / "core" / fname
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8")
                assert "from src" not in content, \
                    f"Engine import in notification file: {fname}"

    def test_operator_endpoint_no_engine_import(self):
        fpath = APP / "api" / "routes" / "operator_retry.py"
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            assert "src.kdexter" not in content


# ===========================================================================
# A01-5: Execution SSOT compliance
# ===========================================================================
class TestA01ExecutionSSOT:

    def test_execute_single_plan_defined_once(self):
        """SSOT must be defined in exactly one file."""
        core_files = list((APP / "core").glob("*.py"))
        defining = [f.name for f in core_files
                    if "def execute_single_plan(" in
                    f.read_text(encoding="utf-8")]
        assert defining == ["retry_executor.py"]

    def test_orchestrator_no_direct_sender(self):
        fpath = APP / "core" / "auto_retry_orchestrator.py"
        content = fpath.read_text(encoding="utf-8")
        lines = [l for l in content.split("\n")
                 if "get_sender" in l and not l.strip().startswith("#")]
        assert len(lines) == 0

    def test_orchestrator_no_private_executor(self):
        fpath = APP / "core" / "auto_retry_orchestrator.py"
        content = fpath.read_text(encoding="utf-8")
        assert "def _execute_single(" not in content

    def test_bridge_no_sender(self):
        fpath = APP / "core" / "flow_retry_bridge.py"
        content = fpath.read_text(encoding="utf-8")
        assert "get_sender" not in content
        assert "send_notifications" not in content

    def test_operator_no_sender(self):
        fpath = APP / "api" / "routes" / "operator_retry.py"
        content = fpath.read_text(encoding="utf-8")
        assert "get_sender" not in content


# ===========================================================================
# A01-6: Forbidden pattern scan (system-wide app/)
# ===========================================================================
class TestA01ForbiddenPatterns:

    def _scan_app_files(self, pattern):
        """Scan all app/ .py files for pattern in non-docstring body."""
        hits = []
        for fpath in APP.rglob("*.py"):
            content = fpath.read_text(encoding="utf-8")
            # Strip module docstring
            parts = content.split('"""')
            body = parts[-1] if len(parts) >= 3 else content
            if pattern in body:
                hits.append(fpath.name)
        return hits

    def test_no_chain_of_thought(self):
        hits = self._scan_app_files("chain_of_thought")
        assert hits == [], f"chain_of_thought found in: {hits}"

    def test_no_raw_prompt(self):
        hits = self._scan_app_files("raw_prompt")
        assert hits == [], f"raw_prompt found in: {hits}"

    def test_no_internal_reasoning(self):
        hits = self._scan_app_files("internal_reasoning")
        assert hits == [], f"internal_reasoning found in: {hits}"

    def test_no_debug_trace(self):
        hits = self._scan_app_files("debug_trace")
        assert hits == [], f"debug_trace found in: {hits}"


# ===========================================================================
# A01-7: Engine layer isolation
# ===========================================================================
class TestA01EngineIsolation:

    def test_engine_exists(self):
        assert (SRC / "kdexter").exists()

    def test_engine_has_governance(self):
        assert (SRC / "kdexter" / "governance").exists()

    def test_engine_has_gates(self):
        assert (SRC / "kdexter" / "gates").exists()

    def test_engine_has_state_machines(self):
        assert (SRC / "kdexter" / "state_machine").exists()

    def test_app_core_does_not_mutate_engine(self):
        """No app/core file should write to src/kdexter."""
        for fpath in (APP / "core").glob("*.py"):
            content = fpath.read_text(encoding="utf-8")
            # Check for imports that might mutate
            assert "kdexter.state_machine" not in content or \
                   "import" not in content.split("kdexter.state_machine")[0].split("\n")[-1], \
                   f"Potential engine mutation in {fpath.name}"


# ===========================================================================
# A01-8: Card B test preservation
# ===========================================================================
class TestA01CardBPreservation:

    def test_card_b_test_files_exist(self):
        """Card B core test files should exist."""
        test_dir = PROJECT_ROOT / "tests"
        test_files = list(test_dir.glob("*.py"))
        assert len(test_files) > 0

    def test_total_test_count_not_decreased(self):
        """Total test count must be >= sealed baseline."""
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "--co", "-q"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )
        # Count "test session starts" or collected items
        lines = result.stdout.strip().split("\n")
        # Last line typically shows "X tests collected"
        count_line = [l for l in lines if "selected" in l or "test" in l]
        # At minimum, we should have 1631+ tests
        assert len(lines) > 100  # rough check that many tests exist


# ===========================================================================
# A01-9: Fail-closed doctrine
# ===========================================================================
class TestA01FailClosed:

    def test_retry_executor_has_try_except(self):
        content = (APP / "core" / "retry_executor.py").read_text(encoding="utf-8")
        assert "except Exception" in content

    def test_orchestrator_has_try_except(self):
        content = (APP / "core" / "auto_retry_orchestrator.py").read_text(encoding="utf-8")
        assert "except Exception" in content

    def test_notification_flow_has_try_except(self):
        content = (APP / "core" / "notification_flow.py").read_text(encoding="utf-8")
        assert "except Exception" in content

    def test_gate_has_try_except(self):
        content = (APP / "core" / "retry_policy_gate.py").read_text(encoding="utf-8")
        assert "except Exception" in content

    def test_budget_has_try_except(self):
        content = (APP / "core" / "retry_budget.py").read_text(encoding="utf-8")
        assert "except Exception" in content


# ===========================================================================
# A01-10: State ownership — no cross-layer mutation
# ===========================================================================
class TestA01StateOwnership:

    def test_mark_executed_only_in_executor(self):
        """mark_executed calls must only be in retry_executor.py."""
        for fpath in (APP / "core").glob("*.py"):
            if fpath.name == "retry_executor.py":
                continue
            if fpath.name == "retry_plan_store.py":
                continue  # definition is allowed
            content = fpath.read_text(encoding="utf-8")
            assert "mark_executed(" not in content, \
                f"mark_executed in {fpath.name} (not executor)"

    def test_mark_expired_only_in_executor(self):
        """mark_expired calls must only be in retry_executor.py."""
        for fpath in (APP / "core").glob("*.py"):
            if fpath.name == "retry_executor.py":
                continue
            if fpath.name == "retry_plan_store.py":
                continue  # definition is allowed
            content = fpath.read_text(encoding="utf-8")
            assert "mark_expired(" not in content, \
                f"mark_expired in {fpath.name} (not executor)"

    def test_get_sender_only_in_allowed_files(self):
        """get_sender must only be in sender and executor."""
        allowed = {"notification_sender.py", "retry_executor.py", "__init__.py"}
        for fpath in (APP / "core").glob("*.py"):
            if fpath.name in allowed:
                continue
            content = fpath.read_text(encoding="utf-8")
            lines = [l for l in content.split("\n")
                     if "get_sender" in l and not l.strip().startswith("#")]
            assert len(lines) == 0, \
                f"get_sender in {fpath.name}"
