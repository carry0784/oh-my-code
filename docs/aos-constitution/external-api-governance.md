---
document_id: DOC-L2-EXT-API-GOV
title: "외부 실행/API 거버넌스 정책"
level: L2
authority_mode: POLICY
parent: DOC-L1-CONSTITUTION
version: "1.0.0"
last_updated: "2026-03-21"
defines: [WorkState 정책, VALIDATING 체크리스트, G-xx Gate 정책, M-xx Mandatory 집행점, Failure Taxonomy, Loop 라우팅, Concurrent Failure Protocol, ForbiddenAction 등록 정책]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum 값, B1/B2/A 티어 정의, Invariant Lens 정의]
---

# 외부 실행/API 거버넌스 정책

> 경계선 선언: 본 문서(DOC-L2-EXT-API-GOV)는 외부 실행/API의 구체적 거버넌스 정책을 정의한다. 헌법 원칙과 불변량은 DOC-L1-CONSTITUTION에서만 정의하며, 본 문서는 이를 재정의하지 않는다.

## 1. 범위

본 문서는 DOC-L1-CONSTITUTION §9(외부 실행 경계면)의 위임을 받아 다음을 정의한다:
- Work State Machine의 정상/실패/차단 경로 정책
- VALIDATING 10-check 체크리스트 정책
- Gate Registry(G-01~G-27) 정책
- 18개 Mandatory 항목(M-01~M-18) 집행점
- 루프별 Mandatory 면제
- Failure Taxonomy(3축 분류) 정책
- Loop 라우팅 결정 정책
- Concurrent Failure Protocol
- Forbidden Action 등록 정책

## 2. Work State 정책

Work State Machine은 22개 상태로 구성된다.

정상 실행 경로 (12단계):
DRAFT → CLARIFYING → SPEC_READY → PLANNING → VALIDATING → RUNNING → EVALUATING → APPROVAL_PENDING → EXECUTING → VERIFY → MONITOR → CLOSED

실패 복구 경로 (8단계):
FAILED → REPLAY → ROOT_CAUSE → REDESIGN → RULE_UPDATE → SANDBOX → IMPROVEMENT → RESUME

차단 상태: BLOCKED, ISOLATED

각 전이는 Guard 조건을 가진다. Guard 실패 시 GuardViolationError가 발생하며 전이가 차단된다.
모든 전이는 EvidenceBundle을 생산해야 한다(D-002).

## 3. VALIDATING 체크리스트 정책

VALIDATING은 PLANNING → RUNNING 사이의 단일 상태이며, 내부에 10개 체크를 순서대로 실행한다.
10개 CHECK 상태를 단일 VALIDATING으로 압축한 이유: 모두 순차 실행이며, 하나라도 실패 시 BLOCKED로 동일하게 전이되어 상태 분리 실익이 없다.

체크리스트 (순서 고정, 모두 PASS 필요):

- [1] FORBIDDEN_CHECK — 금지 항목 위반 여부 (차단 우선)
- [2] MANDATORY_CHECK — 18개 Mandatory 항목 충족 여부
- [3] COMPLIANCE_CHECK — 헌법/정책 준수율 확인 (M-09)
- [4] DRIFT_CHECK — Intent Drift 감지 (M-11)
- [5] CONFLICT_CHECK — Rule 충돌 검사 (M-12)
- [6] PATTERN_CHECK — Failure Pattern 대조 (M-13)
- [7] BUDGET_CHECK — 예산 한도 확인 (M-08)
- [8] TRUST_CHECK — Trust 상태 갱신 및 확인 (M-14)
- [9] LOOP_CHECK — 루프 건강 상태 확인 (M-15)
- [10] LOCK_CHECK — Spec Lock 확인 (M-17)

모두 PASS → RUNNING 전환. 하나라도 FAIL → BLOCKED (실패 체크 ID 기록).

## 4. Gate Registry 정책

### 4.1 Gate 상태 및 페이즈

Gate 상태: PENDING, PASS, FAIL, SKIPPED
Gate 페이즈:
- SHADOW — 실패는 기록만, 실행 차단 없음
- ACTIVE — 실패 시 실행 차단

SHADOW → ACTIVE 전환에는 B1 비준이 필요하다.

### 4.2 Shadow Gate (G-01 ~ G-08)

| Gate | 이름 | 연결 Mandatory | 기준 상태 |
|------|------|---------------|-----------|
| G-01 | Shadow Baseline | — | 기준 정의 완료 |
| G-02 | State Recovery | M-05, M-06 | 기준 정의 완료 |
| G-03 | Risk Control | M-03 | 기준 정의 완료 |
| G-04 | Constitution Compliance | M-04, M-09 | 기준 정의 완료 |
| G-05 | Audit Completeness | M-07 | 기준 정의 완료 |
| G-06 | Shadow Signal Quality | — | 기준 정의 완료 |
| G-07 | Shadow Position Sizing | — | 기준 정의 완료 |
| G-08 | Shadow Risk Filter | — | 기준 정의 완료 |

