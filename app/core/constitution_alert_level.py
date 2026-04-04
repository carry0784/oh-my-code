"""
I-02: Constitution Alert Level Adapter — severity tier → 헌법 alert level 변환

역참조: Operating Constitution v1.0 제14조~제22조
기준 문서: docs/operations/alert_policy.md

목적:
  기존 알림 인프라(C-14~C-32)의 severity_tier(critical/high/low/clear)를
  헌법 alert level(INFO/WARNING/CRITICAL/PROMOTION)로 변환한다.

설계:
  - 기존 인프라를 수정하지 않고 감싸는 어댑터
  - Read-only 변환 (side-effect 없음)
  - Fail-closed: 변환 실패 시 INFO 기본값
  - 자동 실행 권한 생성 금지

등급 매핑 (제15~19조):
  critical → CRITICAL (제18조)
  high     → WARNING  (제17조)
  low      → INFO     (제16조)
  clear    → INFO     (제16조)
  resolve  → INFO     (복구 알림, 제22조)

operator_action_required 규칙 (제20조):
  WARNING 이상 → True
  INFO → False
  PROMOTION → 승인 필요형만 True
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.alert_schema import AlertLevel, ConstitutionAlert


# ---------------------------------------------------------------------------
# Severity tier → Alert level 매핑
# ---------------------------------------------------------------------------

_SEVERITY_TO_LEVEL = {
    "critical": AlertLevel.CRITICAL,
    "high": AlertLevel.WARNING,
    "low": AlertLevel.INFO,
    "clear": AlertLevel.INFO,
}

# PROMOTION 이벤트 키워드 (event_name 기반 분류)
_PROMOTION_KEYWORDS = frozenset({
    "promotion", "demotion", "capital_expand", "capital_reduce",
    "stage_transition", "upgrade", "downgrade",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def map_severity_to_alert_level(
    severity_tier: str,
    event_name: str = "",
    policy_action: str = "",
) -> AlertLevel:
    """
    기존 severity_tier + context → 헌법 AlertLevel 변환.

    규칙:
      1. event_name이 PROMOTION 키워드를 포함하면 → PROMOTION
      2. policy_action이 "resolve"이면 → INFO (복구 알림)
      3. severity_tier 매핑 테이블 적용
      4. 매핑 실패 → INFO (fail-closed, Unknown ≠ Normal이나 알림 수준은 안전하게)
    """
    # Rule 1: PROMOTION 이벤트 분류
    event_lower = event_name.lower()
    for kw in _PROMOTION_KEYWORDS:
        if kw in event_lower:
            return AlertLevel.PROMOTION

    # Rule 2: 복구 알림 → INFO
    if policy_action == "resolve":
        return AlertLevel.INFO

    # Rule 3: 매핑 테이블
    return _SEVERITY_TO_LEVEL.get(severity_tier, AlertLevel.INFO)


def build_constitution_alert(
    severity_tier: str,
    event_name: str,
    system_status: str = "",
    occurred_at: Optional[str] = None,
    impact_scope: Optional[str] = None,
    auto_action_result: Optional[str] = None,
    evidence_receipt_id: Optional[str] = None,
    policy_action: str = "",
) -> ConstitutionAlert:
    """
    표준 8필드 ConstitutionAlert 빌드 (제20조).

    operator_action_required 규칙:
      - CRITICAL → True
      - WARNING → True
      - PROMOTION → True (승격/강등 판단 필요)
      - INFO → False

    자동 실행 권한 없음. 표시/기록 전용.
    """
    level = map_severity_to_alert_level(severity_tier, event_name, policy_action)

    # operator_action_required: WARNING 이상 + PROMOTION
    operator_required = level in (
        AlertLevel.CRITICAL,
        AlertLevel.WARNING,
        AlertLevel.PROMOTION,
    )

    return ConstitutionAlert(
        level=level,
        system_status=system_status or "unknown",
        event_name=event_name or "unknown_event",
        occurred_at=occurred_at or datetime.now(timezone.utc).isoformat(),
        impact_scope=impact_scope,
        auto_action_result=auto_action_result,
        operator_action_required=operator_required,
        evidence_receipt_id=evidence_receipt_id,
    )


def convert_flow_entry_to_alert(
    entry: dict[str, Any],
    system_status: str = "",
) -> ConstitutionAlert:
    """
    기존 FlowLogEntry dict → ConstitutionAlert 변환.

    flow_log 엔트리 필드:
      - severity_tier (from routing)
      - policy_action (send/suppress/escalate/resolve)
      - receipt_id
      - executed_at

    Fail-closed: 변환 실패 시 INFO 기본 알림 반환.
    """
    try:
        severity = ""
        policy_action = entry.get("policy_action", "")

        # Derive severity from policy_urgent or severity_tier
        if entry.get("policy_urgent"):
            severity = "critical"
        elif entry.get("severity_tier"):
            severity = entry["severity_tier"]
        elif policy_action == "escalate":
            severity = "high"
        elif policy_action == "resolve":
            severity = "clear"
        else:
            severity = "low"

        # Derive event name from receipt or flow data
        event_name = entry.get("highest_incident", "")
        if not event_name:
            event_name = entry.get("incident", "")
        if not event_name:
            event_name = policy_action or "unknown_event"

        return build_constitution_alert(
            severity_tier=severity,
            event_name=event_name,
            system_status=system_status,
            occurred_at=entry.get("executed_at"),
            impact_scope=None,
            auto_action_result=policy_action if policy_action else None,
            evidence_receipt_id=entry.get("receipt_id"),
            policy_action=policy_action,
        )
    except Exception:
        # Fail-closed
        return ConstitutionAlert(
            level=AlertLevel.INFO,
            system_status=system_status or "unknown",
            event_name="conversion_failed",
            occurred_at=datetime.now(timezone.utc).isoformat(),
            impact_scope=None,
            auto_action_result=None,
            operator_action_required=False,
            evidence_receipt_id=None,
        )


def convert_receipt_to_alert(
    receipt: dict[str, Any],
    system_status: str = "",
) -> ConstitutionAlert:
    """
    기존 StoredReceipt dict → ConstitutionAlert 변환.
    Fail-closed.
    """
    try:
        severity = receipt.get("severity_tier", "low")
        event_name = receipt.get("highest_incident", "")
        if not event_name:
            event_name = receipt.get("overall_status", "unknown_event")

        return build_constitution_alert(
            severity_tier=severity,
            event_name=event_name,
            system_status=system_status,
            occurred_at=receipt.get("stored_at"),
            impact_scope=None,
            auto_action_result=receipt.get("triage_top"),
            evidence_receipt_id=receipt.get("receipt_id"),
        )
    except Exception:
        return ConstitutionAlert(
            level=AlertLevel.INFO,
            system_status=system_status or "unknown",
            event_name="conversion_failed",
            occurred_at=datetime.now(timezone.utc).isoformat(),
            impact_scope=None,
            auto_action_result=None,
            operator_action_required=False,
            evidence_receipt_id=None,
        )
