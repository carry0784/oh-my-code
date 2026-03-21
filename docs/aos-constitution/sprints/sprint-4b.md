---
document_id: DOC-L3-SPRINT-4B
title: "Sprint 4b — Active Gate (G-16~G-27)"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 4b 구현 과제]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, G-xx Gate 정의, Invariant Lens 정의]
---

# Sprint 4b — Active Gate (G-16~G-27)

## 1. Sprint 목표

v4 기준 Active Gate G-16~G-27의 ACTIVE 모드 작동을 검증한다.
ACTIVE 모드에서 실패 시 실행이 차단됨을 확인한다.
각 Gate의 Mandatory 연결과 VALIDATING 체크리스트 매핑을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| Gate Registry | G-16~G-27 Active Gates | B2 (정책은 B1) |

소스: gate_registry.py (ACTIVE 영역)

## 3. 구현 과제

Gate 정의 및 Mandatory 매핑: DOC-L2-EXT-API-GOV §4.3, §5
VALIDATING 체크리스트 매핑: DOC-L2-EXT-API-GOV §3

1. G-16~G-27 각 Gate의 Mandatory 및 VALIDATING 체크 연결이 DOC-L2-EXT-API-GOV §5 매핑과 일치함을 확인
2. OQ 기준 미정의 Gate(G-19, G-23, G-24, G-25)의 평가 로직이 미정의 상태를 올바르게 처리함을 확인
3. G-25(Completion Gate)의 VERIFY 시점 연결 확인 (VALIDATING이 아닌 별도 시점)
4. G-27(Research Gate)의 PLANNING 선행 조건 연결 확인
5. 모든 Gate의 phase = ACTIVE 확인 (B1 비준 후)
6. ACTIVE 모드에서 FAIL 시 실행 차단 확인

## 4. Gate 활성화

G-16~G-27을 ACTIVE 모드로 활성화한다.
SHADOW→ACTIVE 전환은 B1 비준이 완료된 Gate에 한해 수행한다.
G-28~G-30은 예약이며 본 Sprint 범위 밖이다.

## 5. Mandatory Items

Mandatory 정의 및 상세: DOC-L2-EXT-API-GOV §6

| Mandatory | 관련 Gate |
|-----------|-----------|
| M-08 | G-22 Budget Gate |
| M-09 | G-16 Compliance Gate |
| M-10 | G-18 Provenance Gate |
| M-11 | G-19 Drift Gate |
| M-12 | G-20 Conflict Gate |
| M-13 | G-21 Pattern Gate |
| M-14 | G-23 Trust Gate |
| M-15 | G-24 Loop Gate |
| M-16 | G-25 Completion Gate |
| M-17 | G-26 Spec Lock Gate |
| M-18 | G-27 Research Gate |

### Invariant Lens 반영

본 Sprint는 행위적 불변량 §4.4(VALIDATING 전체 통과)를 행사한다.
Active Gate FAIL은 실행을 차단하며, 이는 Lens 단계의 강제 검증에 해당한다.

## 6. 종료 기준

- G-16~G-27 ACTIVE 모드 평가 전체 작동
- 각 Gate의 Mandatory 및 VALIDATING 체크 매핑 확인
- ACTIVE 실패 시 실행 차단 확인

## 7. 의존관계

선행: Sprint 4a
후행: Sprint 6-gate
