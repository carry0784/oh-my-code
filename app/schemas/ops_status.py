"""
I-01: Operations Status Schema — Constitution-Compliant Dashboard Response

역참조: Operating Constitution v1.0 제5조~제13조, 제41조~제42조
기준 문서: docs/operations/dashboard_spec.md

제약:
  - Read-Only 표면 전용 (제11조)
  - 허용 상태 문구: HEALTHY / DEGRADED / UNVERIFIED / BRAKE / LOCKDOWN (제12조)
  - System Healthy / Trading Authorized 분리 표기 (제42조)
  - Ops Score는 보조 지표이며 단독 권한을 생성하지 않는다 (제41조)
  - 모든 시각 정보는 절대시간(ISO 8601)을 우선한다 (제13조)
  - 자동 승인 / 자동 해제 / 거래 권한 생성 금지
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 제12조: 허용 상태 문구 (이 목록 이외 추가 금지)
# ---------------------------------------------------------------------------
class SystemStatusWord(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNVERIFIED = "UNVERIFIED"
    BRAKE = "BRAKE"
    LOCKDOWN = "LOCKDOWN"


# ---------------------------------------------------------------------------
# 제7조: 전역 상태 바
# ---------------------------------------------------------------------------
class GlobalStatusBar(BaseModel):
    app_env: str = Field(description="APP_ENV")
    phase: str = Field(description="Phase")
    enforcement_state: str = Field(description="Enforcement State")
    trading_permission: bool = Field(description="Trading Permission (표시값, 권한 생성 아님)")
    current_server_time: str = Field(description="Current Server Time (ISO 8601)")
    last_successful_api_poll: Optional[str] = Field(
        default=None, description="Last Successful API Poll (ISO 8601)"
    )
    link_lost_since: Optional[str] = Field(default=None, description="Link Lost Since (ISO 8601)")
    prod_lock: bool = Field(description="PROD_LOCK")


# ---------------------------------------------------------------------------
# 제8조: 무결성 패널
# ---------------------------------------------------------------------------
class IntegrityPanel(BaseModel):
    exchange_db_consistency: str = Field(
        description="Exchange ↔ DB ↔ Engine ↔ Cache 정합성 (ok/mismatch/unknown)"
    )
    snapshot_age_seconds: Optional[int] = Field(default=None, description="Snapshot age (seconds)")
    position_mismatch: bool = Field(description="Position mismatch")
    open_orders_mismatch: bool = Field(description="Open orders mismatch")
    balance_mismatch: bool = Field(description="Balance mismatch")
    stale_data: bool = Field(description="Stale data 여부")


# ---------------------------------------------------------------------------
# 제9조: 거래 안전 패널
# ---------------------------------------------------------------------------
class TradingSafetyPanel(BaseModel):
    allowed_capital_ratio: Optional[float] = Field(default=None, description="허용 자본 비율")
    order_success_rate: Optional[float] = Field(default=None, description="주문 성공률")
    reject_count: int = Field(default=0, description="Reject 건수")
    cancel_residual: bool = Field(default=False, description="Cancel residual 여부")
    latency_status: str = Field(default="unknown", description="Latency 상태")
    kill_switch_active: bool = Field(default=False, description="Kill switch 상태")
    current_trading_mode: str = Field(default="observation", description="현재 거래 모드")
    trading_block_reason: Optional[str] = Field(default=None, description="거래 차단 사유")


# ---------------------------------------------------------------------------
# 제10조: 사고·증거 패널
# ---------------------------------------------------------------------------
class IncidentEvidencePanel(BaseModel):
    incident_title: Optional[str] = Field(default=None, description="Incident title")
    severity: Optional[str] = Field(default=None, description="Severity")
    first_occurred_at: Optional[str] = Field(default=None, description="최초 발생 시각 (ISO 8601)")
    last_confirmed_at: Optional[str] = Field(
        default=None, description="마지막 확인 시각 (ISO 8601)"
    )
    impact_scope: Optional[str] = Field(default=None, description="영향 범위")
    auto_action_result: Optional[str] = Field(default=None, description="자동 조치 결과")
    operator_action_required: bool = Field(default=False, description="운영자 조치 필요 여부")
    evidence_receipt_id: Optional[str] = Field(default=None, description="Evidence/Receipt ID")


# ---------------------------------------------------------------------------
# 제12조: 시스템 상태
# ---------------------------------------------------------------------------
class SystemStatus(BaseModel):
    status_word: SystemStatusWord = Field(description="허용 상태 문구 (5종 제한)")
    status_reason: str = Field(description="상태 판정 사유")


# ---------------------------------------------------------------------------
# 제42조: Trading Authorized 이중 잠금
# ---------------------------------------------------------------------------
class DualLock(BaseModel):
    system_healthy: bool = Field(description="System Healthy (분리 표기)")
    trading_authorized: bool = Field(description="Trading Authorized (분리 표기)")


# ---------------------------------------------------------------------------
# 제41조: Ops Score (보조 지표)
# ---------------------------------------------------------------------------
class OpsScore(BaseModel):
    integrity: float = Field(ge=0.0, le=1.0, description="Integrity")
    connectivity: float = Field(ge=0.0, le=1.0, description="Connectivity")
    execution_safety: float = Field(ge=0.0, le=1.0, description="Execution Safety")
    evidence_completeness: float = Field(ge=0.0, le=1.0, description="Evidence Completeness")
    note: str = Field(
        default="보조 지표. 단독 권한 없음.",
        description="Ops Score는 보조 지표이며 단독으로 권한을 생성하지 않는다.",
    )


# ---------------------------------------------------------------------------
# 전체 응답: 4구역 + 상태 + 이중 잠금 + Ops Score
# ---------------------------------------------------------------------------
class OpsStatusResponse(BaseModel):
    """
    I-01 운영 대시보드 ops-status 응답.
    4구역 구조 + 상태 문구 + 이중 잠금 + Ops Score.
    Read-Only 표면 전용. 자동 실행 권한 없음.
    """

    global_status_bar: GlobalStatusBar = Field(description="제7조: 전역 상태 바")
    integrity_panel: IntegrityPanel = Field(description="제8조: 무결성 패널")
    trading_safety_panel: TradingSafetyPanel = Field(description="제9조: 거래 안전 패널")
    incident_evidence_panel: IncidentEvidencePanel = Field(description="제10조: 사고·증거 패널")
    system_status: SystemStatus = Field(description="제12조: 시스템 상태")
    dual_lock: DualLock = Field(description="제42조: 이중 잠금")
    ops_score: OpsScore = Field(description="제41조: Ops Score (보조 지표)")
