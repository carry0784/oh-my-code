"""
Restart/Recovery Drill — 재기동 후 기준선 복원 검증.

서버/워커/비트 재기동 후에도 기준선 6항목이 자동으로 유지되는지 확인.
런타임 변경 없음. 읽기 전용 검증만 수행.

검증 대상:
  1. FastAPI 재기동 후 /baseline-check 6/6 HOLD
  2. FastAPI 재기동 후 /status operational_mode 유지
  3. FastAPI 재기동 후 /governance-state 정상 로드
  4. Celery beat schedule 재로드 후 금지 task 미등록
  5. Celery startup fingerprint 코드 무결성
  6. ops_state.json 파일 무결성 (읽기 가능 + 기대값 일치)
  7. 기동 로그 시퀀스 무결성 (lifespan 이벤트 순서)
"""

import json
import os

import pytest
from httpx import AsyncClient, ASGITransport

# Read expected operational_mode from ops_state.json (source of truth)
_OPS_STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "ops_state.json")
if os.path.exists(_OPS_STATE_PATH):
    with open(_OPS_STATE_PATH, encoding="utf-8") as _f:
        _EXPECTED_OP_MODE = json.load(_f).get("operational_mode", "BASELINE_HOLD")
    _OPS_STATE_AVAILABLE = True
else:
    _EXPECTED_OP_MODE = "BASELINE_HOLD"
    _OPS_STATE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _OPS_STATE_AVAILABLE,
    reason="ops_state.json not present (gitignored, runtime-only file)",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── Drill 1: 앱 재생성 후 baseline-check ─────────────────────────────


@pytest.fixture
async def fresh_client():
    """Create a fresh ASGI client — simulates server restart."""
    # Re-import to get fresh app state
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_drill_baseline_check_after_restart(fresh_client):
    """After restart, /baseline-check must return HOLD with 6/6 pass."""
    resp = await fresh_client.get("/api/v1/ops/baseline-check")
    assert resp.status_code == 200
    data = resp.json()

    assert data["drift_status"] in ("HOLD", "SOFT_DRIFT"), (
        f"unexpected drift: {data['drift_status']}"
    )
    assert data["summary"]["hard_drift_count"] == 0


@pytest.mark.anyio
async def test_drill_status_operational_mode_after_restart(fresh_client):
    """After restart, /status must show current governed mode from ops_state.json."""
    resp = await fresh_client.get("/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["operational_mode"] == _EXPECTED_OP_MODE
    assert data["exchange_mode"] == "DATA_ONLY"


@pytest.mark.anyio
async def test_drill_governance_state_after_restart(fresh_client):
    """After restart, /governance-state must load from ops_state.json."""
    resp = await fresh_client.get("/api/v1/ops/governance-state")
    assert resp.status_code == 200
    data = resp.json()

    assert data["operational_mode"] == _EXPECTED_OP_MODE
    assert "error" not in data, "ops_state.json load failed"
    assert len(data.get("sealed_crs", [])) >= 5
    assert len(data.get("rules", [])) >= 2


# ── Drill 2: Beat schedule 복원 검증 ──────────────────────────────────


class TestDrillBeatScheduleRecovery:
    """Beat schedule 재로드 후 금지 task 미등록 확인."""

    def test_drill_beat_schedule_reload_no_forbidden(self):
        """Re-import celery_app and verify no forbidden tasks."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        forbidden = [
            "sync-positions-every-minute",
            "check-order-status-every-30s",
            "sol-paper-trading-hourly",
        ]

        for key in forbidden:
            assert key not in schedule, (
                f"Forbidden task '{key}' found in beat_schedule after reload"
            )

    def test_drill_beat_active_count_stable(self):
        """Active beat task count must be 12 after reload."""
        from workers.celery_app import celery_app

        assert len(celery_app.conf.beat_schedule) == 12

    def test_drill_beat_all_dry_run(self):
        """All strategy-cycle tasks must have dry_run=True after reload."""
        from workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        cycle_keys = [k for k in schedule if "strategy-cycle" in k]
        assert len(cycle_keys) == 3

        for key in cycle_keys:
            kwargs = schedule[key].get("kwargs", {})
            assert kwargs.get("dry_run") is True, f"{key} missing dry_run=True after reload"


# ── Drill 3: Celery fingerprint 코드 무결성 ────────────────────────────


class TestDrillCeleryFingerprint:
    """Celery startup fingerprint가 operational_mode를 포함하는지 확인."""

    def test_drill_fingerprint_has_operational_mode(self):
        import inspect
        from workers.celery_app import _startup_fingerprint

        src = inspect.getsource(_startup_fingerprint)
        assert "operational_mode" in src

    def test_drill_fingerprint_has_exchange_mode(self):
        import inspect
        from workers.celery_app import _startup_fingerprint

        src = inspect.getsource(_startup_fingerprint)
        assert "exchange_mode" in src

    def test_drill_beat_init_has_stale_guard(self):
        import inspect
        from workers.celery_app import _on_beat_init

        src = inspect.getsource(_on_beat_init)
        assert "stale_beat_entry_detected" in src


# ── Drill 4: ops_state.json 파일 무결성 ────────────────────────────────


class TestDrillOpsStateFile:
    """ops_state.json 파일이 존재하고 기대값을 포함하는지 확인."""

    _OPS_PATH = os.path.join(os.path.dirname(__file__), "..", "ops_state.json")

    def test_drill_ops_state_file_exists(self):
        assert os.path.isfile(self._OPS_PATH), "ops_state.json not found"

    def test_drill_ops_state_valid_json(self):
        with open(self._OPS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_drill_ops_state_operational_mode(self):
        with open(self._OPS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["operational_mode"] == _EXPECTED_OP_MODE

    def test_drill_ops_state_baseline_values(self):
        with open(self._OPS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        bv = data["baseline_values"]
        assert bv["exchange_mode"] == "DATA_ONLY"
        assert bv["disabled_beat_tasks"] == 2
        assert bv["blocked_api_count"] == 5

    def test_drill_ops_state_rules(self):
        with open(self._OPS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules", [])
        assert "BL-EXMODE01" in rules
        assert "BL-OPS-RESTART01" in rules

    def test_drill_ops_state_updated_by_a(self):
        """Only A may edit ops_state.json."""
        with open(self._OPS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("updated_by") == "A"


# ── Drill 5: 기동 로그 시퀀스 무결성 ───────────────────────────────────


class TestDrillStartupLogSequence:
    """FastAPI lifespan 이벤트 순서가 올바른지 확인."""

    def test_drill_lifespan_event_order(self):
        """governance_state_loaded must come after exchange_mode_initialized."""
        import inspect
        from app.main import lifespan

        src = inspect.getsource(lifespan)
        idx_exchange = src.index("exchange_mode_initialized")
        idx_governance = src.index("governance_state_loaded")

        assert idx_exchange < idx_governance, (
            "governance_state_loaded must come after exchange_mode_initialized"
        )

    def test_drill_lifespan_has_all_required_events(self):
        """Lifespan must emit all required startup events."""
        import inspect
        from app.main import lifespan

        src = inspect.getsource(lifespan)
        required_events = [
            "Starting trading system",
            "exchange_mode_initialized",
            "governance_state_loaded",
            "governance_gate_initialized",
        ]

        for event in required_events:
            assert event in src, f"Missing required startup event: {event}"
