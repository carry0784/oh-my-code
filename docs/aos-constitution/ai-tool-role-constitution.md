---
document_id: DOC-L2-AI-TOOL-ROLE
title: "AI 도구 역할 헌법"
level: L2
authority_mode: POLICY
parent: DOC-L1-CONSTITUTION
version: "1.0.0"
last_updated: "2026-03-29"
defines: [AI 도구 역할, 권한, 금지행위, Provider 정책, 상태별 허용 매핑, 설계 운영안]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum 값, B1/B2/A 티어 정의]
---

# AI 도구 역할 헌법

> 경계선 선언: 본 문서(DOC-L2-AI-TOOL-ROLE)는 시스템에서 사용하는 AI 도구의 역할·권한·금지행위를 정의한다. 헌법 원칙과 불변량은 DOC-L1-CONSTITUTION에서만 정의하며, 본 문서는 이를 재정의하지 않는다.

## 1. 범위

본 문서는 다음을 정의한다:
- 시스템에 연결된 AI 도구의 역할과 책임 경계
- 각 도구의 허용 행위와 금지 행위
- Provider 선택 및 변경 거버넌스
- 상태별 도구 허용 매핑
- 설계 작업 시 운영 절차

## 2. 연결된 AI 도구

### 2.1 현재 연결 도구

| 도구 | 위치 | 역할 |
|------|------|------|
| Anthropic Claude (claude-sonnet-4-20250514) | `app/agents/base.py` | 트레이딩 에이전트 기본 LLM Provider |
| OpenAI GPT-4 (gpt-4-turbo-preview) | `app/agents/base.py` | 트레이딩 에이전트 폴백 LLM Provider |
| Claude Code | `.claude/CLAUDE.md` | 개발 작업 라우팅 (코드 탐색·수정·리뷰·문서) |
| AgentOrchestrator | `app/agents/orchestrator.py` | 에이전트 체이닝 + GovernanceGate 경유 보장 |

### 2.2 미연결 도구

| 도구 | 상태 | 판정 |
|------|------|------|
| 로컬 AI | 코드·문서·설정 어디에도 참조 없음 | 역할 미정의. 도입 시 본 문서 개정 필수 |
| Ollama | 코드·문서·설정 어디에도 참조 없음 | 역할 미정의. 도입 시 본 문서 개정 필수 |

## 3. 역할 분담

### 3.1 역할 정의표

| 도구 | 맡길 일 | 맡기지 말 일 |
|------|---------|-------------|
| **Anthropic Claude** | 정밀 신호 검증, 정밀 리스크 판정 | 실거래 실행, 거래소 직접 호출, 독자적 포지션 변경 |
| **OpenAI GPT-4** | Anthropic 장애 시 폴백 추론 | 기본 Provider 고정 사용, 실거래 실행 |
| **Claude Code** | 코드 탐색·수정·리뷰, 문서 관리, 설계 초안 | 트레이딩 판단, 포지션 변경, 실거래 접근 |
| **AgentOrchestrator** | 에이전트 체이닝, GovernanceGate 경유 보장, 통제된 LLM 호출 흐름 관리 | 독자적 거래 판단, 거래소 직접 호출, 판정 주체로 동작 |

### 3.2 능력 매트릭스

| 도구 | 추론 | 코드 수정 | 거래 판단 | 실거래 실행 | 비용 통제 대상 | 인간 승인 필요 |
|------|------|----------|----------|-----------|-------------|--------------|
| Anthropic Claude | 예 | 아니오 | 예 | **아니오** | 예 | 예 |
| OpenAI GPT-4 | 예 (폴백) | 아니오 | 예 (폴백) | **아니오** | 예 | 예 |
| Claude Code | 아니오 (트레이딩) | 예 | **아니오** | **아니오** | 낮음 | 예 |
| AgentOrchestrator | 아니오 | 아니오 | 체이닝만 | **아니오** | 예 | 예 |

## 4. 전 도구 공통 금지행위

아래 행위는 **모든 AI 도구**에 대해 예외 없이 금지한다.

