---
document_id: DOC-L3-SPRINT-6
title: "Sprint 6 — 자가개선 제한 축"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 6 구현 과제]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, Invariant Lens 정의]
---

# Sprint 6 — 자가개선 제한 축

## 1. Sprint 목표

Self-Improvement Loop의 실행 제한과 안전 장치를 검증한다.
자가개선이 B1 교리 범위 내에서만 작동하며, 헌법 불변량을 위반하지 않음을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| L9 | Self-Improvement Engine | B2 + B1 교리 준수 |

소스: self_improvement_loop.py

## 3. 구현 과제

1. Self-Improvement Loop 실행 상한 확인 (루프 카운트 상한 정책)
2. 개선 실험 결과가 Sandbox를 벗어나지 않음을 확인
3. 개선이 B1 교리(D-001~D-010)를 수정하려는 시도를 차단함을 확인
4. 개선 결과 반영 시 EvidenceBundle 생산 확인

## 4. Gate 활성화

없음. Sprint 6-gate에서 활성화한 자격 조건을 활용한다.

## 5. Mandatory Items

| Mandatory | 관련 |
|-----------|------|
| M-07 | evidence — 개선 과정 EvidenceBundle |
| M-09 | compliance — 개선 후 준수율 확인 |

### Invariant Lens 반영

본 Sprint는 구조적 불변량 §3.2(교리 읽기 전용)와 정량적 경계 정책 §5.3(루프 카운트 정책)을 행사한다.
D-005(B1 immutability)에 의해 자가개선이 B1 교리를 수정할 수 없음을 확인한다.

## 6. 종료 기준

- Self-Improvement Loop 제한 장치 검증 완료
- B1 교리 수정 시도 차단 확인
- Sandbox 격리 유지 확인

## 7. 의존관계

선행: Sprint 6-gate
후행: Sprint 7a
