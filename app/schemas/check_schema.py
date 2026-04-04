"""
I-03: Constitution Check Schema — Operating Constitution 제23~31조 준수 자동 점검 스키마

역참조: Operating Constitution v1.0 제23조~제31조
기준 문서: docs/operations/check_policy.md

제약:
  - 허용 등급: OK / WARN / FAIL / BLOCK (제25조, 4종 제한)
  - BLOCK = 운영자 개입 없이 자동 진행 불가 (제26조, FAIL보다 강한 차단)
  - FAIL = 점검 실패, 복구 조치 필요 (제26조)
  - WARN = 경미한 이슈, 자동 복구 금지 (제24조)
  - OK = 전 항목 통과, evidence 첨부 필수 (제27조)
  - 점검 주기: DAILY / HOURLY / EVENT (제23조)
  - EVENT 점검은 trigger 필드 필수 (제28조)
  - Check, Don't Repair. 자동 실행 권한 없음. (제24조, 제31조)
  - 절대시간(ISO 8601) 우선 (제13조)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# 제25조: 점검 결과 등급 (이 목록 이외 추가 금지)
# ---------------------------------------------------------------------------
class CheckResultGrade(str, Enum):
    """
    점검 결과 등급 (제25조).

    BLOCK: 운영자 개입 없이 자동 진행 절대 불가. FAIL보다 강한 차단 등급.
    FAIL:  점검 실패. 복구 조치 필요. 자동 복구는 금지.
    WARN:  경미한 이슈. 자동 복구 금지. 기록 필수.
    OK:    전 항목 통과. evidence 첨부 필수.
    """

    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
    BLOCK = "BLOCK"


# ---------------------------------------------------------------------------
# 제23조: 점검 주기 유형
# ---------------------------------------------------------------------------
class CheckType(str, Enum):
    """
    점검 주기 유형 (제23조).

    DAILY:  일 1회 정기 점검.
    HOURLY: 매 시간 주기 점검.
    EVENT:  특정 사건 발생 시 트리거되는 점검. trigger 필드 필수 (제28조).
    """

    DAILY = "DAILY"
    HOURLY = "HOURLY"
    EVENT = "EVENT"


# ---------------------------------------------------------------------------
# 제28조: EVENT 점검 트리거 유형 (6종 고정, 추가 금지)
# ---------------------------------------------------------------------------
class EventTrigger(str, Enum):
    """
    EVENT 점검 트리거 유형 (제28조). 6종 고정 목록.

    이 목록 이외의 트리거 추가는 헌법 개정 절차를 통해서만 가능하다.
    """

    PROCESS_RESTART = "process_restart"
    DB_RECONNECT = "db_reconnect"
    API_RECOVERY = "api_recovery"
    LOCKDOWN_RELEASE = "lockdown_release"
    LIVE_PROMOTION = "live_promotion"
    CAPITAL_EXPANSION = "capital_expansion"


# ---------------------------------------------------------------------------
# 제27조: 개별 점검 항목
# ---------------------------------------------------------------------------
class CheckItem(BaseModel):
    """
    개별 점검 항목 단건 (제27조).

    각 항목은 관찰값과 기대값을 명시하며, 판정 근거(evidence_ref)를 첨부해야 한다.
    자동 복구를 수행하지 않는다. (제24조)
    """

    name: str = Field(description="점검 항목명")
    grade: CheckResultGrade = Field(description="항목별 판정 등급 (제25조)")
    observed: Any = Field(description="관찰된 실제 값")
    expected: str = Field(description="기대 기준 값 또는 조건 문자열")
    evidence_ref: Optional[str] = Field(
        default=None, description="근거 Evidence/Receipt ID (OK 등급 시 필수 권고)"
    )
    message: str = Field(description="판정 사유 및 설명")
    rule_refs: list[str] = Field(
        default_factory=list,
        description="이 항목이 준거하는 헌법 조항 번호 목록 (예: ['제27조', '제29조'])",
    )


# ---------------------------------------------------------------------------
# 제23조~제31조: 헌법 점검 결과 전체
# ---------------------------------------------------------------------------
class ConstitutionCheckResult(BaseModel):
    """
    헌법 준수 자동 점검 결과 전체 (제23조~제31조).

    - BLOCK 등급 시 operator_action_required 자동 True (제26조).
    - EVENT 유형 시 trigger 필드 필수 (제28조).
    - 자동 실행 권한 없음. Check, Don't Repair. (제24조, 제31조)
    """

    check_type: CheckType = Field(description="점검 주기 유형 (제23조)")
    timestamp: str = Field(description="점검 실행 시각 (ISO 8601, 제13조)")
    result: CheckResultGrade = Field(description="전체 판정 등급 (제25조)")
    summary: str = Field(description="점검 결과 한 줄 요약")
    items: list[CheckItem] = Field(
        default_factory=list, description="개별 점검 항목 목록 (제27조)"
    )
    failures: list[str] = Field(
        default_factory=list,
        description="실패 항목명 목록 (항목명 기준 오름차순 정렬, 제29조)",
    )
    evidence_id: str = Field(description="이 점검 결과 자체의 Evidence ID")
    rule_refs: list[str] = Field(
        default_factory=list,
        description="이 점검 결과가 준거하는 헌법 조항 번호 목록",
    )
    trigger: Optional[EventTrigger] = Field(
        default=None,
        description="EVENT 점검 트리거 유형 (check_type=EVENT 시 필수, 제28조)",
    )
    operator_action_required: bool = Field(
        default=False,
        description="운영자 개입 필요 여부. BLOCK 등급 시 자동 True (제26조)",
    )

    @model_validator(mode="after")
    def enforce_block_operator_action(self) -> "ConstitutionCheckResult":
        """BLOCK 등급이면 operator_action_required를 강제 True로 설정 (제26조)."""
        if self.result == CheckResultGrade.BLOCK:
            object.__setattr__(self, "operator_action_required", True)
        return self

    @model_validator(mode="after")
    def enforce_event_trigger(self) -> "ConstitutionCheckResult":
        """EVENT 점검 유형은 trigger 필드가 반드시 지정되어야 한다 (제28조)."""
        if self.check_type == CheckType.EVENT and self.trigger is None:
            raise ValueError(
                "check_type=EVENT 인 경우 trigger 필드는 필수입니다. (제28조)"
            )
        return self

    @model_validator(mode="after")
    def sort_failures(self) -> "ConstitutionCheckResult":
        """failures 목록은 항목명 기준 오름차순 정렬 (제29조)."""
        if self.failures:
            object.__setattr__(self, "failures", sorted(self.failures))
        return self


# ---------------------------------------------------------------------------
# 점검 결과 요약 응답
# ---------------------------------------------------------------------------
class CheckSummaryResponse(BaseModel):
    """
    I-03 ops-checks 엔드포인트 응답.

    최근 점검 결과 목록과 유형별 그룹핑 힌트를 포함한다.
    자동 실행 권한 없음. Check, Don't Repair. (제24조, 제31조)

    by_type 필드는 CheckType 값을 키로 하며,
    각 값은 해당 유형의 최근 점검 건수를 나타낸다.
    """

    recent_checks: list[ConstitutionCheckResult] = Field(
        default_factory=list,
        description="최근 점검 결과 목록 (시간 역순 권고)",
    )
    total_count: int = Field(default=0, description="전체 점검 결과 건수")
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="유형별 점검 건수 힌트 (키: CheckType 값, 값: 건수)",
    )
    block_count: int = Field(
        default=0,
        description="BLOCK 등급 점검 건수 (제26조 — 운영자 개입 필요 건수)",
    )
    fail_count: int = Field(
        default=0, description="FAIL 등급 점검 건수"
    )
    note: str = Field(
        default=(
            "Check, Don't Repair. 자동 실행 권한 없음. (제24조, 제31조)"
        ),
        description="운영 원칙 고지",
    )
