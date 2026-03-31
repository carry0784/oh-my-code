"""
SQLite Evidence Backend — K-Dexter AOS v4

Persistent evidence storage using stdlib sqlite3.
WAL mode for concurrent read/write performance.

Append-only: INSERT only, no REPLACE/UPDATE/UPSERT.
Duplicate bundle_id raises DuplicateEvidenceError.
DURABLE: evidence survives process restart.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional

from kdexter.audit.backends import EvidenceBackend
from kdexter.audit.evidence_store import DuplicateEvidenceError, EvidenceBundle


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS evidence_bundles (
    bundle_id   TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    trigger_    TEXT,
    actor       TEXT,
    action      TEXT,
    before_state TEXT,
    after_state  TEXT,
    artifacts   TEXT,
    cycle_id    TEXT
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cycle_id ON evidence_bundles(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_actor ON evidence_bundles(actor)",
    "CREATE INDEX IF NOT EXISTS idx_trigger ON evidence_bundles(trigger_)",
    # CR-027: Composite index for bounded recent queries — eliminates TEMP B-TREE sort.
    "CREATE INDEX IF NOT EXISTS idx_actor_created ON evidence_bundles(actor, created_at)",
]


class SQLiteBackend(EvidenceBackend):
    """SQLite-based persistent evidence storage."""

    def __init__(self, db_path: str = "evidence.db") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_CREATE_TABLE)
        for idx in _CREATE_INDEXES:
            self._conn.execute(idx)
        self._conn.commit()

    def store(self, bundle: EvidenceBundle) -> str:
        try:
            self._conn.execute(
                """INSERT INTO evidence_bundles
                   (bundle_id, created_at, trigger_, actor, action,
                    before_state, after_state, artifacts, cycle_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    bundle.bundle_id,
                    bundle.created_at.isoformat(),
                    bundle.trigger,
                    bundle.actor,
                    bundle.action,
                    _serialize(bundle.before_state),
                    _serialize(bundle.after_state),
                    json.dumps(bundle.artifacts),
                    bundle.cycle_id,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise DuplicateEvidenceError(
                f"Append-only violation: bundle_id={bundle.bundle_id} already exists. "
                f"Evidence records are immutable."
            )
        return bundle.bundle_id

    def get(self, bundle_id: str) -> Optional[EvidenceBundle]:
        row = self._conn.execute(
            "SELECT * FROM evidence_bundles WHERE bundle_id = ?",
            (bundle_id,),
        ).fetchone()
        return _row_to_bundle(row) if row else None

    def count(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM evidence_bundles"
        ).fetchone()[0]

    def count_for_cycle(self, cycle_id: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM evidence_bundles WHERE cycle_id = ?",
            (cycle_id,),
        ).fetchone()[0]

    def count_by_actor(self, actor: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM evidence_bundles WHERE actor = ?",
            (actor,),
        ).fetchone()[0]

    def list_by_trigger(self, trigger: str) -> list[EvidenceBundle]:
        rows = self._conn.execute(
            "SELECT * FROM evidence_bundles WHERE trigger_ LIKE ? ORDER BY created_at",
            (trigger + "%",),
        ).fetchall()
        return [_row_to_bundle(r) for r in rows]

    def list_by_actor(self, actor: str) -> list[EvidenceBundle]:
        rows = self._conn.execute(
            "SELECT * FROM evidence_bundles WHERE actor = ? ORDER BY created_at",
            (actor,),
        ).fetchall()
        return [_row_to_bundle(r) for r in rows]

    def list_by_actor_recent(self, actor: str, limit: int = 20) -> list[EvidenceBundle]:
        """List most recent bundles by actor, bounded by limit. CR-027."""
        rows = self._conn.execute(
            "SELECT * FROM evidence_bundles WHERE actor = ? ORDER BY created_at DESC LIMIT ?",
            (actor, limit),
        ).fetchall()
        return [_row_to_bundle(r) for r in reversed(rows)]

    def list_all(self) -> list[EvidenceBundle]:
        rows = self._conn.execute(
            "SELECT * FROM evidence_bundles ORDER BY created_at"
        ).fetchall()
        return [_row_to_bundle(r) for r in rows]

    def count_orphan_pre(self) -> int:
        """Count PRE-phase bundles not linked by POST/ERROR. CR-028.

        Uses JSON extraction on artifacts column. Bounded by actual PRE/POST
        population which is typically small relative to total evidence.
        """
        rows = self._conn.execute(
            "SELECT bundle_id, artifacts FROM evidence_bundles WHERE artifacts IS NOT NULL AND artifacts != '[]'"
        ).fetchall()
        pre_ids: set[str] = set()
        linked: set[str] = set()
        for bundle_id, artifacts_json in rows:
            try:
                artifacts = json.loads(artifacts_json) if artifacts_json else []
            except (json.JSONDecodeError, TypeError):
                continue
            for art in artifacts:
                if not isinstance(art, dict):
                    continue
                phase = art.get("phase", "")
                if phase == "PRE":
                    pre_ids.add(bundle_id)
                elif phase in ("POST", "ERROR"):
                    lid = art.get("pre_evidence_id", "")
                    if lid:
                        linked.add(lid)
        return len(pre_ids - linked)

    def clear(self) -> None:
        self._conn.execute("DELETE FROM evidence_bundles")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# ── helpers ──────────────────────────────────────────────────────────── #

def _serialize(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return json.dumps(str(value))


def _deserialize(text: Optional[str]):
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def _row_to_bundle(row: tuple) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=row[0],
        created_at=datetime.fromisoformat(row[1]),
        trigger=row[2],
        actor=row[3],
        action=row[4],
        before_state=_deserialize(row[5]),
        after_state=_deserialize(row[6]),
        artifacts=json.loads(row[7]) if row[7] else [],
        cycle_id=row[8],
    )
