---
document_id: DOC-L3-SPRINT-5
title: "Sprint 5 — 차단 축"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 5 구현 과제, 차단 축 검증 범위]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, Invariant Lens 정의, UncertaintyContext 정의, Counterfactual 정의]
---

# Sprint 5 — 차단 축

> Scope Token: 본 Sprint는 차단 축의 검증에 한정한다. U3 상태와 Counterfactual 개념은 DOC-L2-INVARIANT-LENS에서 정의하며, 본 문서는 해당 정의를 참조만 한다.

> 경고: 본 Sprint는 고밀도 Sprint이다. 상위 문서의 정의를 재정의하거나 새 이론을 도입하지 않는다.

## 1. Sprint 목표

U3(Maximum Uncertainty) + outbound 조합이 LOCKDOWN을 유발하는 차단 경로를 검증한다.
Counterfactual 차단 조건이 실행 전에 "만약 이 실행이 허용된다면 어떤 결과가 발생하는가"를 평가하여 위험을 사전 차단하는 메커니즘을 확인한다.
Work State Machine의 recovery path에서 차단이 적절히 작동함을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| Work State Machine | recovery path, BLOCKED/ISOLATED 전이 | B2 |
| L3 | Security & Isolation | B1 |
| L26 | Recovery Engine | A (정책은 B1) |

소스: work_state.py recovery path, failure_taxonomy.md

## 3. 구현 과제

### 3.1 U3 + outbound → LOCKDOWN

1. UncertaintyContext가 U3 상태일 때 외부 실행(outbound) 요청이 감지됨을 확인
2. U3 + outbound 조합이 즉시 SecurityStateEnum.LOCKDOWN 에스컬레이션을 트리거함을 확인
3. LOCKDOWN 트리거 시 EvidenceBundle이 생산됨을 확인
4. LOCKDOWN 이후 모든 자동 작업이 중지됨을 확인
5. LOCKDOWN 해제는 Human Override(L27)만 가능함을 확인(D-004)

### 3.2 Counterfactual 차단 조건

Counterfactual 평가는 실행 전에 가상 시나리오를 분석하여 위험을 사전에 차단한다:

1. 실행 요청이 Forge→Lens 단계에 진입할 때 Counterfactual 평가가 트리거됨을 확인
2. Counterfactual 평가 항목:
   - "이 실행이 D-001(TCL-only)을 위반할 가능성이 있는가?"
   - "이 실행이 현재 SecurityState에서 허용되는 범위를 초과하는가?"
   - "이 실행이 Failure Taxonomy의 CRITICAL 실패를 유발할 가능성이 있는가?"
3. Counterfactual 평가 결과가 위험을 감지하면 실행을 차단하고 review 상태로 전환됨을 확인
4. Counterfactual 차단 시 EvidenceBundle이 생산되며, 차단 사유가 기록됨을 확인
5. Counterfactual 평가는 기존 교리(D-001~D-010)만 참조하며, 새 교리를 생성하지 않음을 확인

### 3.3 Recovery Path 차단

1. FAILED → REPLAY → ROOT_CAUSE → REDESIGN → RULE_UPDATE → SANDBOX → IMPROVEMENT → RESUME 경로에서 각 전이의 Guard가 작동함을 확인
2. Recovery Loop가 사고당 3회 복구 상한(D-006)을 초과하면 차단됨을 확인
3. 3회 초과 시 Human Override 요청이 발생함을 확인
4. ISOLATED 상태에서 자동 복구가 시도되지 않음을 확인 (Human 개입만 허용)
5. BLOCKED 상태에서 원인 분석 없이 재시도가 차단됨을 확인

### 3.4 Failure Taxonomy 연동

1. CRITICAL severity Failure가 즉각 LOCKDOWN + ISOLATED를 트리거함을 확인
2. HIGH severity Failure가 QUARANTINED + FAILED를 트리거함을 확인
3. PATTERN recurrence(3회 이상 OR 7일 내 2회)가 Evolution Loop로 라우팅됨을 확인
4. GOVERNANCE domain CRITICAL이 Recovery + B1 Human Override를 트리거함을 확인

### 3.5 동시 차단 상황

1. Recovery Loop 활성 중 추가 CRITICAL Failure 발생 시 기존 Recovery에 병합됨을 확인
2. 복수 차단 조건이 동시에 성립할 때 가장 높은 severity의 차단이 우선됨을 확인
3. Deadlock 감지 조건(DOC-L2-EXT-API-GOV §10) 충족 시 Human Override 요청이 발생함을 확인

## 4. Gate 활성화

본 Sprint에서 직접 활성화하는 Gate는 없다.
차단 경로에서 Gate 평가가 실패 시 BLOCKED 전이를 트리거하는 기반을 확인한다.

## 5. Mandatory Items

| Mandatory | 관련 구현 과제 |
|-----------|---------------|
| M-03 | risk check — Counterfactual 평가와 리스크 검사 연동 |
| M-04 | security check — SecurityState 에스컬레이션 |
| M-07 | evidence — 모든 차단에서 EvidenceBundle |
| M-14 | trust refresh — Recovery path에서 Trust 갱신 |

### Invariant Lens 반영

본 Sprint는 구조적 불변량 §3.3(LOCKDOWN 해제 제한), §3.4(증거 의무)를 행사한다.
행위적 불변량 §4.5(복구 상한 D-006)의 차단 작동을 검증한다.
U3 상태(DOC-L2-INVARIANT-LENS §6)에서의 차단 정책과 Counterfactual 평가가 Lens 단계의 사전 차단 역할임을 확인한다.

## 6. 종료 기준

- U3 + outbound → LOCKDOWN 차단 작동 확인
- Counterfactual 차단 조건 평가 및 차단 작동 확인
- Recovery path 3회 상한 차단 확인
- ISOLATED 상태에서 자동 복구 차단 확인
- Failure Taxonomy severity별 차단 경로 확인
- 동시 차단 상황에서 우선순위 적용 확인
- 모든 차단에서 EvidenceBundle 생산 확인

## 7. 의존관계

선행: Sprint 3b1, Sprint 3b2
후행: (없음 — 차단 축은 최종 검증 Sprint)