| # | 금지행위 | 근거 | 위반 시 |
|---|---------|------|--------|
| P-01 | 거래소 API 직접 호출 | D-001 (TCL-only) | LOCKDOWN |
| P-02 | EvidenceBundle 없는 판정 | D-002 | LOCKDOWN |
| P-03 | ForbiddenLedger 미점검 실행 | D-009 | LOCKDOWN |
| P-04 | 비용 예산 초과 호출 | M-08, G-22 | BLOCKED |
| P-05 | VALIDATING 진입 없는 에이전트 실행 | GovernanceGate 우회 | LOCKDOWN |
| P-06 | 인간 승인 없는 LOCKDOWN 해제 | D-004 | LOCKDOWN 유지 |
| P-07 | 독자적 모델/Provider 변경 | §7 참조 | BLOCKED |

### 4.1 GovernanceGate 등록 금지행위

GovernanceGate에 사전 등록된 에이전트 스코프 금지행위:

| ID | 패턴 | 설명 | 심각도 |
|----|------|------|--------|
| FA-AGENT-001 | `AGENT_DIRECT_EXCHANGE_CALL` | TCL 우회 거래소 직접 호출 | LOCKDOWN |
| FA-AGENT-002 | `AGENT_UNAPPROVED_EXECUTION` | 리스크 점검 없는 거래 실행 | LOCKDOWN |
| FA-AGENT-003 | `AGENT_EXCEED_POSITION_LIMIT*` | 포지션 한도 초과 승인 | BLOCKED |
| FA-AGENT-004 | `AGENT_SKIP_GOVERNANCE*` | 거버넌스 게이트 우회 시도 | LOCKDOWN |

## 5. 상태별 도구 허용 매핑

| Work State | 허용 도구 | 금지 도구 |
|------------|----------|----------|
| RESEARCH / ANALYZE | Claude Code | 거래소 접근 주체 전부 |
| VALIDATING | Anthropic Claude, OpenAI (폴백), AgentOrchestrator | Claude Code |
| EXECUTION READY | AgentOrchestrator + GovernanceGate 통과 주체만 | 일반 LLM 직접 실행 |
| LIVE EXECUTION | TCL / OrderService만 | **모든 AI 도구** |

**핵심 원칙:** LIVE EXECUTION 상태에서는 어떤 AI 도구도 직접 실행 권한을 갖지 않는다. 실행은 TCL을 통해서만 이루어진다.

## 6. GovernanceGate와의 관계

GovernanceGate는 **통제 경계(control boundary)**이며 판정자가 아니다.

| GovernanceGate가 하는 일 | GovernanceGate가 하지 않는 일 |
|-------------------------|---------------------------|
| 판단 전 통제선 진입 | 거래 판단 |
| 금지행위 선점검 (ForbiddenLedger) | 프롬프트 수정 |
| VALIDATING 10-check 상태 분류 기록 | 리스크 계산 |
| EvidenceBundle 생성 (pre/post/error) | 에이전트 체이닝 순서 결정 |
| 실행 흐름 차단/통과 결정 | 독자적 실행 |

### 6.1 VALIDATING 10-check 에이전트 스코프 분류

| # | 항목 | 에이전트 스코프 상태 | 근거 |
|---|------|-------------------|------|
| 1 | FORBIDDEN_CHECK | passed/failed | 실행됨 |
| 2 | MANDATORY_CHECK | passed/failed | 실행됨 |
| 3 | COMPLIANCE_CHECK | passed/failed | 실행됨 |
| 4 | DRIFT_CHECK | not_applicable | 단일 agent call 스코프 비대상. MainLoop/L15 |
| 5 | CONFLICT_CHECK | not_applicable | 규칙 변경 미수행. RuleLedger/L16 |
| 6 | PATTERN_CHECK | passed/failed | FailurePatternMemory.classify_recurrence() 실행. PATTERN 반복 시 차단 |
| 7 | BUDGET_CHECK | passed/failed | CostController.check() 실행. resource_usage_ratio > 1.0 시 차단 |
| 8 | TRUST_CHECK | not_applicable | 신뢰도 감쇠 비대상. TrustState/L19 |
| 9 | LOOP_CHECK | not_applicable | 루프 건강도 비대상. LoopMonitor/L28 |
| 10 | LOCK_CHECK | not_applicable | 스펙 잠금 변경 미수행. SpecLock/L22 |

