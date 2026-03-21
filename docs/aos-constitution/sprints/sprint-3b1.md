---
document_id: DOC-L3-SPRINT-3B1
title: "Sprint 3b1 — 상태 분리 축"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 3b1 구현 과제, 상태 분리 축 검증 범위]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, Invariant Lens 정의, UncertaintyContext 정의]
---

# Sprint 3b1 — 상태 분리 축

> Scope Token: 본 Sprint는 상태 분리 축의 검증에 한정한다. UncertaintyContext는 DOC-L2-INVARIANT-LENS에서 정의하며, 본 문서는 해당 정의를 참조만 한다.

> 경고: 본 Sprint는 고밀도 Sprint이다. 상위 문서의 정의를 재정의하거나 새 이론을 도입하지 않는다.

## 1. Sprint 목표

UncertaintyContext를 Work State Machine에서 독립적인 상태 축으로 분리하고, Lens 입력 상태를 정규화한다.
TransitionGuard가 UncertaintyContext를 참조하여 전이 허용/거부를 결정하는 메커니즘을 검증한다.
Mandatory Enforcement Map의 강제집행 시점과 UncertaintyContext의 상호작용을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| Work State Machine | TransitionGuards + UncertaintyContext | B2 |
| L22 | Spec Lock System | B1/B2 |

소스: work_state.py TransitionGuards, mandatory_enforcement_map.md

## 3. 구현 과제

### 3.1 UncertaintyContext 독립화

1. UncertaintyContext가 WorkStateContext와 독립적으로 관리됨을 확인
2. UncertaintyContext의 U0~U3 상태가 Work State 전이와 별개로 변동할 수 있음을 확인
3. UncertaintyContext 변경 시 EvidenceBundle이 생산됨을 확인
4. UncertaintyContext가 TransitionGuard의 입력으로 사용됨을 확인

### 3.2 TransitionGuard와 UncertaintyContext 결합

1. PLANNING → VALIDATING 전이 Guard에서 UncertaintyContext가 U3이면 전이 차단 확인
2. VALIDATING → RUNNING 전이 Guard에서 UncertaintyContext가 U2 이상이면 실행 보류 확인
3. EXECUTING → VERIFY 전이 Guard에서 UncertaintyContext 변화가 반영됨을 확인
4. Guard 실패 시 GuardViolationError에 UncertaintyContext 상태가 포함됨을 확인

### 3.3 Lens 입력 상태 정규화

Invariant Lens에 전달되는 상태를 정규화한다:
1. Lens 입력은 (WorkStateEnum, UncertaintyContext, SecurityStateEnum) 3-tuple로 정규화됨을 확인
2. 정규화된 입력이 Forge→Lens→Council→Judge 파이프라인에 일관되게 전달됨을 확인
3. 정규화 과정에서 상태 손실이 없음을 확인 (모든 필드가 보존)
4. 정규화 결과가 EvidenceBundle에 기록됨을 확인

### 3.4 Mandatory Enforcement Map 연동

1. VALIDATING 10-check 순서에서 UncertaintyContext가 [4] DRIFT_CHECK에 영향을 미침을 확인
2. [8] TRUST_CHECK에서 UncertaintyContext가 Trust 상태 판정에 참조됨을 확인
3. M-03(risk check)에서 UncertaintyContext가 U2 이상이면 추가 리스크 검사를 요구함을 확인
4. 강제집행 시점에서 UncertaintyContext가 정규화된 상태로 참조됨을 확인

### 3.5 Spec Lock과 UncertaintyContext

1. L22 Spec Lock System에서 UncertaintyContext가 U3이면 잠금 해제를 차단함을 확인
2. Spec Lock 잠금/해제 시 UncertaintyContext 상태가 EvidenceBundle에 기록됨을 확인
3. [10] LOCK_CHECK에서 UncertaintyContext가 참조됨을 확인

## 4. Gate 활성화

본 Sprint에서 직접 활성화하는 Gate는 없다.
G-19(Drift Gate), G-23(Trust Gate)의 UncertaintyContext 입력 정규화 기반을 마련한다.

## 5. Mandatory Items

| Mandatory | 관련 구현 과제 |
|-----------|---------------|
| M-03 | risk check — UncertaintyContext U2 이상 시 추가 검사 |
| M-07 | evidence — UncertaintyContext 변경 시 EvidenceBundle |
| M-11 | drift check — UncertaintyContext 영향 |
| M-14 | trust refresh — UncertaintyContext 참조 |
| M-17 | spec lock check — UncertaintyContext U3 잠금 해제 차단 |

### Invariant Lens 반영

본 Sprint는 행위적 불변량 §4.3(리스크/보안 선행), §4.4(VALIDATING 전체 통과)를 행사한다.
UncertaintyContext가 Invariant Lens(DOC-L2-INVARIANT-LENS §6)의 U0~U3 정의를 준수하여 상태 분리됨을 확인한다.
Lens 입력 정규화가 Forge→Lens→Council→Judge 파이프라인(§2)의 일관성을 보장함을 확인한다.

## 6. 종료 기준

- UncertaintyContext가 WorkStateContext와 독립적으로 관리됨 확인
- TransitionGuard에서 UncertaintyContext 참조 작동 확인
- Lens 입력 정규화 (WorkState, Uncertainty, SecurityState) 3-tuple 확인
- Mandatory Enforcement Map의 UncertaintyContext 연동 확인
- Spec Lock에서 U3 잠금 해제 차단 확인
- 모든 UncertaintyContext 변경에서 EvidenceBundle 생산 확인

## 7. 의존관계

선행: Sprint 3a
후행: Sprint 5
