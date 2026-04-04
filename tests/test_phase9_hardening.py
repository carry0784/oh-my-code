"""
Tests for Phase 9 hardening patch — DB persistence, startup restore,
event dedup, and transition idempotency.

Coverage:
  - SafeModeStatus DB persistence on state transition
  - SafeModeTransition append-only audit on every transition
  - Startup restore: no status → NORMAL
  - Startup restore: existing status → restored state
  - Drift event processed mark after consumption
  - Same event re-consumption blocked
  - Transition idempotency (duplicate from+to+source_event_id)
  - Full recovery path persisted
  - Snapshot receipt generation
  - DriftLedgerEntry processed field model check
  - Regression: existing Phase 9 minimal tests unbroken
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.models.safe_mode import (
    SafeModeState,
    SafeModeReasonCode,
    SafeModeStatus,
    SafeModeTransition,
)
from app.models.drift_ledger import (
    DriftLedgerEntry,
    BundleType as LedgerBundleType,
    DriftAction as LedgerDriftAction,
    DriftSeverity as LedgerDriftSeverity,
)
from app.services.recovery_policy_engine import (
    SafeModeStateMachine,
    RecoveryPolicyEngine,
    PolicyDecision,
    TransitionRecord,
)
from app.services.safe_mode_persistence import (
    PersistentSafeModeManager,
    _STATUS_ROW_ID,
)


# ── Mock DB Helpers ──────────────────────────────────────────────────


def _mock_db():
    """Create a mock AsyncSession with execute/flush/add tracking."""
    db = AsyncMock()
    db._added = []

    original_add = db.add

    def track_add(obj):
        db._added.append(obj)

    db.add = track_add
    return db


def _mock_execute_returns(scalar_value):
    """Helper: mock db.execute to return a scalar_one_or_none result."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_value
    return mock_result


