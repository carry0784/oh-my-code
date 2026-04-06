"""
Tests for CR-049 operational visibility endpoints + BL-EXMODE01 rule.

Verifies:
  1. /api/v1/ops/exchange-mode returns correct mode and API matrix
  2. /api/v1/ops/beat-tasks returns all tasks with status/reason codes
  3. /api/v1/ops/blocked-operations returns blocked APIs and tasks
  4. /status includes exchange_mode field
  5. DATA_ONLY blocks 5 private APIs, permits 2 public APIs
  6. Disabled tasks have valid reason codes
  7. BL-EXMODE01 rule document exists
  8. Startup logs exchange_mode
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── /api/v1/ops/exchange-mode ──────────────────────────────────────


@pytest.mark.anyio
async def test_exchange_mode_endpoint(client):
    resp = await client.get("/api/v1/ops/exchange-mode")
    assert resp.status_code == 200
    data = resp.json()

    assert data["exchange_mode"] == "DATA_ONLY"
    assert data["contract"] == "BL-EXMODE01"
    assert data["cr_ref"] == "CR-049"


@pytest.mark.anyio
async def test_exchange_mode_api_permissions(client):
    """DATA_ONLY: fetch_ticker/fetch_ohlcv allowed, 5 private APIs blocked."""
    resp = await client.get("/api/v1/ops/exchange-mode")
    perms = resp.json()["api_permissions"]

    # Public APIs — allowed in DATA_ONLY
    assert perms["fetch_ticker"]["allowed"] is True
    assert perms["fetch_ohlcv"]["allowed"] is True

    # Private APIs — blocked in DATA_ONLY
    for api in ["fetch_balance", "fetch_positions", "fetch_order", "cancel_order", "create_order"]:
        assert perms[api]["allowed"] is False, f"{api} should be blocked in DATA_ONLY"


@pytest.mark.anyio
async def test_exchange_mode_adapters(client):
    """All 5 adapters listed with guard enforcement."""
    resp = await client.get("/api/v1/ops/exchange-mode")
    adapters = resp.json()["adapters"]

    adapter_names = {a["name"] for a in adapters}
    assert adapter_names == {"binance", "bitget", "upbit", "kis", "kiwoom"}

    for adapter in adapters:
        assert adapter["guard"] == "_require_mode()"
        assert adapter["enforcement"] == "adapter-level"


# ── /api/v1/ops/beat-tasks ─────────────────────────────────────────


@pytest.mark.anyio
async def test_beat_tasks_endpoint(client):
    resp = await client.get("/api/v1/ops/beat-tasks")
    assert resp.status_code == 200
    data = resp.json()

    assert data["exchange_mode"] == "DATA_ONLY"
    assert data["summary"]["total"] > 0
    assert data["summary"]["active"] > 0
    assert data["summary"]["disabled"] > 0


@pytest.mark.anyio
async def test_beat_tasks_disabled_have_reason_codes(client):
    """Every disabled task must have a valid reason_code."""
    resp = await client.get("/api/v1/ops/beat-tasks")
    data = resp.json()
    reason_codes = data["reason_codes"]

    for task in data["tasks"]:
        if task["status"] == "DISABLED":
            assert task["reason_code"] is not None, (
                f"Disabled task {task['schedule_label']} missing reason_code"
            )
            assert task["reason_code"] in reason_codes, (
                f"Reason code {task['reason_code']} not in registry"
            )


@pytest.mark.anyio
async def test_beat_tasks_cr049_disabled(client):
    """sync_all_positions and check_pending_orders disabled by CR-049."""
    resp = await client.get("/api/v1/ops/beat-tasks")
    tasks = resp.json()["tasks"]

    cr049_disabled = [t for t in tasks if t["cr_ref"] == "CR-049" and t["status"] == "DISABLED"]
    labels = {t["schedule_label"] for t in cr049_disabled}
    assert "sync-positions-every-minute" in labels
    assert "check-order-status-every-30s" in labels


@pytest.mark.anyio
async def test_beat_tasks_active_tasks_present(client):
    """Core active tasks present: market data collection, signal expiry, snapshots."""
    resp = await client.get("/api/v1/ops/beat-tasks")
    tasks = resp.json()["tasks"]

    active_labels = {t["schedule_label"] for t in tasks if t["status"] == "ACTIVE"}
    assert "collect-market-state-every-5m (BTC)" in active_labels
    assert "expire-old-signals" in active_labels
    assert "record-asset-snapshot-every-5m" in active_labels


# ── /api/v1/ops/blocked-operations ─────────────────────────────────


@pytest.mark.anyio
async def test_blocked_operations_endpoint(client):
    resp = await client.get("/api/v1/ops/blocked-operations")
    assert resp.status_code == 200
    data = resp.json()

    assert data["exchange_mode"] == "DATA_ONLY"
    assert data["blocked_api_count"] == 5  # 5 private APIs
    assert data["blocked_task_count"] == 3  # 3 disabled tasks


@pytest.mark.anyio
async def test_blocked_apis_have_enforcement_info(client):
    """Each blocked API has exception type and enforcement mechanism."""
    resp = await client.get("/api/v1/ops/blocked-operations")
    for api in resp.json()["blocked_apis"]:
        assert api["exception"] == "OperationNotPermitted"
        assert "_require_mode()" in api["enforcement"]


@pytest.mark.anyio
async def test_blocked_tasks_have_re_enable_info(client):
    """Each blocked task specifies when it can be re-enabled."""
    resp = await client.get("/api/v1/ops/blocked-operations")
    for task in resp.json()["blocked_tasks"]:
        assert task["re_enable_when"] is not None
        assert task["reason_detail"] != "Unknown"


# ── /status (exchange_mode + operational_mode integration) ─────────


@pytest.mark.anyio
async def test_status_includes_exchange_mode(client):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()

    assert "exchange_mode" in data
    assert data["exchange_mode"] == "DATA_ONLY"
    assert data["sources"]["exchange_mode"] == "DATA_ONLY"


@pytest.mark.anyio
async def test_status_includes_operational_mode(client):
    """GET /status includes operational_mode from ops_state.json."""
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()

    assert "operational_mode" in data
    # ops_state.json exists → should not be UNKNOWN
    assert data["operational_mode"] != "UNKNOWN"
    assert data["sources"]["operational_mode"] == data["operational_mode"]


# ── /api/v1/ops/governance-state ──────────────────────────────────


@pytest.mark.anyio
async def test_governance_state_endpoint(client):
    """GET /api/v1/ops/governance-state returns ops_state.json content."""
    resp = await client.get("/api/v1/ops/governance-state")
    assert resp.status_code == 200
    data = resp.json()

    assert "operational_mode" in data
    assert "sealed_crs" in data
    assert "rules" in data
    assert "prohibitions" in data
    assert "last_updated" in data
    assert "updated_by" in data


@pytest.mark.anyio
async def test_governance_state_baseline_values(client):
    """Governance state baseline_values match runtime contract."""
    resp = await client.get("/api/v1/ops/governance-state")
    data = resp.json()

    bv = data.get("baseline_values", {})
    assert bv.get("exchange_mode") == "DATA_ONLY"
    assert bv.get("disabled_beat_tasks") == 2
    assert bv.get("blocked_api_count") == 5


@pytest.mark.anyio
async def test_governance_state_rules_present(client):
    """BL-EXMODE01 and BL-OPS-RESTART01 listed in governance rules."""
    resp = await client.get("/api/v1/ops/governance-state")
    rules = resp.json().get("rules", [])

    assert "BL-EXMODE01" in rules
    assert "BL-OPS-RESTART01" in rules


@pytest.mark.anyio
async def test_governance_state_read_only(client):
    """No write endpoint exists — POST/PUT/DELETE should 405."""
    for method in ["post", "put", "delete", "patch"]:
        resp = await getattr(client, method)("/api/v1/ops/governance-state")
        assert resp.status_code == 405, f"{method.upper()} should be 405"


# ── /api/v1/ops/baseline-check (자동 기준선 점검) ──────────────────────


@pytest.mark.anyio
async def test_baseline_check_endpoint(client):
    """GET /api/v1/ops/baseline-check returns drift status and checks."""
    resp = await client.get("/api/v1/ops/baseline-check")
    assert resp.status_code == 200
    data = resp.json()

    assert "drift_status" in data
    assert "summary" in data
    assert "checks" in data
    assert "measured_at" in data
    assert data["baseline_source"] == "ops_state.json"


@pytest.mark.anyio
async def test_baseline_check_all_pass(client):
    """All 6 baseline checks should pass in current state."""
    resp = await client.get("/api/v1/ops/baseline-check")
    data = resp.json()

    assert data["drift_status"] == "HOLD"
    assert data["summary"]["passed"] == 6
    assert data["summary"]["failed"] == 0
    assert data["summary"]["hard_drift_count"] == 0
    assert data["summary"]["soft_drift_count"] == 0


@pytest.mark.anyio
async def test_baseline_check_items_complete(client):
    """All 6 observation items are present in checks."""
    resp = await client.get("/api/v1/ops/baseline-check")
    items = {c["item"] for c in resp.json()["checks"]}

    assert "operational_mode" in items
    assert "exchange_mode" in items
    assert "blocked_api_count" in items
    assert "disabled_beat_tasks" in items
    assert "forbidden_beat_tasks_absent" in items
    assert "startup_log_consistency" in items


@pytest.mark.anyio
async def test_baseline_check_expected_values(client):
    """Each check reports correct expected baseline values."""
    resp = await client.get("/api/v1/ops/baseline-check")
    checks = {c["item"]: c for c in resp.json()["checks"]}

    assert checks["operational_mode"]["expected"] in ("BASELINE_HOLD", "GUARDED_RELEASE")
    assert checks["exchange_mode"]["expected"] == "DATA_ONLY"
    assert checks["blocked_api_count"]["expected"] == 5
    assert checks["disabled_beat_tasks"]["expected"] == 2


# ── /api/v1/ops/change-gate (변경 재진입 Gate) ─────────────────────────


@pytest.mark.anyio
async def test_change_gate_endpoint(client):
    """GET /api/v1/ops/change-gate returns gate status."""
    resp = await client.get("/api/v1/ops/change-gate")
    assert resp.status_code == 200
    data = resp.json()

    assert "gate_status" in data
    assert "operational_mode" in data
    assert "reentry_allowed" in data
    assert "approval_required" in data
    assert "blocked_reasons" in data
    assert "required_checks" in data
    assert "path_risk_reference" in data


@pytest.mark.anyio
async def test_change_gate_locked_during_governed_mode(client):
    """During BASELINE_HOLD or GUARDED_RELEASE, gate_status is LOCKED and L3/L4 blocked."""
    resp = await client.get("/api/v1/ops/change-gate")
    data = resp.json()

    assert data["gate_status"] == "LOCKED"
    assert data["operational_mode"] in ("BASELINE_HOLD", "GUARDED_RELEASE")

    allowed = data["reentry_allowed"]
    assert allowed["L0"] is True
    assert allowed["L1"] is True
    # L2: True during BASELINE_HOLD, False during GUARDED_RELEASE (24h review)
    assert allowed["L3"] is False
    assert allowed["L4"] is False


@pytest.mark.anyio
async def test_change_gate_blocked_reasons(client):
    """Blocked reasons include governed mode name and prohibitions."""
    resp = await client.get("/api/v1/ops/change-gate")
    reasons = resp.json()["blocked_reasons"]

    assert len(reasons) > 0
    assert any("BASELINE_HOLD" in r or "GUARDED_RELEASE" in r for r in reasons)
    assert any("L4" in r for r in reasons)


@pytest.mark.anyio
async def test_change_gate_required_checks(client):
    """Required checks list includes baseline-check and regression."""
    resp = await client.get("/api/v1/ops/change-gate")
    checks = resp.json()["required_checks"]

    check_names = {c["check"] for c in checks}
    assert "baseline-check" in check_names
    assert "회귀 테스트" in check_names
    assert "restart drill" in check_names


@pytest.mark.anyio
async def test_change_gate_path_risk_reference(client):
    """Path risk reference includes key paths with levels."""
    resp = await client.get("/api/v1/ops/change-gate")
    paths = resp.json()["path_risk_reference"]

    path_map = {p["path"]: p["level"] for p in paths}
    assert path_map.get("docs/") == "L0"
    assert path_map.get("tests/") == "L1"
    assert "L4" in path_map.get("exchanges/", "")


@pytest.mark.anyio
async def test_change_gate_policy_docs_referenced(client):
    """Gate response references policy documents."""
    resp = await client.get("/api/v1/ops/change-gate")
    data = resp.json()

    assert "change_gate_policy" in data["policy_doc"]
    assert "change_scope_matrix" in data["scope_matrix"]
    assert "change_reentry_review_template" in data["review_template"]


# ── BL-EXMODE01 rule document existence ────────────────────────────


def test_bl_exmode01_document_exists():
    """BL-EXMODE01 rule document must exist in architecture docs."""
    doc_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "architecture", "bl_exmode01.md"
    )
    assert os.path.isfile(doc_path), "BL-EXMODE01 rule document not found"

    with open(doc_path, encoding="utf-8") as f:
        content = f.read()

    # Key sections must exist
    assert "BL-EXMODE01" in content
    assert "DATA_ONLY" in content
    assert "PAPER" in content
    assert "LIVE" in content
    assert "_require_mode()" in content
    assert "OperationNotPermitted" in content


def test_bl_exmode01_mode_enum_consistency():
    """ExchangeMode enum values match BL-EXMODE01 contract."""
    from exchanges.base import ExchangeMode

    assert ExchangeMode.DATA_ONLY.value == "DATA_ONLY"
    assert ExchangeMode.PAPER.value == "PAPER"
    assert ExchangeMode.LIVE.value == "LIVE"
    assert len(ExchangeMode) == 3


def test_bl_exmode01_config_default():
    """Default exchange_mode in config is DATA_ONLY."""
    from app.core.config import settings

    assert settings.exchange_mode == "DATA_ONLY"


def test_bl_exmode01_operation_not_permitted_raises():
    """OperationNotPermitted is a RuntimeError subclass."""
    from exchanges.base import OperationNotPermitted

    assert issubclass(OperationNotPermitted, RuntimeError)

    exc = OperationNotPermitted("test message")
    assert "test message" in str(exc)
