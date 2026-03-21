---
document_id: DOC-L3-SPRINT-6-GATE
title: "Sprint 6-gate — 개선 자격 축"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 6-gate 구현 과제]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, G-xx Gate 정의, Invariant Lens 정의]
---

# Sprint 6-gate — 개선 자격 축

## 1. Sprint 목표

Self-Improvement Loop 진입을 위한 Gate 자격 조건을 검증한다.
개선 시도가 B1 교리를 준수하며, 적격 조건을 충족할 때만 허용됨을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| L9 | Self-Improvement Engine | B2 + B1 교리 준수 |
| Gate | 관련 Gate 자격 조건 | B2 |

소스: gate_registry.py, mandatory_enforcement_map.md

## 3. 구현 과제

1. Self-Improvement Loop 진입 전 모든 필수 Mandatory 통과 확인
2. 개선 실험이 Sandbox에서만 실행됨을 확인 (L9 격리)
3. 개선 결과가 Forge→Lens→Council→Judge 파이프라인을 통과해야 반영됨을 확인
4. B1 교리 위반 개선안은 Judge 단계에서 거부됨을 확인

## 4. Gate 활성화

Self-Improvement 관련 Gate 자격 조건을 ACTIVE로 확인한다.

## 5. Mandatory Items

Mandatory 정의 및 상세: DOC-L2-EXT-API-GOV §6

| Mandatory | 관련 |
|-----------|------|
| M-09 | compliance check — 개선 전 준수율 확인 |

### Invariant Lens 반영

본 Sprint는 행위적 불변량 §4.6(동시 쓰기 직렬화)을 행사한다.
Forge→Lens→Council→Judge(DOC-L2-INVARIANT-LENS §2)에서 개선안이 Lens를 통과해야 함을 확인한다.
개선은 D-005(B1 immutability) 위반 없이 수행되어야 한다.

## 6. 종료 기준

- Self-Improvement Gate 자격 조건 검증 완료
- Sandbox 격리 확인
- Forge→Lens→Council→Judge 파이프라인 통과 확인

## 7. 의존관계

선행: Sprint 4b
후행: Sprint 6
