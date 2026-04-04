"""
B-08: AI Assist Data Source Schema — read-only 정규화 소스 구조

AI Assist가 소비할 정규화된 데이터 소스 shape를 정의한다.
summary 중심으로 제한하며, raw 민감 정보(agent_analysis, guard condition)는 노출하지 않는다.
실행/추천/판단 자동화 없음. read-only source shape만 정의.

연결 소스: ops_summary, signal_pipeline, position_overview, evidence_summary
제외 소스: 실시간 호가(B-09), agent_analysis 원문, guard condition 원문
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class OpsSummary(BaseModel):
    """I-01~I-07 ops 계열 요약. AI 친화적 shape."""

    status_word: str = Field(default="UNKNOWN", description="I-01 시스템 상태 문구")
    system_healthy: bool = Field(default=False, description="I-01 이중 잠금: system healthy")
    trading_authorized: bool = Field(default=False, description="I-01 이중 잠금: trading authorized")
    ops_score_average: float = Field(default=0.0, description="I-01 Ops Score 4축 평균")
    latest_check_grade: str = Field(default="UNKNOWN", description="I-03 최근 점검 등급")
    preflight_decision: str = Field(default="UNKNOWN", description="I-04 preflight 판정")
    gate_decision: str = Field(default="UNKNOWN", description="I-05 gate 판정")
    gate_conditions_met: int = Field(default=0, description="I-05 충족 조건 수")
    approval_decision: str = Field(default="UNKNOWN", description="I-06 승인 판정")
    policy_decision: str = Field(default="UNKNOWN", description="I-07 policy 판정")
    alert_total: int = Field(default=0, description="I-02 최근 알림 건수")
    alert_suppressed: int = Field(default=0, description="I-02 억제 건수")


class SignalPipelineSummary(BaseModel):
    """신호 파이프라인 요약."""

    total_24h: int = Field(default=0)
    validated: int = Field(default=0)
    rejected: int = Field(default=0)
    executed: int = Field(default=0)
    pending: int = Field(default=0)
    rejection_rate: Optional[float] = Field(default=None, description="거부율 (0.0~1.0)")


class PositionOverview(BaseModel):
    """포지션 개요."""

    total_positions: int = Field(default=0)
    total_value: Optional[float] = Field(default=None)
    unrealized_pnl: Optional[float] = Field(default=None)
    exchanges_connected: int = Field(default=0)
    exchanges_total: int = Field(default=6)


class EvidenceSummary(BaseModel):
    """evidence 요약. 상세 원문은 노출하지 않고 존재 여부/건수만 제공."""

    total_bundles: Optional[int] = Field(default=None, description="전체 evidence 건수")
    governance_active: bool = Field(default=False)
    has_recent_evidence: bool = Field(default=False, description="최근 evidence 존재 여부")
    orphan_count: Optional[int] = Field(default=None, description="미연결 evidence 수")


class AIAssistSources(BaseModel):
    """
    B-08: AI Assist 정규화 데이터 소스.
    read-only summary 전용. 실행/추천/판단 자동화 없음.
    """

    ops_summary: OpsSummary = Field(default_factory=OpsSummary)
    signal_pipeline: SignalPipelineSummary = Field(default_factory=SignalPipelineSummary)
    position_overview: PositionOverview = Field(default_factory=PositionOverview)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    source_note: str = Field(
        default="Read-only AI Assist sources. No execution/recommendation/judgment.",
    )
