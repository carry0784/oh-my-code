"""
Card C-33: Operator Retry Trigger — Tests

검수 범위:
  C33-1: 모듈 구조
  C33-2: POST retry-pass 호출
  C33-3: GET retry-status 호출
  C33-4: fail-closed
  C33-5: 자동 실행 없음
  C33-6: 금지 조항

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "operator_retry.py"


# ===========================================================================
# C33-1: 모듈 구조
# ===========================================================================
class TestC33ModuleStructure:
    def test_module_exists(self):
        assert ROUTE_PATH.exists()

    def test_has_retry_pass_endpoint(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert "retry-pass" in content

    def test_has_retry_status_endpoint(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert "retry-status" in content

    def test_has_router(self):
        from app.api.routes.operator_retry import router

        assert router is not None

    def test_docstring_forbids_auto(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert "automatic retry is forbidden" in content.lower()


# ===========================================================================
# C33-2: POST retry-pass
# ===========================================================================
class TestC33RetryPassEndpoint:
    @pytest.mark.asyncio
    async def test_retry_pass_returns_dict(self):
        from app.api.routes.operator_retry import operator_retry_pass

        result = await operator_retry_pass(max_executions=1)
        assert isinstance(result, dict)
        assert "triggered_at" in result

    @pytest.mark.asyncio
    async def test_retry_pass_has_success_field(self):
        from app.api.routes.operator_retry import operator_retry_pass

        result = await operator_retry_pass()
        assert "success" in result

    @pytest.mark.asyncio
    async def test_retry_pass_calls_manual_entrypoint(self):
        from app.api.routes.operator_retry import operator_retry_pass

        with patch("app.core.notification_flow.run_manual_retry_pass") as mock:
            mock.return_value = {"plans_attempted": 0, "plans_succeeded": 0}
            result = await operator_retry_pass()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_retry_pass_respects_max_executions(self):
        from app.api.routes.operator_retry import operator_retry_pass

        with patch("app.core.notification_flow.run_manual_retry_pass") as mock:
            mock.return_value = {"plans_attempted": 2}
            await operator_retry_pass(max_executions=2)
            args, kwargs = mock.call_args
            assert kwargs.get("max_executions") == 2 or (len(args) >= 2 and args[1] == 2)


# ===========================================================================
# C33-3: GET retry-status
# ===========================================================================
class TestC33RetryStatusEndpoint:
    @pytest.mark.asyncio
    async def test_retry_status_returns_dict(self):
        from app.api.routes.operator_retry import operator_retry_status

        result = await operator_retry_status()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_retry_status_has_available(self):
        from app.api.routes.operator_retry import operator_retry_status

        result = await operator_retry_status()
        assert "available" in result

    @pytest.mark.asyncio
    async def test_retry_status_shows_counts(self):
        from app.api.routes.operator_retry import operator_retry_status

        result = await operator_retry_status()
        if result.get("available"):
            assert "pending" in result
            assert "total" in result


# ===========================================================================
# C33-4: fail-closed
# ===========================================================================
class TestC33FailClosed:
    @pytest.mark.asyncio
    async def test_store_unavailable_handled(self):
        from app.api.routes.operator_retry import operator_retry_pass, _get_plan_store

        original = getattr(_get_plan_store, "_instance", None)
        try:
            _get_plan_store._instance = None
            with patch("app.api.routes.operator_retry._get_plan_store", return_value=None):
                result = await operator_retry_pass()
                assert result["success"] is False
                assert "unavailable" in result.get("error", "")
        finally:
            if original is not None:
                _get_plan_store._instance = original

    @pytest.mark.asyncio
    async def test_status_store_unavailable(self):
        from app.api.routes.operator_retry import operator_retry_status

        with patch("app.api.routes.operator_retry._get_plan_store", return_value=None):
            result = await operator_retry_status()
            assert result["available"] is False

    @pytest.mark.asyncio
    async def test_flow_error_handled(self):
        from app.api.routes.operator_retry import operator_retry_pass

        with patch(
            "app.core.notification_flow.run_manual_retry_pass", side_effect=RuntimeError("boom")
        ):
            result = await operator_retry_pass()
            assert result["success"] is False
            assert "error" in result


# ===========================================================================
# C33-5: 자동 실행 없음
# ===========================================================================
class TestC33NoAutoExecution:
    def test_import_no_side_effect(self):
        import app.api.routes.operator_retry  # noqa: F401
        # No exception = no auto execution

    def test_no_startup_hook(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert "on_startup" not in content
        assert "app.add_event" not in content

    def test_post_only_trigger(self):
        """retry-pass는 POST여야 한다."""
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert '.post("/retry-pass"' in content


# ===========================================================================
# C33-6: 금지 조항
# ===========================================================================
class TestC33Forbidden:
    def test_no_forbidden_strings(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            "chain_of_thought",
            "raw_prompt",
            "internal_reasoning",
            "debug_trace",
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_daemon(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        parts = content.split('"""')
        body = parts[-1] if len(parts) >= 3 else content
        assert "daemon" not in body.lower()
        assert "while true" not in body.lower()

    def test_no_engine_imports(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert "src.kdexter" not in content
        assert "from src" not in content

    def test_no_threading(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert "threading" not in content
        assert "asyncio.create_task" not in content
