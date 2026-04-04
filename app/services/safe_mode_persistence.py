"""
Persistent Safe Mode Manager — DB-backed wrapper around SafeModeStateMachine.

Responsibilities:
  1. DB persistence: every transition writes SafeModeStatus + SafeModeTransition
  2. Startup restore: reconstruct state machine from DB on app start
  3. Drift event dedup: mark processed events in drift_ledger
  4. Transition idempotency: prevent duplicate from+to+source_event_id

This is the hardening layer that makes Phase 9 minimal restart-safe.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safe_mode import (
    SafeModeState,
    SafeModeStatus,
    SafeModeTransition,
)
from app.models.drift_ledger import DriftLedgerEntry
from app.services.recovery_policy_engine import (
    SafeModeStateMachine,
    SafeModeError,
    TransitionRecord,
    RecoveryPolicyEngine,
    DriftEventConsumer,
    PolicyDecision,
    BUNDLE_TO_REASON,
)
from app.services.runtime_verifier import DriftEvent

logger = logging.getLogger(__name__)

# Singleton status row ID (deterministic, single-row table)
_STATUS_ROW_ID = "safe-mode-singleton"


class PersistentSafeModeManager:
    """DB-backed Safe Mode manager.

    Wraps SafeModeStateMachine and ensures all state changes are
    persisted to PostgreSQL.  Provides startup restore and
    drift event dedup.
    """

    def __init__(
        self,
        db: AsyncSession,
        state_machine: SafeModeStateMachine | None = None,
        policy_engine: RecoveryPolicyEngine | None = None,
    ) -> None:
        self.db = db
        self._sm = state_machine or SafeModeStateMachine()
        self._policy = policy_engine or RecoveryPolicyEngine()
        self._consumer = DriftEventConsumer(self._policy, self._sm)

    @property
    def state(self) -> SafeModeState:
        return self._sm.state

    @property
    def state_machine(self) -> SafeModeStateMachine:
        return self._sm

    # ── Startup Restore ──────────────────────────────────────────────

    async def restore_from_db(self) -> SafeModeState:
        """Restore state machine from DB.  Called at app startup.

        If no status row exists, creates one with NORMAL state.
        If a row exists, restores the state machine to match.
        """
        result = await self.db.execute(
            select(SafeModeStatus).where(SafeModeStatus.id == _STATUS_ROW_ID)
        )
        status = result.scalar_one_or_none()

        if status is None:
            # First boot — create NORMAL row
            status = SafeModeStatus(
                id=_STATUS_ROW_ID,
                current_state=SafeModeState.NORMAL,
            )
            self.db.add(status)
            await self.db.flush()
            logger.info("Safe Mode: initialized to NORMAL (first boot)")
            return SafeModeState.NORMAL

        # Restore state machine to match DB
        db_state = status.current_state
        self._sm._state = db_state
        self._sm._entered_at = status.entered_at
        self._sm._entered_reason_code = status.entered_reason_code
        self._sm._source_event_id = status.source_event_id
        self._sm._cooldown_until = status.cooldown_until

        # Restore processed event IDs from drift_ledger
        processed_result = await self.db.execute(
            select(DriftLedgerEntry.id).where(DriftLedgerEntry.processed == True)  # noqa: E712
        )
        for (event_id,) in processed_result:
            self._consumer._processed_ids.add(event_id)

        logger.info(
            "Safe Mode: restored to %s (reason=%s, processed_events=%d)",
            db_state.value,
            status.entered_reason_code,
            len(self._consumer._processed_ids),
        )
        return db_state

    # ── Auto entry (SM3) with persistence ────────────────────────────

    async def enter_sm3(
        self,
        reason_code: str,
        source_event_id: str | None = None,
        detail: str | None = None,
        cooldown_seconds: int = 300,
    ) -> TransitionRecord | None:
        """Enter SM3 with DB persistence.  Returns None if suppressed."""

        # Transition idempotency check
        if source_event_id:
            is_dup = await self._is_duplicate_transition(
                SafeModeState.NORMAL.value,
                SafeModeState.SM3_RECOVERY_ONLY.value,
                source_event_id,
            )
            if is_dup:
                logger.info("Transition idempotency: duplicate SM3 entry for %s", source_event_id)
                return None

        record = self._sm.enter_sm3(
            reason_code=reason_code,
            source_event_id=source_event_id,
            detail=detail,
            cooldown_seconds=cooldown_seconds,
        )
        if record is None:
            return None

        await self._persist_transition(record)
        await self._update_status()
        return record

    # ── Manual transition with persistence ───────────────────────────

    async def manual_transition(
        self,
        to_state: SafeModeState,
        reason_code: str,
        approved_by: str,
        detail: str | None = None,
    ) -> TransitionRecord:
        """Manual transition with DB persistence."""

        record = self._sm.manual_transition(
            to_state=to_state,
            reason_code=reason_code,
            approved_by=approved_by,
            detail=detail,
        )
        await self._persist_transition(record)
        await self._update_status()
        return record

    # ── Drift event consumption with persistence ─────────────────────

    async def consume_drift_event(self, event_id: str) -> PolicyDecision:
        """Consume a drift event from DB by ID with full persistence.

        Reads the event from drift_ledger, processes it through
        the policy engine, and marks it as processed.
        """
        # Load event from DB
        result = await self.db.execute(
            select(DriftLedgerEntry).where(DriftLedgerEntry.id == event_id)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            logger.warning("Drift event not found: %s", event_id)
            return PolicyDecision.NOOP

        if entry.processed:
            logger.debug("Drift event already processed: %s", event_id)
            return PolicyDecision.DUPLICATE_SUPPRESSED

        # Convert DB entry to DriftEvent for the consumer
        from app.services.runtime_bundle import (
            BundleType as RBBundleType,
            DriftSeverity as RBSeverity,
        )
        from app.services.runtime_verifier import DriftAction as RVDriftAction

        drift_event = DriftEvent(
            bundle_type=RBBundleType(entry.bundle_type.value),
            expected_hash=entry.expected_hash,
            observed_hash=entry.observed_hash,
            action=RVDriftAction(entry.action.value),
            sm3_candidate=entry.sm3_candidate,
            severity=RBSeverity(entry.severity.value),
        )
        drift_event.id = entry.id

        decision = self._consumer.consume(drift_event)

        # If the consumer decided ENTER_SM3, persist the state change
        if decision == PolicyDecision.ENTER_SM3:
            await self._update_status()
            # Persist the transition that the consumer triggered
            transitions = self._sm.transitions
            if transitions:
                last = transitions[-1]
                await self._persist_transition(last)

        # Mark event as processed
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(DriftLedgerEntry)
            .where(DriftLedgerEntry.id == event_id)
            .values(processed=True, processed_at=now)
        )
        await self.db.flush()

        return decision

    async def consume_unprocessed_events(self) -> list[PolicyDecision]:
        """Consume all unprocessed drift events from DB."""
        result = await self.db.execute(
            select(DriftLedgerEntry)
            .where(DriftLedgerEntry.processed == False)  # noqa: E712
            .where(DriftLedgerEntry.sm3_candidate == True)  # noqa: E712
            .order_by(DriftLedgerEntry.detected_at)
        )
        entries = list(result.scalars().all())
        decisions = []
        for entry in entries:
            d = await self.consume_drift_event(entry.id)
            decisions.append(d)
        return decisions

    # ── Internal persistence helpers ─────────────────────────────────

    async def _persist_transition(self, record: TransitionRecord) -> None:
        """Write a transition record to DB."""
        transition = SafeModeTransition(
            id=record.id,
            from_state=record.from_state.value
            if isinstance(record.from_state, SafeModeState)
            else record.from_state,
            to_state=record.to_state.value
            if isinstance(record.to_state, SafeModeState)
            else record.to_state,
            reason_code=record.reason_code,
            source_event_id=record.source_event_id,
            approved_by=record.approved_by,
            detail=record.detail,
            created_at=record.created_at,
        )
        self.db.add(transition)
        await self.db.flush()

    async def _update_status(self) -> None:
        """Upsert the singleton SafeModeStatus row."""
        result = await self.db.execute(
            select(SafeModeStatus).where(SafeModeStatus.id == _STATUS_ROW_ID)
        )
        status = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        sm = self._sm

        if status is None:
            status = SafeModeStatus(
                id=_STATUS_ROW_ID,
                current_state=sm.state,
                entered_at=sm.entered_at,
                entered_reason_code=sm.entered_reason_code,
                source_event_id=sm.source_event_id,
                cooldown_until=sm.cooldown_until,
                updated_at=now,
            )
            self.db.add(status)
        else:
            status.previous_state = status.current_state
            status.current_state = sm.state
            status.entered_at = sm.entered_at
            status.entered_reason_code = sm.entered_reason_code
            status.source_event_id = sm.source_event_id
            status.cooldown_until = sm.cooldown_until
            status.updated_at = now

            if sm.state == SafeModeState.NORMAL:
                status.released_at = now
                status.release_reason = sm.entered_reason_code

        await self.db.flush()

    async def _is_duplicate_transition(
        self,
        from_state: str,
        to_state: str,
        source_event_id: str,
    ) -> bool:
        """Check if an identical transition already exists in DB."""
        result = await self.db.execute(
            select(SafeModeTransition)
            .where(SafeModeTransition.from_state == from_state)
            .where(SafeModeTransition.to_state == to_state)
            .where(SafeModeTransition.source_event_id == source_event_id)
        )
        return result.scalar_one_or_none() is not None

    # ── Status snapshot (for receipt/audit) ──────────────────────────

    def snapshot(self) -> dict:
        """Return current state as a JSON-serializable dict."""
        return {
            "current_state": self._sm.state.value,
            "entered_at": self._sm.entered_at.isoformat() if self._sm.entered_at else None,
            "entered_reason_code": self._sm.entered_reason_code,
            "source_event_id": self._sm.source_event_id,
            "cooldown_until": self._sm.cooldown_until.isoformat()
            if self._sm.cooldown_until
            else None,
            "transition_count": len(self._sm.transitions),
        }
