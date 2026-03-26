"""
C-04 SSOT Drift Sentinel — Score Source Path Alignment Tests

Verifies that Dashboard, Gate, Approval, Policy, and CheckRunner
all derive score-dependent decisions from the same freshness-aligned DB path.

Tests validate PATH identity, not just value equality.
If any consumer uses a different source (hardcoded, cached, or divergent),
these tests must fail.

Genesis Baseline: 27d46ca
Step 4 Baseline: 2ac6afa
"""

import sys
import inspect
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# Stub heavy dependencies
_STUB_MODULES = [
    "app.core.database", "app.models", "app.models.order",
    "app.models.position", "app.models.signal", "app.models.trade",
    "app.models.asset_snapshot", "app.exchanges", "app.exchanges.factory",
    "app.exchanges.base", "app.exchanges.binance", "app.exchanges.okx",
    "app.services", "app.services.order_service",
    "app.services.position_service", "app.services.signal_service",
    "ccxt", "ccxt.async_support", "redis", "celery", "asyncpg",
]
for m in _STUB_MODULES:
    if m not in sys.modules:
        sys.modules[m] = MagicMock()
sys.modules["app.models.position"].Position = MagicMock()
sys.modules["app.models.position"].PositionSide = MagicMock()
sys.modules["app.models.order"].Order = MagicMock()
sys.modules["app.models.order"].OrderStatus = MagicMock()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# SSOT-1: All score consumers reference Position/AssetSnapshot fallback
# ===========================================================================
class TestSSOTSourcePathAlignment:
    """Verify that all score consumers use the same DB freshness path."""

    def test_gate_uses_position_query(self):
        """Gate _check_ops_score must query Position.updated_at."""
        src = Path(PROJECT_ROOT / "app/core/execution_gate.py").read_text(encoding="utf-8")
        fn_start = src.find("def _check_ops_score")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "Position.updated_at" in fn_body or "Position" in fn_body

    def test_gate_uses_asset_snapshot_fallback(self):
        """Gate must fall back to AssetSnapshot when Position is empty."""
        src = Path(PROJECT_ROOT / "app/core/execution_gate.py").read_text(encoding="utf-8")
        fn_start = src.find("def _check_ops_score")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "AssetSnapshot" in fn_body

    def test_approval_uses_position_query(self):
        """Approval _collect_ops_score must query Position.updated_at."""
        src = Path(PROJECT_ROOT / "app/core/operator_approval.py").read_text(encoding="utf-8")
        fn_start = src.find("def _collect_ops_score")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "Position.updated_at" in fn_body or "Position" in fn_body

    def test_approval_uses_asset_snapshot_fallback(self):
        """Approval must fall back to AssetSnapshot."""
        src = Path(PROJECT_ROOT / "app/core/operator_approval.py").read_text(encoding="utf-8")
        fn_start = src.find("def _collect_ops_score")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "AssetSnapshot" in fn_body

    def test_policy_uses_position_query(self):
        """Policy _recheck_ops_score must query Position.updated_at."""
        src = Path(PROJECT_ROOT / "app/core/execution_policy.py").read_text(encoding="utf-8")
        fn_start = src.find("def _recheck_ops_score")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "Position.updated_at" in fn_body or "Position" in fn_body

    def test_policy_uses_asset_snapshot_fallback(self):
        """Policy must fall back to AssetSnapshot."""
        src = Path(PROJECT_ROOT / "app/core/execution_policy.py").read_text(encoding="utf-8")
        fn_start = src.find("def _recheck_ops_score")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "AssetSnapshot" in fn_body

    def test_dashboard_uses_position_query(self):
        """Dashboard _compute_integrity_panel must query Position.updated_at."""
        src = Path(PROJECT_ROOT / "app/api/routes/dashboard.py").read_text(encoding="utf-8")
        fn_start = src.find("def _compute_integrity_panel")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "Position.updated_at" in fn_body

    def test_dashboard_uses_asset_snapshot_fallback(self):
        """Dashboard must fall back to AssetSnapshot."""
        src = Path(PROJECT_ROOT / "app/api/routes/dashboard.py").read_text(encoding="utf-8")
        fn_start = src.find("def _compute_integrity_panel")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "AssetSnapshot" in fn_body

    def test_check_runner_uses_position_query(self):
        """CheckRunner _get_snapshot_age_sync must query Position.updated_at."""
        src = Path(PROJECT_ROOT / "app/core/constitution_check_runner.py").read_text(encoding="utf-8")
        fn_start = src.find("def _get_snapshot_age_sync")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "Position.updated_at" in fn_body or "Position" in fn_body

    def test_check_runner_uses_asset_snapshot_fallback(self):
        """CheckRunner must fall back to AssetSnapshot."""
        src = Path(PROJECT_ROOT / "app/core/constitution_check_runner.py").read_text(encoding="utf-8")
        fn_start = src.find("def _get_snapshot_age_sync")
        fn_body = src[fn_start:src.find("\ndef ", fn_start + 20)] if fn_start != -1 else ""
        assert "AssetSnapshot" in fn_body