G-09 ~ G-15: Phase 4 확장용 예약 (B1 승인 필요).

### 4.3 Active Gate (G-16 ~ G-27)

| Gate | 이름 | 연결 Mandatory | 기준 상태 |
|------|------|---------------|-----------|
| G-16 | Compliance Gate | M-09 | 기준 미정의 |
| G-17 | Reserved | — | — |
| G-18 | Provenance Gate | M-10 | 기준 미정의 |
| G-19 | Drift Gate | M-11 | 기준 미정의 (OQ-4) |
| G-20 | Conflict Gate | M-12 | 기준 미정의 |
| G-21 | Pattern Gate | M-13 | 기준 미정의 |
| G-22 | Budget Gate | M-08 | 기준 미정의 |
| G-23 | Trust Gate | M-14 | 기준 미정의 (OQ-5) |
| G-24 | Loop Gate | M-15 | 기준 미정의 (OQ-6) |
| G-25 | Completion Gate | M-16 | 기준 미정의 (OQ-7) |
| G-26 | Spec Lock Gate | M-17 | 기준 미정의 |
| G-27 | Research Gate | M-18 | 기준 미정의 |

G-28 ~ G-30: 예약 (기준 미할당).

## 5. Gate ↔ Mandatory 매핑 요약

| Gate | Mandatory | Gate | Mandatory |
|------|-----------|------|-----------|
| G-02 | M-05, M-06 | G-03 | M-03 |
| G-04 | M-04, M-09 | G-05 | M-07 |
| G-16 | M-09 | G-18 | M-10 |
| G-19 | M-11 | G-20 | M-12 |
| G-21 | M-13 | G-22 | M-08 |
| G-23 | M-14 | G-24 | M-15 |
| G-25 | M-16 | G-26 | M-17 |
| G-27 | M-18 | | |

## 6. Mandatory 집행점 (M-01 ~ M-18)

| # | 항목 | 강제 시점 | 강제 Gate | 담당 레이어 | 미충족 시 |
|---|------|-----------|-----------|-------------|-----------|
| M-01 | clarify — 의도 명확화 | CLARIFYING 진입 | — | L4 | CLARIFYING 탈출 불가 |
| M-02 | spec twin — 스펙 쌍 생성 | SPEC_READY 진입 | — | L4 | SPEC_READY 탈출 불가 |
| M-03 | risk check — 리스크 검사 | PLANNING | G-03 | L3 | BLOCKED |
| M-04 | security check — 보안 검사 | PLANNING | G-04 | L3 | BLOCKED |
| M-05 | rollback plan — 롤백 계획 | PLANNING | G-02 | L26 | PLANNING 탈출 불가 |
| M-06 | recovery simulation | PLANNING (Sandbox) | G-02 | L26/B2 | PLANNING 탈출 불가 |
| M-07 | evidence — 증거 첨부 | 모든 전환 시 | G-05 | L10 | 전환 차단 |
| M-08 | budget check — 예산 확인 | VALIDATING [7] | G-22 | L29 | BLOCKED |
| M-09 | compliance check — 준수율 | VALIDATING [3] | G-04, G-16 | L13 | BLOCKED |
| M-10 | provenance — 출처 기록 | Rule Ledger 쓰기 | G-18 | L12 | 등록 거부 |
| M-11 | drift check — 이탈 감지 | VALIDATING [4] | G-19 | L15 | BLOCKED |
| M-12 | conflict check — 충돌 검사 | VALIDATING [5] | G-20 | L16 | BLOCKED |
| M-13 | pattern check — 패턴 대조 | VALIDATING [6] | G-21 | L17 | BLOCKED |
| M-14 | trust refresh — 신뢰 갱신 | VALIDATING [8] | G-23 | L19 | BLOCKED |
| M-15 | loop health — 루프 건강 | VALIDATING [9] | G-24 | L28 | BLOCKED |
| M-16 | completion check — 완성 검증 | VERIFY | G-25 | L21 | VERIFY 탈출 불가 |
| M-17 | spec lock check — 잠금 확인 | VALIDATING [10] | G-26 | L22 | BLOCKED |
| M-18 | research — 리서치 | PLANNING 선행 | G-27 | L23 | PLANNING 탈출 불가 |

## 7. 루프별 Mandatory 면제

Main Loop는 M-01~M-18 전체를 강제한다.
Recovery Loop는 10개를 면제한다: M-01, M-02, M-05, M-06, M-11, M-12, M-13, M-15, M-17, M-18.
면제 근거: 복구는 시간이 핵심이며, 면제된 항목은 복구 완료 후 소급 처리한다.

Self-Improvement Loop와 Evolution Loop는 M-01~M-18 전체를 강제한다.

면제는 속도가 아니라 루프 목적상 중복 또는 역순이 되는 항목에 한정한다.
M-03(risk), M-04(security), M-07(evidence), M-08(budget), M-09(compliance), M-10(provenance), M-14(trust), M-16(completion)은 모든 루프에서 필수이다.

