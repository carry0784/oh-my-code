"""
I-04: Incident Playback Builder — 제44조 사고 타임라인 재구성

I-04는 incident replay engine이 아니라 incident review/재구성 계층이다.
Simulation / replay execution / failover test 실행 금지.

역참조: Operating Constitution v1.0 제44조
재구성 순서: 발생 → 탐지 → 자동조치 → 운영자조치 → 종료

금지: 실제 재실행, failover, recovery, promotion, state mutation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.preflight_schema import (
    IncidentPlaybackResult,
    PlaybackConfidence,
    PlaybackTimelineEntry,
)

logger = get_logger(__name__)

_REQUIRED_PHASES = {"발생", "탐지", "자동조치", "운영자조치", "종료"}


def build_incident_playback() -> IncidentPlaybackResult:
    """
    제44조: Incident Playback 타임라인 재구성.
    Review/재구성만 수행. 실행/failover/recovery 금지.
    """
    now = datetime.now(timezone.utc)
    timeline: list[PlaybackTimelineEntry] = []
    evidence_ids: list[str] = []
    receipt_ids: list[str] = []
    flow_events: list[str] = []
    check_refs: list[str] = []

    try:
        import app.main as main_module
        app_inst = main_module.app

        # Source 1: Receipt store → 발생 phase
        receipt_store = getattr(app_inst.state, "receipt_store", None)
        if receipt_store and receipt_store.count() > 0:
            for r in receipt_store.list_receipts(limit=20):
                rid = r.get("receipt_id", "")
                receipt_ids.append(rid)
                sev = r.get("severity_tier", "")
                phase = "발생" if sev in ("critical", "high") else "탐지"
                timeline.append(PlaybackTimelineEntry(
                    timestamp=r.get("stored_at", now.isoformat()),
                    phase=phase,
                    description=f"{sev}: {r.get('highest_incident', 'unknown')}",
                    source="receipt_store",
                    evidence_ref=rid,
                ))

        # Source 2: Flow log → 탐지/자동조치/종료 phases
        flow_log = getattr(app_inst.state, "flow_log", None)
        if flow_log and flow_log.count() > 0:
            for e in flow_log.list_entries(limit=20):
                log_id = e.get("log_id", "")
                flow_events.append(log_id)
                action = e.get("policy_action", "")
                if action in ("send", "escalate"):
                    phase = "자동조치"
                elif action == "resolve":
                    phase = "종료"
                elif e.get("routing_ok"):
                    phase = "탐지"
                else:
                    phase = "운영자조치"
                timeline.append(PlaybackTimelineEntry(
                    timestamp=e.get("executed_at", now.isoformat()),
                    phase=phase,
                    description=f"action={action}, channels={e.get('channels_delivered', 0)}",
                    source="flow_log",
                    evidence_ref=e.get("receipt_id"),
                ))

        # Source 3: Evidence store → check results
        # CR-027: Bounded query — only recent N bundles, not full 84K+ scan.
        gate = getattr(app_inst.state, "governance_gate", None)
        if gate and hasattr(gate, "evidence_store"):
            _store = gate.evidence_store
            for actor_prefix in ("i03_", "i04_"):
                _actor = f"{actor_prefix}daily_check"
                if hasattr(_store, "list_by_actor_recent"):
                    _check_bundles = _store.list_by_actor_recent(_actor, 20)
                else:
                    _check_bundles = _store.list_by_actor(_actor)[-20:]
                for b in _check_bundles:
                    bid = b.bundle_id if hasattr(b, "bundle_id") else str(uuid.uuid4())
                    evidence_ids.append(bid)
                    check_refs.append(f"check:{bid[:8]}")
                    timeline.append(PlaybackTimelineEntry(
                        timestamp=b.created_at.isoformat() if hasattr(b.created_at, "isoformat") else str(b.created_at),
                        phase="탐지",
                        description=f"check by {b.actor}" if hasattr(b, "actor") else "check",
                        source="check_runner",
                        evidence_ref=bid,
                    ))

    except Exception as e:
        logger.warning("incident_playback_build_failed", error=str(e))

    # Sort timeline by timestamp
    timeline.sort(key=lambda x: x.timestamp)

    # Detect timeline gaps (> 5 min between entries)
    gap_detected = False
    if len(timeline) >= 2:
        for i in range(1, len(timeline)):
            try:
                t1 = datetime.fromisoformat(timeline[i - 1].timestamp.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(timeline[i].timestamp.replace("Z", "+00:00"))
                if (t2 - t1).total_seconds() > 300:
                    gap_detected = True
                    break
            except Exception:
                pass

    # Compute missing phases
    observed_phases = {e.phase for e in timeline}
    missing = list(_REQUIRED_PHASES - observed_phases)

    # Compute confidence
    if not missing and not gap_detected and len(timeline) >= 3:
        confidence = PlaybackConfidence.HIGH
    elif len(missing) <= 2 and len(timeline) >= 1:
        confidence = PlaybackConfidence.MEDIUM
    else:
        confidence = PlaybackConfidence.LOW

    # Determine incident_id and time_range
    incident_id = receipt_ids[0] if receipt_ids else f"INC-{now.strftime('%Y%m%d%H%M%S')}"
    time_start = timeline[0].timestamp if timeline else now.isoformat()
    time_end = timeline[-1].timestamp if timeline else now.isoformat()

    summary_parts = [f"timeline={len(timeline)} entries"]
    if missing:
        summary_parts.append(f"missing phases: {', '.join(missing)}")
    if gap_detected:
        summary_parts.append("timeline gaps detected")
    summary = f"Incident playback: {', '.join(summary_parts)}, confidence={confidence.value}"

    # Store evidence
    evidence_id = _store_playback_evidence(incident_id, timeline, confidence, now)

    return IncidentPlaybackResult(
        incident_id=incident_id,
        time_range={"start": time_start, "end": time_end},
        trigger_source=receipt_ids[0] if receipt_ids else None,
        summary=summary,
        timeline=timeline,
        related_evidence_ids=list(dict.fromkeys(evidence_ids)),
        related_receipt_ids=list(dict.fromkeys(receipt_ids)),
        related_flow_events=list(dict.fromkeys(flow_events)),
        related_check_refs=list(dict.fromkeys(check_refs)),
        confidence=confidence,
        missing_observations=missing,
        timeline_gap_detected=gap_detected,
        rule_refs=["Art44"],
    )


def _store_playback_evidence(
    incident_id: str,
    timeline: list[PlaybackTimelineEntry],
    confidence: PlaybackConfidence,
    now: datetime,
) -> str:
    """Store playback result to evidence store. Append-only."""
    try:
        import app.main as main_module
        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is None or not hasattr(gate, "evidence_store"):
            return f"fallback-pb-{uuid.uuid4().hex[:8]}"

        from kdexter.audit.evidence_store import EvidenceBundle
        bundle = EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            created_at=now,
            trigger="incident_playback",
            actor="i04_playback",
            action="playback_completed",
            before_state=None,
            after_state={
                "incident_id": incident_id,
                "timeline_entries": len(timeline),
                "confidence": confidence.value,
            },
            artifacts=[{"phase": e.phase, "source": e.source, "timestamp": e.timestamp} for e in timeline[:20]],
        )
        return gate.evidence_store.store(bundle)
    except Exception as e:
        logger.warning("playback_evidence_store_failed", error=str(e))
        return f"fallback-pb-{uuid.uuid4().hex[:8]}"
