"""
Card C-16: Receipt Persistence / Delivery Log — Tests

검수 범위:
  C16-1: 모듈 구조 및 데이터 모델
  C16-2: ReceiptStore CRUD 동작
  C16-3: Ring buffer cap
  C16-4: Fail-closed 동작
  C16-5: C-15 NotificationReceipt 호환
  C16-6: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

from pathlib import Path

import pytest

from app.core.notification_receipt_store import (
    StoredReceipt,
    ReceiptStore,
    DEFAULT_MAX_SIZE,
)
from app.core.notification_sender import (
    NotificationReceipt,
    ChannelResult,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORE_PATH = PROJECT_ROOT / "app" / "core" / "notification_receipt_store.py"


# ===========================================================================
# C16-1: 모듈 구조
# ===========================================================================
class TestC16ModuleStructure:
    def test_module_exists(self):
        assert STORE_PATH.exists()

    def test_stored_receipt_dataclass(self):
        r = StoredReceipt(receipt_id="RX-TEST", severity_tier="high")
        assert r.receipt_id == "RX-TEST"
        assert r.severity_tier == "high"

    def test_stored_receipt_to_dict(self):
        r = StoredReceipt(receipt_id="RX-01", channels_attempted=2)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["receipt_id"] == "RX-01"
        assert d["channels_attempted"] == 2

    def test_receipt_store_class_exists(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "class ReceiptStore" in content


# ===========================================================================
# C16-2: ReceiptStore CRUD
# ===========================================================================
class TestC16StoreCRUD:
    def test_store_returns_receipt_id(self):
        store = ReceiptStore()
        rid = store.store({"severity_tier": "low"})
        assert rid.startswith("RX-")

    def test_count_increments(self):
        store = ReceiptStore()
        assert store.count() == 0
        store.store({"severity_tier": "low"})
        assert store.count() == 1
        store.store({"severity_tier": "high"})
        assert store.count() == 2

    def test_latest_returns_most_recent(self):
        store = ReceiptStore()
        store.store({"severity_tier": "low"}, {"highest_incident": "FIRST"})
        store.store({"severity_tier": "high"}, {"highest_incident": "SECOND"})
        latest = store.latest()
        assert latest is not None
        assert latest["highest_incident"] == "SECOND"

    def test_latest_returns_none_when_empty(self):
        store = ReceiptStore()
        assert store.latest() is None

    def test_list_receipts_newest_first(self):
        store = ReceiptStore()
        store.store({"severity_tier": "low"}, {"highest_incident": "A"})
        store.store({"severity_tier": "high"}, {"highest_incident": "B"})
        items = store.list_receipts()
        assert items[0]["highest_incident"] == "B"
        assert items[1]["highest_incident"] == "A"

    def test_list_receipts_respects_limit(self):
        store = ReceiptStore()
        for i in range(10):
            store.store({"severity_tier": "low"})
        items = store.list_receipts(limit=3)
        assert len(items) == 3

    def test_clear_empties_store(self):
        store = ReceiptStore()
        store.store({"severity_tier": "low"})
        store.store({"severity_tier": "high"})
        store.clear()
        assert store.count() == 0
        assert store.latest() is None

    def test_stored_at_populated(self):
        store = ReceiptStore()
        store.store({"severity_tier": "low"})
        latest = store.latest()
        assert latest["stored_at"] != ""


# ===========================================================================
# C16-3: Ring buffer cap
# ===========================================================================
class TestC16RingBuffer:
    def test_default_max_size(self):
        assert DEFAULT_MAX_SIZE == 100

    def test_buffer_caps_at_max_size(self):
        store = ReceiptStore(max_size=5)
        for i in range(10):
            store.store({"severity_tier": "low"}, {"highest_incident": f"INC-{i}"})
        assert store.count() == 5
        # Oldest should be evicted
        items = store.list_receipts()
        assert items[0]["highest_incident"] == "INC-9"
        assert items[-1]["highest_incident"] == "INC-5"


# ===========================================================================
# C16-4: Fail-closed
# ===========================================================================
class TestC16FailClosed:
    def test_store_handles_none_receipt(self):
        store = ReceiptStore()
        rid = store.store(None)
        assert rid.startswith("RX-")

    def test_store_handles_empty_dict(self):
        store = ReceiptStore()
        rid = store.store({})
        assert rid.startswith("RX-")

    def test_store_handles_invalid_receipt_type(self):
        store = ReceiptStore()
        rid = store.store(42)
        assert rid.startswith("RX-")


# ===========================================================================
# C16-5: C-15 NotificationReceipt 호환
# ===========================================================================
class TestC16C15Compatibility:
    def test_stores_notification_receipt_dataclass(self):
        store = ReceiptStore()
        receipt = NotificationReceipt(
            attempted_at="2026-03-24T10:00:00Z",
            severity_tier="critical",
            channels_attempted=3,
            channels_delivered=2,
            results=[
                ChannelResult(channel="console", delivered=True, detail="ok"),
                ChannelResult(channel="snapshot", delivered=True, detail="ok"),
                ChannelResult(channel="external", delivered=False, detail="stub"),
            ],
        )
        snapshot = {
            "highest_incident": "LOCKDOWN",
            "overall_status": "LOCKDOWN",
            "triage_top": "Resolve LOCKDOWN",
        }
        rid = store.store(receipt, snapshot)
        assert rid.startswith("RX-")

        latest = store.latest()
        assert latest["severity_tier"] == "critical"
        assert latest["highest_incident"] == "LOCKDOWN"
        assert latest["channels_attempted"] == 3
        assert latest["channels_delivered"] == 2
        assert len(latest["channel_results"]) == 3
        assert latest["triage_top"] == "Resolve LOCKDOWN"


# ===========================================================================
# C16-6: 금지 조항
# ===========================================================================
class TestC16Forbidden:
    def test_no_forbidden_strings(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            "chain_of_thought",
            "raw_prompt",
            "internal_reasoning",
            "debug_trace",
            "agent_analysis",
            "error_class",
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_db_dependency(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "sqlalchemy" not in content
        assert "asyncpg" not in content
        assert "database" not in content.lower().replace("# no external db", "")

    def test_no_state_mutation(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "app.state" not in content