## 8. Failure Taxonomy 정책

모든 Failure는 3개 축으로 분류한다:

**Domain**: INFRA (인프라 장애) / STRATEGY (전략 실패) / GOVERNANCE (정책 위반)
**Severity**: CRITICAL (즉각 LOCKDOWN) / HIGH (QUARANTINED) / MEDIUM (RESTRICTED) / LOW (NORMAL, 경고만)
**Recurrence**: FIRST (최초) / REPEAT (재발, 패턴 미달) / PATTERN (패턴 초과: 3회 이상 OR 7일 내 2회, v4 임시값)

Failure Severity → Security State 전환:
- CRITICAL → LOCKDOWN, Work State → ISOLATED
- HIGH → QUARANTINED, Work State → FAILED
- MEDIUM → RESTRICTED, Work State → FAILED
- LOW → NORMAL 유지, Work State → MONITOR 유지

## 9. Loop 라우팅 정책

| Domain | Severity | Recurrence | 담당 Loop |
|--------|----------|------------|-----------|
| INFRA | CRITICAL | any | Recovery |
| INFRA | HIGH | any | Recovery |
| INFRA | MEDIUM | FIRST/REPEAT | Recovery |
| INFRA | MEDIUM | PATTERN | Recovery + Evolution 예약 |
| INFRA | LOW | any | Main Loop 내 처리 |
| STRATEGY | CRITICAL | any | Recovery |
| STRATEGY | HIGH | FIRST/REPEAT | Self-Improvement |
| STRATEGY | HIGH | PATTERN | Evolution |
| STRATEGY | MEDIUM | FIRST/REPEAT | Self-Improvement |
| STRATEGY | MEDIUM | PATTERN | Evolution |
| STRATEGY | LOW | any | Main Loop 내 처리 |
| GOVERNANCE | CRITICAL | any | Recovery + B1 Human Override |
| GOVERNANCE | HIGH | any | Recovery + B1 통보 |
| GOVERNANCE | MEDIUM | FIRST/REPEAT | Self-Improvement |
| GOVERNANCE | MEDIUM | PATTERN | Evolution + B1 통보 |
| GOVERNANCE | LOW | any | Audit 기록 후 계속 |

INFRA 실패는 항상 Recovery Loop가 담당한다.
STRATEGY CRITICAL은 Recovery로, 나머지는 Recurrence에 따라 Self-Improvement 또는 Evolution으로 분기한다.
GOVERNANCE CRITICAL/HIGH는 Recovery + B1 통보, PATTERN은 Evolution + B1 통보이다.

## 10. Concurrent Failure Protocol

우선순위 (변경 불가): Recovery > Main > Self-Improvement > Evolution

동시 발생 규칙:
- Recovery 활성 중 Evolution/Self-Improvement 발동 → Priority Queue 대기 (Recovery 완료 후 실행)
- Recovery 활성 중 새 Recovery 발동 → 기존 Recovery에 병합
- Main Loop + Recovery 동시 → Main Loop 일시 중단, Recovery 완료 후 Resume

최대 동시 활성: Recovery 1 + Main 1 = 2개. Self-Improvement/Evolution은 Queue 대기.

Deadlock 감지 조건:
1. Recovery Loop가 Rule Ledger Write Lock 보유 중
2. Main Loop가 Rule Ledger Write Lock 대기 중
3. Recovery Loop가 Main Loop 상태 결과를 대기 중
4. 대기 시간 > timeout_deadlock (OQ-2)
→ Deadlock 판정 시 Human Override 요청.

Evolution Loop 지연 한도:
최대 대기 시간 timeout_evolution_defer (OQ-3) 초과 시 Human Override 알림 + 강제 상태 보고.

## 11. Forbidden Action 등록 정책

Forbidden Action은 ForbiddenLedger에 등록되며, 상태와 무관하게 항상 금지된다.
각 Forbidden Action은 action_id(FA-xxx), severity(LOCKDOWN/BLOCKED), pattern, registered_by를 가진다.

LOCKDOWN severity 위반 → 즉시 시스템 LOCKDOWN (D-009).
BLOCKED severity 위반 → 해당 작업 차단 + BLOCKED 상태 전이.

등록 권한: B1(L3)만 Forbidden Action을 등록/해제할 수 있다.
VALIDATING [1] FORBIDDEN_CHECK에서 최우선 검사되며, 위반 시 나머지 체크를 생략하고 즉시 차단한다.

위반 시 EvidenceBundle이 생산되며 감사 추적에 기록된다.

## 12. TCL 거버넌스

TCL(Trading Command Language)은 A 계층 인프라로, L8 Execution Cell의 하위 컴포넌트이다.
모든 거래소 상호작용은 TCL 표준 명령(ORDER.BUY, ORDER.SELL 등)을 통해야 한다(D-001).
상위 레이어의 직접 API 호출은 금지된다.
TCL 어댑터 추가/변경은 B2 승인 + B1 교리 준수 확인이 필요하다.
