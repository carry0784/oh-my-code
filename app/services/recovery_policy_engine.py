"""
Recovery Policy Engine (Phase 9 minimal) — interprets drift events
and drives Safe Mode state transitions.

Components:
  1. RecoveryPolicyEngine: drift event → policy decision
  2. SafeModeStateMachine: manages state transitions with rules
  3. DriftEventConsumer: idempotent consumer of drift ledger entries

Scope constraints (this batch):
  - Auto entry: SM3 only
  - Auto downward transition: FORBIDDEN
  - Release: manual approval required at each step
  - No runbook executor, no immune system, no auto-fix scoring
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.services.runtime_bundle import BundleType, DriftSeverity
from app.services.runtime_verifier import DriftAction, DriftEvent
from app.models.safe_mode import SafeModeState, SafeModeReasonCode

logger = logging.getLogger(__name__)


# ── Policy Decision ──────────────────────────────────────────────────


class PolicyDecision(str, Enum):
    ENTER_SM3 = "enter_sm3"
    NOOP = "noop"
    DUPLICATE_SUPPRESSED = "duplicate_suppressed"
    ESCALATE_REVIEW = "escalate_review"


# ── Reason code mapping from bundle type ─────────────────────────────

BUNDLE_TO_REASON: dict[BundleType, SafeModeReasonCode] = {
    BundleType.STRATEGY: SafeModeReasonCode.DRIFT_STRATEGY_BUNDLE,
    BundleType.FEATURE_PACK: SafeModeReasonCode.DRIFT_FEATURE_PACK_BUNDLE,
    BundleType.BROKER_POLICY: SafeModeReasonCode.DRIFT_BROKER_POLICY_BUNDLE,
    BundleType.RISK_LIMIT: SafeModeReasonCode.DRIFT_RISK_LIMIT_BUNDLE,
}


# ── Fingerprint for dedup ────────────────────────────────────────────


def _event_fingerprint(event: DriftEvent) -> str:
    """Unique fingerprint for dedup: bundle_type + expected + observed + action."""
    return f"{event.bundle_type.value}:{event.expected_hash}:{event.observed_hash}:{event.action.value}"


# ── Recovery Policy Engine ───────────────────────────────────────────


class RecoveryPolicyEngine:
    """Interprets drift events and produces policy decisions.

    Rules (minimal batch):
      - sm3_candidate=True AND action in {REFUSE_LOAD, RUNTIME_DRIFT_DETECTED}
        → ENTER_SM3
      - Same fingerprint within cooldown → DUPLICATE_SUPPRESSED
      - sm3_candidate=False → NOOP
      - action not in qualifying set → NOOP
    """

    QUALIFYING_ACTIONS: frozenset[DriftAction] = frozenset(
        {
            DriftAction.REFUSE_LOAD,
            DriftAction.RUNTIME_DRIFT_DETECTED,
        }
    )

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._seen_fingerprints: dict[str, datetime] = {}
        self._suppression_count: int = 0

    def evaluate(self, event: DriftEvent) -> PolicyDecision:
        """Evaluate a drift event and return a policy decision."""

        # Non-candidate events are always NOOP
        if not event.sm3_candidate:
            return PolicyDecision.NOOP

        # Non-qualifying actions are NOOP
        if event.action not in self.QUALIFYING_ACTIONS:
            return PolicyDecision.NOOP

        # Duplicate check
        fp = _event_fingerprint(event)
        now = datetime.now(timezone.utc)
        last_seen = self._seen_fingerprints.get(fp)
        if last_seen is not None:
            elapsed = (now - last_seen).total_seconds()
            if elapsed < self._cooldown_seconds:
                self._suppression_count += 1
                logger.info(
                    "Duplicate drift suppressed: fp=%s elapsed=%.0fs cooldown=%ds",
                    fp[:40],
                    elapsed,
                    self._cooldown_seconds,
                )
                return PolicyDecision.DUPLICATE_SUPPRESSED

        # Record fingerprint
        self._seen_fingerprints[fp] = now
        return PolicyDecision.ENTER_SM3

    @property
    def suppression_count(self) -> int:
        return self._suppression_count

    def reset(self) -> None:
        """Reset state (testing only)."""
        self._seen_fingerprints.clear()
        self._suppression_count = 0


# ── Transition record ────────────────────────────────────────────────


@dataclass
class TransitionRecord:
    """In-memory audit record for a state transition."""

    id: str = field(default_factory=lambda: str(uuid4()))
    from_state: SafeModeState = SafeModeState.NORMAL
    to_state: SafeModeState = SafeModeState.NORMAL
    reason_code: str = ""
    source_event_id: str | None = None
    approved_by: str | None = None
    detail: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Safe Mode State Machine ─────────────────────────────────────────

# Allowed automatic transitions (no approval needed)
_AUTO_TRANSITIONS: set[tuple[SafeModeState, SafeModeState]] = {
    (SafeModeState.NORMAL, SafeModeState.SM3_RECOVERY_ONLY),
}

# Allowed manual transitions (approval required)
_MANUAL_TRANSITIONS: set[tuple[SafeModeState, SafeModeState]] = {
    (SafeModeState.SM3_RECOVERY_ONLY, SafeModeState.SM2_EXIT_ONLY),
    (SafeModeState.SM2_EXIT_ONLY, SafeModeState.SM1_OBSERVE_ONLY),
    (SafeModeState.SM1_OBSERVE_ONLY, SafeModeState.NORMAL),
    # Direct escalation paths (manual only)
    (SafeModeState.NORMAL, SafeModeState.SM2_EXIT_ONLY),
    (SafeModeState.NORMAL, SafeModeState.SM1_OBSERVE_ONLY),
    (SafeModeState.SM3_RECOVERY_ONLY, SafeModeState.SM1_OBSERVE_ONLY),
}


class SafeModeError(Exception):
    """Raised when a state transition is invalid."""

    pass


class SafeModeStateMachine:
    """Manages Safe Mode state with enforced transition rules.

    Invariants:
      - Auto transitions: only NORMAL → SM3
      - Manual transitions: require approved_by
      - No auto downward/release transitions
      - All transitions produce audit records
    """

    def __init__(self) -> None:
        self._state = SafeModeState.NORMAL
        self._entered_at: datetime | None = None
        self._entered_reason_code: str | None = None
        self._source_event_id: str | None = None
        self._cooldown_until: datetime | None = None
        self._transitions: list[TransitionRecord] = []

    @property
    def state(self) -> SafeModeState:
        return self._state

    @property
    def entered_at(self) -> datetime | None:
        return self._entered_at

    @property
    def entered_reason_code(self) -> str | None:
        return self._entered_reason_code

    @property
    def source_event_id(self) -> str | None:
        return self._source_event_id

    @property
    def cooldown_until(self) -> datetime | None:
        return self._cooldown_until

    @property
    def transitions(self) -> list[TransitionRecord]:
        return list(self._transitions)

    @property
    def is_normal(self) -> bool:
        return self._state == SafeModeState.NORMAL

    # ── Auto entry (SM3 only) ────────────────────────────────────────

    def enter_sm3(
        self,
        reason_code: str,
        source_event_id: str | None = None,
        detail: str | None = None,
        cooldown_seconds: int = 300,
    ) -> TransitionRecord | None:
        """Automatically enter SM3_RECOVERY_ONLY.

        Returns None if already in SM3 or more restrictive state (suppressed).
        Raises SafeModeError if transition is invalid.
        """
        target = SafeModeState.SM3_RECOVERY_ONLY

        # Already in SM3 or more restrictive — suppress
        if self._state in (
            SafeModeState.SM3_RECOVERY_ONLY,
            SafeModeState.SM2_EXIT_ONLY,
            SafeModeState.SM1_OBSERVE_ONLY,
        ):
            logger.info(
                "SM3 entry suppressed: already in %s",
                self._state.value,
            )
            return None

        transition = (self._state, target)
        if transition not in _AUTO_TRANSITIONS:
            raise SafeModeError(f"Auto transition {self._state.value} → {target.value} not allowed")

        return self._apply_transition(
            to_state=target,
            reason_code=reason_code,
            source_event_id=source_event_id,
            detail=detail,
            approved_by=None,
            cooldown_seconds=cooldown_seconds,
        )

    # ── Manual transitions ───────────────────────────────────────────

    def manual_transition(
        self,
        to_state: SafeModeState,
        reason_code: str,
        approved_by: str,
        detail: str | None = None,
    ) -> TransitionRecord:
        """Perform a manual (approval-required) state transition.

        Raises SafeModeError if transition is invalid or approved_by is missing.
        """
        if not approved_by:
            raise SafeModeError("Manual transition requires approved_by")

        transition = (self._state, to_state)
        if transition not in _MANUAL_TRANSITIONS:
            raise SafeModeError(
                f"Manual transition {self._state.value} → {to_state.value} not allowed"
            )

        return self._apply_transition(
            to_state=to_state,
            reason_code=reason_code,
            source_event_id=None,
            detail=detail,
            approved_by=approved_by,
            cooldown_seconds=0,
        )

    # ── Internal ─────────────────────────────────────────────────────

    def _apply_transition(
        self,
        to_state: SafeModeState,
        reason_code: str,
        source_event_id: str | None,
        detail: str | None,
        approved_by: str | None,
        cooldown_seconds: int,
    ) -> TransitionRecord:
        now = datetime.now(timezone.utc)
        record = TransitionRecord(
            from_state=self._state,
            to_state=to_state,
            reason_code=reason_code,
            source_event_id=source_event_id,
            approved_by=approved_by,
            detail=detail,
            created_at=now,
        )
        self._transitions.append(record)

        prev = self._state
        self._state = to_state
        self._entered_at = now
        self._entered_reason_code = reason_code
        self._source_event_id = source_event_id

        if cooldown_seconds > 0:
            from datetime import timedelta

            self._cooldown_until = now + timedelta(seconds=cooldown_seconds)
        else:
            self._cooldown_until = None

        if to_state == SafeModeState.NORMAL:
            self._entered_at = None
            self._entered_reason_code = None
            self._source_event_id = None
            self._cooldown_until = None

        logger.warning(
            "SAFE MODE TRANSITION: %s → %s reason=%s approved_by=%s",
            prev.value,
            to_state.value,
            reason_code,
            approved_by,
        )
        return record


# ── Drift Event Consumer ─────────────────────────────────────────────


class DriftEventConsumer:
    """Idempotent consumer that connects drift events to Safe Mode transitions.

    Consumes DriftEvent objects, passes them through RecoveryPolicyEngine,
    and drives SafeModeStateMachine transitions when warranted.

    Idempotency:
      - Tracks processed event IDs
      - Same event ID is never processed twice
      - Duplicate fingerprints are suppressed by the policy engine
    """

    def __init__(
        self,
        policy_engine: RecoveryPolicyEngine,
        state_machine: SafeModeStateMachine,
    ) -> None:
        self._policy = policy_engine
        self._sm = state_machine
        self._processed_ids: set[str] = set()

    def consume(self, event: DriftEvent) -> PolicyDecision:
        """Process a single drift event. Idempotent by event ID.

        Returns the policy decision taken.
        """
        # Idempotency guard
        if event.id in self._processed_ids:
            logger.debug("Event already processed: %s", event.id)
            return PolicyDecision.DUPLICATE_SUPPRESSED

        self._processed_ids.add(event.id)

        decision = self._policy.evaluate(event)

        if decision == PolicyDecision.ENTER_SM3:
            reason = BUNDLE_TO_REASON.get(
                event.bundle_type,
                SafeModeReasonCode.DRIFT_STRATEGY_BUNDLE,
            )
            result = self._sm.enter_sm3(
                reason_code=reason.value,
                source_event_id=event.id,
                detail=f"severity={event.severity.value} action={event.action.value}",
            )
            if result is None:
                # Already in SM3+ — treat as suppressed
                decision = PolicyDecision.DUPLICATE_SUPPRESSED

        return decision

    def consume_batch(self, events: list[DriftEvent]) -> list[PolicyDecision]:
        """Process multiple events in order."""
        return [self.consume(e) for e in events]

    @property
    def processed_count(self) -> int:
        return len(self._processed_ids)

    def reset(self) -> None:
        """Reset state (testing only)."""
        self._processed_ids.clear()
