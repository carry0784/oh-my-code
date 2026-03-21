---
document_id: DOC-L3-SPRINT-4A
title: "Sprint 4a — Shadow Gate (G-01~G-08)"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 4a 구현 과제]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, G-xx Gate 정의, Invariant Lens 정의]
---

# Sprint 4a — Shadow Gate (G-01~G-08)

## 1. Sprint 목표

Phase 4 Shadow Validation Gate G-01~G-08의 SHADOW 모드 작동을 검증한다.
SHADOW 모드에서 실패는 기록만 되고 실행을 차단하지 않음을 확인한다.
각 Gate의 evaluate 함수가 GateVerdict를 정확히 반환함을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| Gate Registry | G-01~G-08 Shadow Gates | B2 (정책은 B1) |

소스: gate_registry.py (SHADOW 영역)

## 3. 구현 과제

Gate 정의 및 Mandatory 매핑: DOC-L2-EXT-API-GOV §4.2, §5

1. G-01~G-08 각 Gate의 evaluate 함수가 GateVerdict를 정확히 반환함을 확인
2. G-02~G-05의 Mandatory 연결이 DOC-L2-EXT-API-GOV §5 매핑과 일치함을 확인
3. G-06~G-08의 독립 기준(신호 품질, 포지션 크기, 리스크 필터) 검증
4. 모든 Gate의 phase = SHADOW 확인
5. SHADOW 모드에서 FAIL 시 로그만 기록되고 실행 차단 없음 확인

## 4. Gate 활성화

G-01~G-08을 SHADOW 모드로 활성화한다.
G-09~G-15는 Phase 4 확장용 예약이며 본 Sprint 범위 밖이다.

## 5. Mandatory Items

Mandatory 정의 및 상세: DOC-L2-EXT-API-GOV §6

| Mandatory | 관련 Gate |
|-----------|-----------|
| M-03 | G-03 Risk Control |
| M-04, M-09 | G-04 Constitution Compliance |
| M-05, M-06 | G-02 State Recovery |
| M-07 | G-05 Audit Completeness |

### Invariant Lens 반영

본 Sprint는 구조적 불변량 §3.4(증거 의무)와 행위적 불변량 §4.3(리스크/보안 선행)을 행사한다.
Shadow Gate는 Lens 단계의 검증 도구이며, SHADOW→ACTIVE 전환에는 B1 비준이 필요하다.

## 6. 종료 기준

- G-01~G-08 SHADOW 모드 평가 전체 작동
- 각 Gate의 Mandatory 연결 확인
- SHADOW 실패 시 기록만, 차단 없음 확인

## 7. 의존관계

선행: Sprint 2
후행: Sprint 4b
