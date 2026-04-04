"""
Card C-18: Receipt File Backend — Append-only JSONL persistence.

Purpose:
  Persist notification receipts to a local JSONL file so receipt history
  survives process restart. One JSON object per line, append-only.

Design:
  - Append-only: never modifies or deletes existing lines
  - Fail-closed: write errors are silently skipped (receipt still in memory)
  - Human-readable: standard JSON, one line per receipt
  - Load-on-init: reads existing file to populate ReceiptStore on startup
  - No external dependencies beyond stdlib
  - No hidden reasoning, no debug traces
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class ReceiptFileBackend:
    """
    Append-only JSONL file backend for notification receipts.

    Usage:
        backend = ReceiptFileBackend("/path/to/receipts.jsonl")
        backend.append(receipt_dict)
        history = backend.load_all()
    """

    def __init__(self, file_path: str | Path) -> None:
        self._path = Path(file_path)

    @property
    def file_path(self) -> Path:
        return self._path

    def append(self, receipt: dict[str, Any]) -> bool:
        """
        Append a single receipt as one JSON line.

        Returns True on success, False on failure.
        Fail-closed: never raises.
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(receipt, ensure_ascii=False, default=str)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return True
        except Exception:
            return False

    def load_all(self) -> list[dict[str, Any]]:
        """
        Load all receipts from file.

        Returns list of dicts (newest last). Skips malformed lines.
        Fail-closed: returns empty list on any file error.
        """
        if not self._path.exists():
            return []

        try:
            entries = []
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # skip malformed lines
            return entries
        except Exception:
            return []

    def count(self) -> int:
        """Count receipts in file. Fail-closed: returns 0 on error."""
        try:
            if not self._path.exists():
                return 0
            with open(self._path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def exists(self) -> bool:
        """Check if the receipt file exists."""
        return self._path.exists()