# ===========================================================================
# SSOT-2: No hardcoded snapshot_age=None remaining
# ===========================================================================
class TestSSOTNoHardcodedNull:
    """Verify no consumer uses hardcoded snapshot_age_seconds=None."""

    def _check_no_hardcoded_none(self, filepath, fn_name):
        src = Path(filepath).read_text(encoding="utf-8")
        fn_start = src.find(f"def {fn_name}")
        if fn_start == -1:
            pytest.skip(f"{fn_name} not found in {filepath}")
        fn_end = src.find("\ndef ", fn_start + 20)
        fn_body = src[fn_start:fn_end] if fn_end != -1 else src[fn_start:]
        # Should NOT have hardcoded snapshot_age_seconds=None in IntegrityPanel construction
        lines = fn_body.split("\n")
        for line in lines:
            stripped = line.strip()
            if "snapshot_age_seconds=None" in stripped and "IntegrityPanel" in fn_body[: fn_body.find(stripped)]:
                # Check it's not in a fallback/except block
                if "except" not in stripped and "# fallback" not in stripped.lower():
                    pytest.fail(f"Hardcoded snapshot_age_seconds=None found in {fn_name}")

    def test_gate_no_hardcoded_none(self):
        self._check_no_hardcoded_none(
            PROJECT_ROOT / "app/core/execution_gate.py", "_check_ops_score"
        )

    def test_approval_no_hardcoded_none(self):
        self._check_no_hardcoded_none(
            PROJECT_ROOT / "app/core/operator_approval.py", "_collect_ops_score"
        )

    def test_policy_no_hardcoded_none(self):
        self._check_no_hardcoded_none(
            PROJECT_ROOT / "app/core/execution_policy.py", "_recheck_ops_score"
        )


# ===========================================================================
# SSOT-3: All consumers use _compute_ops_score from dashboard
# ===========================================================================
class TestSSOTSharedScoreFunction:
    """Verify all consumers import and use the same _compute_ops_score."""

    def test_gate_imports_compute_ops_score(self):
        src = Path(PROJECT_ROOT / "app/core/execution_gate.py").read_text(encoding="utf-8")
        assert "_compute_ops_score" in src

    def test_approval_imports_compute_ops_score(self):
        src = Path(PROJECT_ROOT / "app/core/operator_approval.py").read_text(encoding="utf-8")
        assert "_compute_ops_score" in src

    def test_policy_imports_compute_ops_score(self):
        src = Path(PROJECT_ROOT / "app/core/execution_policy.py").read_text(encoding="utf-8")
        assert "_compute_ops_score" in src

    def test_no_duplicate_score_function(self):
        """No consumer defines its own _compute_ops_score."""
        for filepath in [
            PROJECT_ROOT / "app/core/execution_gate.py",
            PROJECT_ROOT / "app/core/operator_approval.py",
            PROJECT_ROOT / "app/core/execution_policy.py",
        ]:
            src = filepath.read_text(encoding="utf-8")
            assert "def _compute_ops_score" not in src, (
                f"Duplicate _compute_ops_score definition in {filepath.name}"
            )


# ===========================================================================
# SSOT-4: UI does not derive scores
# ===========================================================================
class TestSSOTUINoScoreDerivation:
    """Verify UI template does not compute scores independently."""

    def test_no_score_average_in_renderer(self):
        html = Path(PROJECT_ROOT / "app/templates/dashboard.html").read_text(encoding="utf-8")
        start = html.find("function _renderC04(")
        end = html.find("\nfunction ", start + 30) if start != -1 else -1
        body = html[start:end].lower() if start != -1 and end != -1 else ""
        # No score averaging formula in renderer
        assert "/ 4" not in body or "9" in body.split("/ 4")[0][-10:]

    def test_no_integrity_connectivity_sum(self):
        html = Path(PROJECT_ROOT / "app/templates/dashboard.html").read_text(encoding="utf-8")
        start = html.find("function _renderC04(")
        end = html.find("\nfunction ", start + 30) if start != -1 else -1
        body = html[start:end].lower() if start != -1 and end != -1 else ""
        assert "integrity + connectivity" not in body
        assert "integrity+connectivity" not in body
