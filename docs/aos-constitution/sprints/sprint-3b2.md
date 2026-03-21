---
document_id: DOC-L3-SPRINT-3B2
title: "Sprint 3b2 — ForbiddenLedger + Forge→Lens→Council→Judge"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 3b2 구현 과제]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, Invariant Lens 정의, Forge-Lens-Council-Judge 정의]
---

# Sprint 3b2 — ForbiddenLedger + Forge→Lens→Council→Judge

## 1. Sprint 목표

ForbiddenLedger의 금지행위 등록·검사·차단 메커니즘을 검증한다.
Forge→Lens→Council→Judge 파이프라인에서 ForbiddenLedger가 Lens 단계의 최우선 검사 대상임을 확인한다.
LOCKDOWN severity 위반 시 즉시 시스템 잠금이 작동함을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| L3 | Security & Isolation | B1 |
| Ledger | ForbiddenLedger | B1 |

소스: forbidden_ledger.py

## 3. 구현 과제

1. ForbiddenAction 등록: action_id(FA-xxx), severity(LOCKDOWN/BLOCKED), pattern, registered_by 필드 확인
2. ForbiddenLedger.check_and_enforce()가 패턴 매칭으로 금지 행위를 감지함을 확인
3. LOCKDOWN severity 위반 시 SecurityStateContext.escalate(LOCKDOWN) 호출 확인
4. BLOCKED severity 위반 시 해당 작업 차단 + BLOCKED 상태 전이 확인
5. 위반 시 EvidenceBundle(ForbiddenViolation) 생산 확인
6. VALIDATING [1] FORBIDDEN_CHECK에서 최우선 검사되며, 위반 시 나머지 체크 생략 확인
7. B1Constitution.check_forbidden_action()이 ForbiddenLedger에 위임함을 확인
8. Forge→Lens 단계에서 ForbiddenLedger 검사가 Lens의 첫 번째 필터임을 확인

## 4. Gate 활성화

본 Sprint에서 직접 활성화하는 Gate는 없다.
VALIDATING [1] FORBIDDEN_CHECK가 모든 Gate 평가에 선행하는 구조를 확인한다.

## 5. Mandatory Items

| Mandatory | 관련 구현 과제 |
|-----------|---------------|
| M-07 | evidence — 위반 시 EvidenceBundle 생산 |

### Invariant Lens 반영

본 Sprint는 구조적 불변량 §3.4(증거 의무)를 행사한다.
Forge→Lens→Council→Judge 파이프라인(DOC-L2-INVARIANT-LENS §2)에서 Lens 단계의 ForbiddenLedger 검사를 확인한다.
D-009(Forbidden action zero tolerance)의 구현 적합성을 검증한다.

## 6. 종료 기준

- ForbiddenAction 등록·감지·차단 전체 경로 검증 완료
- LOCKDOWN severity → 즉시 LOCKDOWN 작동
- VALIDATING [1]에서 최우선 검사 확인
- 모든 위반에서 EvidenceBundle 생산 확인

## 7. 의존관계

선행: Sprint 2
후행: Sprint 5
