"""
Card C-40: Execution Boundary Lock — Structural enforcement tests

Purpose:
  Enforce that execute_single_plan() is the SOLE retry execution
  entry point. No auto/manual/operator path may bypass it.

Rules:
  - execute_single_plan() = retry execution SSOT
  - Direct sender calls (get_sender) forbidden in orchestration layers
  - All retry execution must flow through C-31 public helper
  - Bypass = immediate NO-GO

Scope:
  Test-only card. No production code changes.
  Structural enforcement via static analysis tests.

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Files that MUST use execute_single_plan for retry execution
ORCHESTRATOR_PATH = PROJECT_ROOT / "app" / "core" / "auto_retry_orchestrator.py"
EXECUTOR_PATH = PROJECT_ROOT / "app" / "core" / "retry_executor.py"
FLOW_PATH = PROJECT_ROOT / "app" / "core" / "notification_flow.py"
BRIDGE_PATH = PROJECT_ROOT / "app" / "core" / "flow_retry_bridge.py"
OPERATOR_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "operator_retry.py"

# Files that DEFINE execute_single_plan (allowed to import get_sender)
SSOT_DEFINITION_FILE = EXECUTOR_PATH


# ===========================================================================
# C40-1: SSOT 존재 확인
# ===========================================================================
class TestC40SSOTExists:

    def test_execute_single_plan_defined(self):
        """execute_single_plan must exist as public function in C-31."""
        content = SSOT_DEFINITION_FILE.read_text(encoding="utf-8")
        assert "def execute_single_plan(" in content

    def test_execute_single_plan_is_public(self):
        """Must not start with underscore."""
        from app.core.retry_executor import execute_single_plan
        assert not execute_single_plan.__name__.startswith("_")

    def test_execute_single_plan_importable(self):
        """Must be importable from retry_executor."""
        from app.core.retry_executor import execute_single_plan
        assert callable(execute_single_plan)

    def test_reason_prefix_parameter(self):
        """Must accept reason_prefix for caller identification."""
        content = SSOT_DEFINITION_FILE.read_text(encoding="utf-8")
        assert "reason_prefix" in content


# ===========================================================================
# C40-2: C-38 orchestrator — sender 직접 호출 금지
# ===========================================================================
class TestC40OrchestratorBoundary:

    def test_no_get_sender_import(self):
        """C-38 must NOT import get_sender directly."""
        content = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        lines = [l for l in content.split("\n")
                 if "get_sender" in l
                 and not l.strip().startswith("#")]
        assert len(lines) == 0, f"Direct get_sender usage found: {lines}"

    def test_no_send_webhook(self):
        """C-38 must NOT call send_webhook directly."""
        content = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        assert "send_webhook" not in content

    def test_no_send_notifications(self):
        """C-38 must NOT call send_notifications directly."""
        content = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        assert "send_notifications" not in content

    def test_no_private_execute_single(self):
        """C-38 must NOT have its own _execute_single."""
        content = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        assert "def _execute_single(" not in content

    def test_uses_execute_single_plan(self):
        """C-38 MUST use execute_single_plan from C-31."""
        content = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        assert "execute_single_plan" in content

    def test_auto_retry_prefix(self):
        """C-38 must use auto_retry reason prefix."""
        content = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        assert 'reason_prefix="auto_retry"' in content


# ===========================================================================
# C40-3: C-31 executor — SSOT 정의 파일 검수
# ===========================================================================
class TestC40ExecutorSSOT:

    def test_executor_defines_helper(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "def execute_single_plan(" in content

    def test_executor_uses_own_helper(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        # Internal call must use the public name
        assert "execute_single_plan(" in content
        assert "def _execute_single_retry(" not in content

    def test_executor_retry_prefix(self):
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert 'reason_prefix="retry"' in content

    def test_only_executor_has_get_sender(self):
        """Only the SSOT file should import get_sender for retry execution."""
        content = EXECUTOR_PATH.read_text(encoding="utf-8")
        assert "get_sender" in content  # SSOT is allowed


# ===========================================================================
# C40-4: notification_flow — sender 직접 호출 경계
# ===========================================================================
class TestC40FlowBoundary:

    def test_manual_retry_uses_executor(self):
        """run_manual_retry_pass must call execute_retry_pass, not sender."""
        content = FLOW_PATH.read_text(encoding="utf-8")
        # Manual path uses execute_retry_pass which uses execute_single_plan
        assert "execute_retry_pass" in content

    def test_no_execute_single_plan_direct(self):
        """Flow should not call execute_single_plan directly."""
        content = FLOW_PATH.read_text(encoding="utf-8")
        assert "execute_single_plan" not in content


# ===========================================================================
# C40-5: bridge — sender 직접 호출 금지
# ===========================================================================
class TestC40BridgeBoundary:

    def test_bridge_no_sender_call(self):
        """Bridge must NOT call get_sender or send_notifications."""
        content = BRIDGE_PATH.read_text(encoding="utf-8")
        assert "get_sender" not in content
        assert "send_notifications" not in content
        assert "send_webhook" not in content

    def test_bridge_no_execute_single(self):
        """Bridge must NOT execute retries directly."""
        content = BRIDGE_PATH.read_text(encoding="utf-8")
        assert "execute_single_plan" not in content
        assert "execute_retry_pass" not in content


# ===========================================================================
# C40-6: operator endpoint — sender 직접 호출 금지
# ===========================================================================
class TestC40OperatorBoundary:

    def test_operator_no_sender(self):
        """Operator endpoint must NOT import sender directly."""
        content = OPERATOR_PATH.read_text(encoding="utf-8")
        assert "get_sender" not in content
        assert "send_webhook" not in content

    def test_operator_uses_manual_path(self):
        """Operator must use run_manual_retry_pass."""
        content = OPERATOR_PATH.read_text(encoding="utf-8")
        assert "run_manual_retry_pass" in content

    def test_operator_no_execute_single(self):
        """Operator must NOT call execute_single_plan directly."""
        content = OPERATOR_PATH.read_text(encoding="utf-8")
        assert "execute_single_plan" not in content


# ===========================================================================
# C40-7: 전체 retry 계층 — execution 경로 단일성
# ===========================================================================
class TestC40ExecutionPathUnity:

    def test_only_executor_defines_single_plan(self):
        """execute_single_plan must be defined in exactly one file."""
        retry_files = list((PROJECT_ROOT / "app" / "core").glob("*.py"))
        defining_files = []
        for f in retry_files:
            content = f.read_text(encoding="utf-8")
            if "def execute_single_plan(" in content:
                defining_files.append(f.name)
        assert defining_files == ["retry_executor.py"], \
            f"SSOT violation: defined in {defining_files}"

    def test_no_retry_layer_has_own_sender_execution(self):
        """No retry orchestration file should have its own sender call."""
        files_to_check = [
            ORCHESTRATOR_PATH,
            BRIDGE_PATH,
            OPERATOR_PATH,
        ]
        for fpath in files_to_check:
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8")
            lines = [l.strip() for l in content.split("\n")
                     if ("get_sender" in l or "send_webhook" in l)
                     and not l.strip().startswith("#")]
            assert len(lines) == 0, \
                f"Direct sender in {fpath.name}: {lines}"


# ===========================================================================
# C40-8: 금지 조항 총합
# ===========================================================================
class TestC40ForbiddenSummary:

    def test_no_forbidden_in_retry_stack(self):
        """No retry stack file should have forbidden debug strings."""
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace',
        ]
        files = [
            EXECUTOR_PATH, ORCHESTRATOR_PATH, BRIDGE_PATH,
            OPERATOR_PATH, FLOW_PATH,
        ]
        for fpath in files:
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8")
            body = content.split('"""', 2)[-1] if '"""' in content else content
            for f in forbidden:
                assert f not in body, \
                    f"Forbidden '{f}' in {fpath.name}"

    def test_no_engine_in_retry_stack(self):
        files = [
            EXECUTOR_PATH, ORCHESTRATOR_PATH, BRIDGE_PATH,
            OPERATOR_PATH,
        ]
        for fpath in files:
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8")
            assert "src.kdexter" not in content, \
                f"Engine import in {fpath.name}"
