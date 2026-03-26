"""
Card C-18: Receipt Persistence Backend (File-first) — Tests

검수 범위:
  C18-1: ReceiptFileBackend CRUD
  C18-2: JSONL format 검증
  C18-3: Fail-closed 동작
  C18-4: ReceiptStore + file backend 통합
  C18-5: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import json
import tempfile
from pathlib import Path

import pytest

from app.core.notification_receipt_file_backend import ReceiptFileBackend
from app.core.notification_receipt_store import ReceiptStore, StoredReceipt
from app.core.notification_sender import NotificationReceipt, ChannelResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_PATH = PROJECT_ROOT / "app" / "core" / "notification_receipt_file_backend.py"
STORE_PATH = PROJECT_ROOT / "app" / "core" / "notification_receipt_store.py"


# ===========================================================================
# C18-1: ReceiptFileBackend CRUD
# ===========================================================================
class TestC18BackendCRUD:

    def test_append_returns_true(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "test.jsonl")
        assert backend.append({"id": "RX-001"}) is True

    def test_file_created_on_append(self, tmp_path):
        path = tmp_path / "test.jsonl"
        backend = ReceiptFileBackend(path)
        backend.append({"id": "RX-001"})
        assert path.exists()

    def test_load_all_returns_appended(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "test.jsonl")
        backend.append({"id": "RX-001", "severity": "high"})
        backend.append({"id": "RX-002", "severity": "low"})
        entries = backend.load_all()
        assert len(entries) == 2
        assert entries[0]["id"] == "RX-001"
        assert entries[1]["id"] == "RX-002"

    def test_count_matches_appended(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "test.jsonl")
        assert backend.count() == 0
        backend.append({"id": "1"})
        backend.append({"id": "2"})
        backend.append({"id": "3"})
        assert backend.count() == 3

    def test_exists_false_before_write(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "nonexistent.jsonl")
        assert backend.exists() is False

    def test_exists_true_after_write(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "test.jsonl")
        backend.append({"id": "1"})
        assert backend.exists() is True

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "receipts.jsonl"
        backend = ReceiptFileBackend(path)
        backend.append({"id": "1"})
        assert path.exists()


# ===========================================================================
# C18-2: JSONL format
# ===========================================================================
class TestC18JSONLFormat:

    def test_each_line_is_valid_json(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "test.jsonl")
        backend.append({"id": "RX-001"})
        backend.append({"id": "RX-002"})
        with open(tmp_path / "test.jsonl") as f:
            lines = f.readlines()
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert isinstance(parsed, dict)

    def test_one_object_per_line(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "test.jsonl")
        backend.append({"a": 1})
        backend.append({"b": 2})
        with open(tmp_path / "test.jsonl") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        assert len(lines) == 2

    def test_append_only_no_overwrite(self, tmp_path):
        path = tmp_path / "test.jsonl"
        backend = ReceiptFileBackend(path)
        backend.append({"id": "FIRST"})
        backend.append({"id": "SECOND"})
        entries = backend.load_all()
        assert entries[0]["id"] == "FIRST"
        assert entries[1]["id"] == "SECOND"


# ===========================================================================
# C18-3: Fail-closed
# ===========================================================================
class TestC18FailClosed:

    def test_append_to_readonly_returns_false(self, tmp_path):
        """쓰기 불가 경로에 쓰기 실패 시 False 반환."""
        import sys
        # Use a path that cannot be written on any OS
        if sys.platform == "win32":
            bad_path = "NUL:\\impossible\\path.jsonl"
        else:
            bad_path = "/proc/0/impossible/path.jsonl"
        backend = ReceiptFileBackend(bad_path)
        result = backend.append({"id": "1"})
        assert result is False

    def test_load_nonexistent_returns_empty(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "nope.jsonl")
        assert backend.load_all() == []

    def test_load_skips_malformed_lines(self, tmp_path):
        path = tmp_path / "test.jsonl"
        with open(path, "w") as f:
            f.write('{"id": "good"}\n')
            f.write('NOT JSON\n')
            f.write('{"id": "also_good"}\n')
        backend = ReceiptFileBackend(path)
        entries = backend.load_all()
        assert len(entries) == 2

    def test_count_nonexistent_returns_zero(self, tmp_path):
        backend = ReceiptFileBackend(tmp_path / "nope.jsonl")
        assert backend.count() == 0


# ===========================================================================
# C18-4: ReceiptStore + file backend 통합
# ===========================================================================
class TestC18StoreIntegration:

    def test_store_with_backend_persists(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        backend = ReceiptFileBackend(path)
        store = ReceiptStore(file_backend=backend)
        store.store({"severity_tier": "high"}, {"highest_incident": "LOCKDOWN"})
        assert backend.count() == 1

    def test_store_without_backend_still_works(self):
        """backend=None이면 기존 memory-only 동작."""
        store = ReceiptStore()
        rid = store.store({"severity_tier": "low"})
        assert rid.startswith("RX-")
        assert store.count() == 1

    def test_load_on_init_restores_history(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        backend = ReceiptFileBackend(path)

        # First store: write 3 receipts
        store1 = ReceiptStore(file_backend=backend)
        store1.store({"severity_tier": "low"}, {"highest_incident": "A"})
        store1.store({"severity_tier": "high"}, {"highest_incident": "B"})
        store1.store({"severity_tier": "critical"}, {"highest_incident": "C"})
        assert store1.count() == 3

        # Simulate restart: new store with same file
        store2 = ReceiptStore(file_backend=backend)
        assert store2.count() == 3
        latest = store2.latest()
        assert latest["highest_incident"] == "C"

    def test_store_with_c15_receipt(self, tmp_path):
        path = tmp_path / "receipts.jsonl"
        backend = ReceiptFileBackend(path)
        store = ReceiptStore(file_backend=backend)

        receipt = NotificationReceipt(
            attempted_at="2026-03-24T10:00:00Z",
            severity_tier="critical",
            channels_attempted=2,
            channels_delivered=1,
            results=[
                ChannelResult(channel="console", delivered=True, detail="ok"),
                ChannelResult(channel="external", delivered=False, detail="stub"),
            ],
        )
        rid = store.store(receipt, {"highest_incident": "LOCKDOWN"})
        assert rid.startswith("RX-")
        assert backend.count() == 1

        # Verify persisted content
        entries = backend.load_all()
        assert entries[0]["severity_tier"] == "critical"
        assert entries[0]["highest_incident"] == "LOCKDOWN"


# ===========================================================================
# C18-5: 금지 조항
# ===========================================================================
class TestC18Forbidden:

    def test_no_forbidden_strings_in_backend(self):
        content = BACKEND_PATH.read_text(encoding="utf-8")
        body = content.split('"""', 2)[-1] if '"""' in content else content
        forbidden = [
            'chain_of_thought', 'raw_prompt', 'internal_reasoning',
            'debug_trace', 'agent_analysis', 'error_class',
        ]
        for f in forbidden:
            assert f not in body, f"Forbidden string '{f}'"

    def test_no_db_dependency(self):
        content = BACKEND_PATH.read_text(encoding="utf-8")
        assert "sqlalchemy" not in content
        assert "asyncpg" not in content

    def test_no_external_libs(self):
        content = BACKEND_PATH.read_text(encoding="utf-8")
        assert "import requests" not in content
        assert "import httpx" not in content

    def test_store_file_backend_field_exists(self):
        content = STORE_PATH.read_text(encoding="utf-8")
        assert "file_backend" in content