## 7. Provider 선택 및 변경 거버넌스

### 7.1 현재 Provider 구성

| Provider | 모델 | 용도 | 위치 |
|----------|------|------|------|
| Anthropic | claude-sonnet-4-20250514 | 기본 | `app/agents/base.py:18` |
| OpenAI | gpt-4-turbo-preview | 폴백 | `app/agents/base.py:21` |

### 7.2 Provider/Model 변경 규칙

| # | 규칙 | 근거 |
|---|------|------|
| R-01 | 모델 변경은 코드 커밋을 통해서만 이루어진다 | 런타임 변경 금지 |
| R-02 | 모델 변경 커밋은 단독 PR로 분리한다 | 다른 변경과 혼합 금지 |
| R-03 | 모델 변경 PR에는 변경 사유, 비용 영향, 롤백 계획을 명시한다 | 추적 가능성 |
| R-04 | 기본 Provider (Anthropic) 변경은 인간 승인 필수 | P-07 |
| R-05 | 폴백 Provider 추가/제거도 인간 승인 필수 | P-07 |
| R-06 | 모델 업그레이드 시 기존 테스트 전체 통과 필수 | 회귀 방지 |

### 7.3 폴백 전환 조건

Anthropic → OpenAI 폴백은 다음 조건에서만 발생한다:
- Anthropic API 호출 실패 (`_call_llm` 예외)
- 현재 구현: BaseAgent 생성 시 `provider` 파라미터로 결정 (런타임 자동 전환 아님)
- 자동 폴백 메커니즘은 미구현. 구현 시 본 문서 개정 필수.

## 8. 설계 운영안

설계 작업 시 아래 절차를 따른다.

### 8.1 3단계 운영 구조

| 단계 | 담당 | 역할 | 금지 |
|------|------|------|------|
| 1. 초안 작성 | Claude (Anthropic) | 설계 초안만 작성 | 자기 정당화, 방어 논리 |
| 2. 반대토론 | OpenAI GPT-4 | 실패 가능성·숨은 가정·권한 충돌·과설계·누락 리스크 공격적 지적 | 초안 방어, 찬성 논리 |
| 3. 최종 판정 | **인간** | 채택/기각/보류 판정 | — |

### 8.2 반대토론 공격 기준 (고정)

1. 과설계
2. 누락 설계
3. 권한 충돌
4. 상태전이 누락
5. 비용 비현실성
6. 운영 불가능성
7. 헌법 위반 가능성

### 8.3 실행 규칙

- 반대토론은 **초안 완성 직후, 구현 계획 분해 전**에만 수행
- 실행 직전 단계에서는 반대토론 금지 — 헌법/거버넌스 검수만 수행
- 토론은 **1회전 종료형** (초안 1회 → 반대토론 1회 → 통합 1회)
- "찬성 AI" 역할 없음 — 초안 작성자 / 반대토론자 / 최종 판정자 3역할만 존재

## 9. 미연결 도구 도입 절차

로컬 AI, Ollama, 또는 기타 AI 도구를 새로 연결할 때:

1. 본 문서(DOC-L2-AI-TOOL-ROLE)에 역할·권한·금지행위를 먼저 정의한다
2. §3 역할 정의표, §3.2 능력 매트릭스, §5 상태별 매핑을 갱신한다
3. GovernanceGate에 해당 도구 스코프의 ForbiddenAction을 등록한다
4. 인간 승인 후 코드 연결을 진행한다
5. 코드 연결 없이 역할만 먼저 정의하는 것은 허용한다

## 10. 문서 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0.0 | 2026-03-29 | 최초 작성. 4개 연결 도구 역할 정의, 7개 공통 금지행위, Provider 거버넌스, 설계 운영안 |
