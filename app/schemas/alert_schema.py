"""
I-02: Constitution Alert Schema — Operating Constitution 제14~22조 준수 알림 스키마

역참조: Operating Constitution v1.0 제14조~제22조
기준 문서: docs/operations/alert_policy.md

제약:
  - 허용 등급: INFO / WARNING / CRITICAL / PROMOTION (제15조, 4종 제한)
  - 표준 필드 8항목 필수 (제20조)
  - WARNING 이상 operator_action_required 강제 (제20조)
  - 알림은 자동 실행 권한을 가지지 않는다
  - 절대시간(ISO 8601) 우선 (제13조)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 제15조: 알림 등급 (이 목록 이외 추가 금지)
# ---------------------------------------------------------------------------
class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    PROMOTION = "PROMOTION"


# ---------------------------------------------------------------------------
# 제20조: 표준 필드 8항목
# ---------------------------------------------------------------------------
class ConstitutionAlert(BaseModel):
    """
    헌법 준수 알림 단건. 표준 필드 8항목 (제20조).
    알림은 운영 개입 유도 장치이며, 자동 실행 권한을 가지지 않는다 (제14조).
    """

    level: AlertLevel = Field(description="알림 등급 (제15조)")
    system_status: str = Field(description="현재 시스템 상태 문구")
    event_name: str = Field(description="사건명")
    occurred_at: str = Field(description="발생 시각 (ISO 8601)")
    impact_scope: Optional[str] = Field(default=None, description="영향 범위")
    auto_action_result: Optional[str] = Field(default=None, description="자동 조치 결과")
    operator_action_required: bool = Field(description="운영자 해야 할 일 (WARNING 이상 필수)")
    evidence_receipt_id: Optional[str] = Field(default=None, description="Evidence/Receipt ID")


# ---------------------------------------------------------------------------
# 알림 요약 응답
# ---------------------------------------------------------------------------
class AlertSummaryResponse(BaseModel):
    """
    I-02 ops-alerts 엔드포인트 응답.
    최근 알림 목록 + 억제/복구 통계.
    자동 실행 권한 없음.
    """

    alerts: list[ConstitutionAlert] = Field(default_factory=list, description="최근 알림 목록")
    total_count: int = Field(default=0, description="전체 알림 건수")
    suppressed_count: int = Field(default=0, description="억제된 알림 건수 (제22조 억제 규칙)")
    recovery_count: int = Field(default=0, description="복구 알림 건수 (제22조 복구 알림 필수)")
    note: str = Field(
        default="알림은 운영 개입 유도 장치이며, 자동 실행 권한을 가지지 않는다.",
        description="제14조 원칙",
    )