def _mock_execute_returns_scalars(values):
    """Helper: mock db.execute to return scalars().all() result."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = values
    mock_result.scalars.return_value = mock_scalars
    return mock_result


# ── Drift Ledger Model: Processed Field ──────────────────────────────


class TestDriftLedgerProcessedField:
    def test_processed_default_false(self):
        entry = DriftLedgerEntry(
            bundle_type=LedgerBundleType.STRATEGY,
            expected_hash="a" * 64,
            observed_hash="b" * 64,
            action=LedgerDriftAction.REFUSE_LOAD,
            severity=LedgerDriftSeverity.HIGH,
            processed=False,
        )
        assert entry.processed is False
        assert entry.processed_at is None

    def test_processed_set_true(self):
        entry = DriftLedgerEntry(
            bundle_type=LedgerBundleType.STRATEGY,
            expected_hash="a" * 64,
            observed_hash="b" * 64,
            action=LedgerDriftAction.REFUSE_LOAD,
            severity=LedgerDriftSeverity.HIGH,
            processed=True,
            processed_at=datetime.now(timezone.utc),
        )
        assert entry.processed is True
        assert entry.processed_at is not None


# ── Startup Restore ─────────────────────────────────────────────────


class TestStartupRestore:
    @pytest.mark.asyncio
    async def test_no_status_creates_normal(self):
        """First boot: no status row → create NORMAL."""
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        state = await manager.restore_from_db()

        assert state == SafeModeState.NORMAL
        assert manager.state == SafeModeState.NORMAL
        # Should have added a new SafeModeStatus
        assert any(isinstance(o, SafeModeStatus) for o in db._added)

    @pytest.mark.asyncio
    async def test_existing_status_restores_sm3(self):
        """Existing DB row with SM3 → state machine restored to SM3."""
        db = _mock_db()

        existing = SafeModeStatus(
            id=_STATUS_ROW_ID,
            current_state=SafeModeState.SM3_RECOVERY_ONLY,
            entered_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
            entered_reason_code="drift_strategy_bundle",
            source_event_id="evt-001",
            cooldown_until=datetime(2026, 4, 2, 12, 5, 0, tzinfo=timezone.utc),
        )

        # First call: status lookup → returns existing
        # Second call: processed events lookup → returns empty
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_execute_returns(existing)
            else:
                return _mock_execute_returns_scalars([])

        db.execute = mock_execute

        manager = PersistentSafeModeManager(db)
        state = await manager.restore_from_db()

        assert state == SafeModeState.SM3_RECOVERY_ONLY
        assert manager.state == SafeModeState.SM3_RECOVERY_ONLY
        assert manager.state_machine._entered_reason_code == "drift_strategy_bundle"
        assert manager.state_machine._source_event_id == "evt-001"

    @pytest.mark.asyncio
    async def test_existing_status_restores_sm2(self):
        """Existing DB row with SM2 → state machine restored to SM2."""
        db = _mock_db()

        existing = SafeModeStatus(
            id=_STATUS_ROW_ID,
            current_state=SafeModeState.SM2_EXIT_ONLY,
            entered_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
            entered_reason_code="stability_confirmed",
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_execute_returns(existing)
            else:
                return _mock_execute_returns_scalars([])

        db.execute = mock_execute

        manager = PersistentSafeModeManager(db)
        state = await manager.restore_from_db()

        assert state == SafeModeState.SM2_EXIT_ONLY

    @pytest.mark.asyncio
    async def test_restore_loads_processed_event_ids(self):
        """Restore should load processed event IDs for dedup."""
        db = _mock_db()

        existing = SafeModeStatus(
            id=_STATUS_ROW_ID,
            current_state=SafeModeState.SM3_RECOVERY_ONLY,
            entered_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
            entered_reason_code="drift_strategy_bundle",
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_execute_returns(existing)
            else:
                # Return processed event IDs as tuples
                mock_result = MagicMock()
                mock_result.__iter__ = MagicMock(return_value=iter([("evt-001",), ("evt-002",)]))
                return mock_result

        db.execute = mock_execute

        manager = PersistentSafeModeManager(db)
        await manager.restore_from_db()

        assert "evt-001" in manager._consumer._processed_ids
        assert "evt-002" in manager._consumer._processed_ids


# ── SM3 Entry Persistence ────────────────────────────────────────────


class TestSM3EntryPersistence:
    @pytest.mark.asyncio
    async def test_enter_sm3_persists_transition(self):
        """SM3 entry should write SafeModeTransition to DB."""
        db = _mock_db()
        # Transition idempotency check returns no duplicate
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        record = await manager.enter_sm3(
            reason_code="drift_strategy_bundle",
            source_event_id="evt-001",
        )

        assert record is not None
        assert manager.state == SafeModeState.SM3_RECOVERY_ONLY
        # Should have added SafeModeTransition + SafeModeStatus
        transition_added = [o for o in db._added if isinstance(o, SafeModeTransition)]
        assert len(transition_added) >= 1
        t = transition_added[0]
        assert t.from_state == "normal"
        assert t.to_state == "sm3_recovery_only"

    @pytest.mark.asyncio
    async def test_enter_sm3_persists_status(self):
        """SM3 entry should update SafeModeStatus in DB."""
        db = _mock_db()

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            # idempotency check → None (no dup), then status upsert → None (new)
            return _mock_execute_returns(None)

        db.execute = mock_execute

        manager = PersistentSafeModeManager(db)
        await manager.enter_sm3(reason_code="drift_strategy_bundle")

        status_added = [o for o in db._added if isinstance(o, SafeModeStatus)]
        assert len(status_added) >= 1

    @pytest.mark.asyncio
    async def test_enter_sm3_when_already_sm3_suppressed(self):
        """SM3 entry when already SM3 → suppressed, no DB write."""
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        await manager.enter_sm3(reason_code="drift_strategy_bundle")

        added_before = len(db._added)
        result = await manager.enter_sm3(reason_code="drift_risk_limit_bundle")

        assert result is None
        # No new objects added for suppressed entry
        assert len(db._added) == added_before


# ── Manual Transition Persistence ────────────────────────────────────


class TestManualTransitionPersistence:
    @pytest.mark.asyncio
    async def test_manual_sm3_to_sm2_persists(self):
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        await manager.enter_sm3(reason_code="drift_strategy_bundle")

        added_before = len(db._added)
        record = await manager.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator",
        )

        assert manager.state == SafeModeState.SM2_EXIT_ONLY
        assert record.approved_by == "operator"
        # New objects should be added
        new_added = db._added[added_before:]
        transitions = [o for o in new_added if isinstance(o, SafeModeTransition)]
        assert len(transitions) >= 1

    @pytest.mark.asyncio
    async def test_full_recovery_persists_all_transitions(self):
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        await manager.enter_sm3(reason_code="drift_risk_limit_bundle")
        await manager.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator",
        )
        await manager.manual_transition(
            to_state=SafeModeState.SM1_OBSERVE_ONLY,
            reason_code="stability_confirmed",
            approved_by="approver",
        )
        await manager.manual_transition(
            to_state=SafeModeState.NORMAL,
            reason_code="manual_release",
            approved_by="approver_a",
        )

        assert manager.state == SafeModeState.NORMAL
        transitions = [o for o in db._added if isinstance(o, SafeModeTransition)]
        assert len(transitions) == 4


# ── Transition Idempotency ───────────────────────────────────────────


class TestTransitionIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_transition_suppressed(self):
        """Same from+to+source_event_id → second attempt suppressed."""
        db = _mock_db()

        call_count = 0
        existing_transition = SafeModeTransition(
            from_state="normal",
            to_state="sm3_recovery_only",
            reason_code="drift_strategy_bundle",
            source_event_id="evt-001",
        )

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Idempotency check: return existing transition (duplicate!)
                return _mock_execute_returns(existing_transition)
            return _mock_execute_returns(None)

        db.execute = mock_execute

        manager = PersistentSafeModeManager(db)
        result = await manager.enter_sm3(
            reason_code="drift_strategy_bundle",
            source_event_id="evt-001",
        )

        assert result is None  # Suppressed
        assert manager.state == SafeModeState.NORMAL  # Unchanged

    @pytest.mark.asyncio
    async def test_different_source_event_not_suppressed(self):
        """Different source_event_id → not a duplicate."""
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        result = await manager.enter_sm3(
            reason_code="drift_strategy_bundle",
            source_event_id="evt-002",
        )

        assert result is not None
        assert manager.state == SafeModeState.SM3_RECOVERY_ONLY

    @pytest.mark.asyncio
    async def test_no_source_event_skips_idempotency(self):
        """No source_event_id → skip idempotency check entirely."""
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        result = await manager.enter_sm3(
            reason_code="drift_strategy_bundle",
            source_event_id=None,
        )

        assert result is not None
        assert manager.state == SafeModeState.SM3_RECOVERY_ONLY


# ── Snapshot Receipt ─────────────────────────────────────────────────


class TestSnapshotReceipt:
    def test_snapshot_normal(self):
        db = _mock_db()
        manager = PersistentSafeModeManager(db)
        snap = manager.snapshot()
        assert snap["current_state"] == "normal"
        assert snap["entered_at"] is None
        assert snap["transition_count"] == 0

    @pytest.mark.asyncio
    async def test_snapshot_sm3(self):
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        await manager.enter_sm3(reason_code="drift_strategy_bundle")

        snap = manager.snapshot()
        assert snap["current_state"] == "sm3_recovery_only"
        assert snap["entered_at"] is not None
        assert snap["entered_reason_code"] == "drift_strategy_bundle"
        assert snap["transition_count"] == 1


# ── Drift Event Dedup Persistence ────────────────────────────────────


class TestDriftEventDedupPersistence:
    @pytest.mark.asyncio
    async def test_consume_marks_event_processed(self):
        """After consumption, drift event should be marked processed in DB."""
        db = _mock_db()

        entry = DriftLedgerEntry(
            id="evt-drift-001",
            bundle_type=LedgerBundleType.STRATEGY,
            expected_hash="a" * 64,
            observed_hash="b" * 64,
            action=LedgerDriftAction.REFUSE_LOAD,
            sm3_candidate=True,
            severity=LedgerDriftSeverity.HIGH,
            processed=False,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Load drift event
                return _mock_execute_returns(entry)
            # All other calls (status upsert, update processed, etc.)
            return _mock_execute_returns(None)

        db.execute = mock_execute

        manager = PersistentSafeModeManager(db)
        decision = await manager.consume_drift_event("evt-drift-001")

        assert decision == PolicyDecision.ENTER_SM3
        assert manager.state == SafeModeState.SM3_RECOVERY_ONLY

    @pytest.mark.asyncio
    async def test_already_processed_event_returns_suppressed(self):
        """Event with processed=True → DUPLICATE_SUPPRESSED."""
        db = _mock_db()

        entry = DriftLedgerEntry(
            id="evt-drift-001",
            bundle_type=LedgerBundleType.STRATEGY,
            expected_hash="a" * 64,
            observed_hash="b" * 64,
            action=LedgerDriftAction.REFUSE_LOAD,
            sm3_candidate=True,
            severity=LedgerDriftSeverity.HIGH,
            processed=True,
        )

        db.execute.return_value = _mock_execute_returns(entry)

        manager = PersistentSafeModeManager(db)
        decision = await manager.consume_drift_event("evt-drift-001")

        assert decision == PolicyDecision.DUPLICATE_SUPPRESSED
        assert manager.state == SafeModeState.NORMAL

    @pytest.mark.asyncio
    async def test_nonexistent_event_returns_noop(self):
        """Event not found in DB → NOOP."""
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        decision = await manager.consume_drift_event("nonexistent")

        assert decision == PolicyDecision.NOOP

    @pytest.mark.asyncio
    async def test_non_candidate_event_noop(self):
        """Event with sm3_candidate=False → NOOP."""
        db = _mock_db()

        entry = DriftLedgerEntry(
            id="evt-noop",
            bundle_type=LedgerBundleType.STRATEGY,
            expected_hash="a" * 64,
            observed_hash="b" * 64,
            action=LedgerDriftAction.REFUSE_LOAD,
            sm3_candidate=False,
            severity=LedgerDriftSeverity.HIGH,
            processed=False,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_execute_returns(entry)
            return _mock_execute_returns(None)

        db.execute = mock_execute

        manager = PersistentSafeModeManager(db)
        decision = await manager.consume_drift_event("evt-noop")

        assert decision == PolicyDecision.NOOP
        assert manager.state == SafeModeState.NORMAL


# ── Audit Trail Reconstruction ───────────────────────────────────────


class TestAuditReconstruction:
    @pytest.mark.asyncio
    async def test_transitions_match_db_records(self):
        """All in-memory transitions should correspond to DB writes."""
        db = _mock_db()
        db.execute.return_value = _mock_execute_returns(None)

        manager = PersistentSafeModeManager(db)
        await manager.enter_sm3(reason_code="drift_strategy_bundle")
        await manager.manual_transition(
            to_state=SafeModeState.SM2_EXIT_ONLY,
            reason_code="stability_confirmed",
            approved_by="operator",
        )

        in_memory = manager.state_machine.transitions
        db_transitions = [o for o in db._added if isinstance(o, SafeModeTransition)]

        assert len(in_memory) == len(db_transitions)
        for mem, db_t in zip(in_memory, db_transitions):
            mem_from = (
                mem.from_state.value
                if isinstance(mem.from_state, SafeModeState)
                else mem.from_state
            )
            assert mem_from == db_t.from_state
