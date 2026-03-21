---
document_id: DOC-L3-SPRINT-1
title: "Sprint 1 — B1/Doctrine/Security 기초"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 1 구현 과제, Sprint 1 Gate 활성화]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, M-xx, G-xx, Invariant Lens 정의]
---

# Sprint 1 — B1/Doctrine/Security 기초

## 1. Sprint 목표

B1 Constitutional Layer의 기초 구현을 검증한다.
DoctrineRegistry의 10개 핵심 교리(D-001~D-010) 비준 상태를 확인한다.
SecurityStateContext의 4단계 에스컬레이션 경로를 검증한다.
ConstitutionalInvariant CI-001, CI-002의 enforce() 작동을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| L1 | Human Decision | B1 |
| L2 | Doctrine & Policy | B1 |
| L3 | Security & Isolation | B1 |

소스: b1_constitution.py, doctrine.py, security_state.py

## 3. 구현 과제

1. DoctrineRegistry 초기화 시 D-001~D-010이 RATIFIED 상태로 로드됨을 확인
2. B1Constitution.enforce()가 CONSTITUTIONAL severity 위반 시 LOCKDOWN 에스컬레이션을 수행함을 확인
3. B1Constitution.enforce()가 CRITICAL severity 위반 시 QUARANTINED 에스컬레이션을 수행함을 확인
4. suspend_doctrine()이 핵심 교리(D-001~D-010)에 대해 ConstitutionalViolationError를 발생시킴을 확인
5. release_lockdown()이 L27_HUMAN 외의 authorized_by에 대해 ConstitutionalViolationError를 발생시킴을 확인
6. SecurityStateContext.escalate()가 단방향 에스컬레이션을 준수함을 확인
7. SecurityStateContext.de_escalate()에서 LOCKDOWN → any가 HUMAN_OVERRIDE를 요구함을 확인
8. check_invariants()가 CI-001, CI-002를 검증함을 확인

## 4. Gate 활성화

본 Sprint에서 직접 활성화하는 Gate는 없다.
G-04(Constitution Compliance)의 SHADOW 단계 검증 기반을 마련한다.

## 5. Mandatory Items

Mandatory 정의 및 상세: DOC-L2-EXT-API-GOV §6

| Mandatory | 관련 구현 과제 |
|-----------|---------------|
| M-04 | security check — L3 보안 정책 enforce() 기반 |
| M-07 | evidence — 모든 enforce() 호출 시 EvidenceBundle 생산 확인 |

### Invariant Lens 반영

본 Sprint는 구조적 불변량 §3.1(거버넌스 계층 불변), §3.2(교리 읽기 전용), §3.3(LOCKDOWN 해제 제한), §3.4(증거 의무)를 행사한다.
CI-001, CI-002 불변량의 enforce() 통과를 확인하여 Invariant Lens 적합성을 검증한다.

## 6. 종료 기준

- 핵심 교리 D-001~D-010 전체 RATIFIED 확인
- enforce()에서 CONSTITUTIONAL → LOCKDOWN, CRITICAL → QUARANTINED 에스컬레이션 작동
- check_invariants() 위반 0건
- 모든 EvidenceBundle 생산 확인

## 7. 의존관계

선행: 없음 (최초 Sprint)
후행: Sprint 2, Sprint 3b2, Sprint 4a
