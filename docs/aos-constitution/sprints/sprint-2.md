---
document_id: DOC-L3-SPRINT-2
title: "Sprint 2 — WorkState 22상태 머신"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 2 구현 과제, Sprint 2 Gate 활성화]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, M-xx, G-xx, WorkStateEnum 정의, Invariant Lens 정의]
---

# Sprint 2 — WorkState 22상태 머신

## 1. Sprint 목표

Work State Machine의 22개 상태와 전이 Guard 조건을 검증한다. 상태 분류는 DOC-L2-EXT-API-GOV §2를 따른다.
VALIDATING 내부 10-check 체크리스트의 순서와 실패 처리를 확인한다.
모든 상태 전이에서 EvidenceBundle 생산을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| Work State Machine | 22개 상태 + TransitionGuards | B2 |

소스: work_state.py

## 3. 구현 과제

1. WorkStateEnum 22개 상태 존재 확인 (분류 기준: DOC-L2-EXT-API-GOV §2)
2. 정상 경로 전이 순서 검증: DRAFT → CLARIFYING → SPEC_READY → PLANNING → VALIDATING → RUNNING → EVALUATING → APPROVAL_PENDING → EXECUTING → VERIFY → MONITOR → CLOSED
3. 실패 복구 경로 전이 순서 검증: FAILED → REPLAY → ROOT_CAUSE → REDESIGN → RULE_UPDATE → SANDBOX → IMPROVEMENT → RESUME
4. ValidatingCheck 10개 순서 검증: FORBIDDEN → MANDATORY → COMPLIANCE → DRIFT → CONFLICT → PATTERN → BUDGET → TRUST → LOOP → LOCK
5. TransitionGuard 실패 시 GuardViolationError 발생 확인
6. VALIDATING에서 체크 실패 시 BLOCKED 전이 확인
7. 모든 전이에서 EvidenceBundle 생산 확인 (D-002)

## 4. Gate 활성화

본 Sprint에서 직접 활성화하는 Gate는 없다.
Work State Machine이 Gate 평가를 호출하는 기반 경로를 확인한다.

## 5. Mandatory Items

| Mandatory | 관련 구현 과제 |
|-----------|---------------|
| M-01 | clarify — CLARIFYING 진입 조건 |
| M-02 | spec twin — SPEC_READY 진입 조건 |
| M-07 | evidence — 모든 전이 시 EvidenceBundle |

### Invariant Lens 반영

본 Sprint는 행위적 불변량 §4.1(의도 선행), §4.2(스펙 쌍 선행), §4.4(VALIDATING 전체 통과)를 행사한다.
모든 전이에서 증거 의무(§3.4)를 확인한다.

## 6. 종료 기준

- 22개 상태 전이 경로 전체 검증 완료
- 10-check 순서 및 실패 처리 확인
- Guard 실패 시 GuardViolationError 확인
- 모든 전이에서 EvidenceBundle 생산 확인

## 7. 의존관계

선행: Sprint 1
후행: Sprint 3a, Sprint 3b1, Sprint 3b2
