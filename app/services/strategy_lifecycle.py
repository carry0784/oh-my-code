"""
StrategyLifecycle — CR-044 Phase 7
State machine for strategy lifecycle management.

States: CANDIDATE → VALIDATED → PAPER_TRADING → PROMOTED → RETIRED
        PROMOTED can be DEMOTED → PAPER_TRADING (re-evaluation)
        Any state can transition to RETIRED (terminal)

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


class StrategyState(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PAPER_TRADING = "paper_trading"
    PROMOTED = "promoted"
    DEMOTED = "demoted"
    RETIRED = "retired"


ALLOWED_TRANSITIONS: dict[StrategyState, list[StrategyState]] = {
    StrategyState.CANDIDATE: [StrategyState.VALIDATED, StrategyState.RETIRED],
    StrategyState.VALIDATED: [StrategyState.PAPER_TRADING, StrategyState.RETIRED],
    StrategyState.PAPER_TRADING: [
        StrategyState.PROMOTED,
        StrategyState.DEMOTED,
        StrategyState.RETIRED,
    ],
    StrategyState.PROMOTED: [StrategyState.DEMOTED, StrategyState.RETIRED],
    StrategyState.DEMOTED: [StrategyState.PAPER_TRADING, StrategyState.RETIRED],
    StrategyState.RETIRED: [],
}


@dataclass
class LifecycleRecord:
    genome_id: str = ""
    current_state: StrategyState = StrategyState.CANDIDATE
    state_history: list[tuple[str, str, str]] = field(default_factory=list)
    promotion_count: int = 0
    demotion_count: int = 0


@dataclass
class TransitionRequest:
    genome_id: str = ""
    from_state: StrategyState = StrategyState.CANDIDATE
    to_state: StrategyState = StrategyState.VALIDATED
    reason: str = ""


class StrategyLifecycleManager:
    """Manages strategy state transitions."""

    def __init__(self):
        self.records: dict[str, LifecycleRecord] = {}

    def register(self, genome_id: str) -> LifecycleRecord:
        record = LifecycleRecord(genome_id=genome_id)
        self.records[genome_id] = record
        return record

    def request_transition(self, request: TransitionRequest) -> bool:
        record = self.records.get(request.genome_id)
        if not record:
            logger.warning("lifecycle_unknown_genome", genome_id=request.genome_id)
            return False

        if record.current_state != request.from_state:
            logger.warning(
                "lifecycle_state_mismatch",
                genome_id=request.genome_id,
                expected=request.from_state.value,
                actual=record.current_state.value,
            )
            return False

        allowed = ALLOWED_TRANSITIONS.get(request.from_state, [])
        if request.to_state not in allowed:
            logger.warning(
                "lifecycle_invalid_transition",
                genome_id=request.genome_id,
                from_state=request.from_state.value,
                to_state=request.to_state.value,
            )
            return False

        # Execute transition
        now = datetime.now(timezone.utc).isoformat()
        record.state_history.append((now, request.from_state.value, request.to_state.value))
        record.current_state = request.to_state

        if request.to_state == StrategyState.PROMOTED:
            record.promotion_count += 1
        elif request.to_state == StrategyState.DEMOTED:
            record.demotion_count += 1

        logger.info(
            "lifecycle_transition",
            genome_id=request.genome_id,
            from_state=request.from_state.value,
            to_state=request.to_state.value,
            reason=request.reason,
        )
        return True

    def get_state(self, genome_id: str) -> LifecycleRecord | None:
        return self.records.get(genome_id)

    def get_by_state(self, state: StrategyState) -> list[LifecycleRecord]:
        return [r for r in self.records.values() if r.current_state == state]

    def auto_retire(self, genome_ids: list[str], reason: str = "auto_retire") -> list[str]:
        retired = []
        for gid in genome_ids:
            record = self.records.get(gid)
            if record and record.current_state != StrategyState.RETIRED:
                allowed = ALLOWED_TRANSITIONS.get(record.current_state, [])
                if StrategyState.RETIRED in allowed:
                    req = TransitionRequest(
                        genome_id=gid,
                        from_state=record.current_state,
                        to_state=StrategyState.RETIRED,
                        reason=reason,
                    )
                    if self.request_transition(req):
                        retired.append(gid)
        return retired
