---
document_id: DOC-L2-SPRINT-PLAN
title: "Sprint 계획 및 순서"
level: L2
authority_mode: POLICY
parent: DOC-L1-CONSTITUTION
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 순서, Sprint 의존관계, Sprint 완료 기준]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS, DOC-L3-SPRINT-1, DOC-L3-SPRINT-2, DOC-L3-SPRINT-3A, DOC-L3-SPRINT-3B1, DOC-L3-SPRINT-3B2, DOC-L3-SPRINT-4A, DOC-L3-SPRINT-4B, DOC-L3-SPRINT-5, DOC-L3-SPRINT-6-GATE, DOC-L3-SPRINT-6, DOC-L3-SPRINT-7A]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, M-xx, G-xx, Invariant Lens 정의]
---

# Sprint 계획 및 순서

## 1. Sprint 체계 개요

본 문서는 K-Dexter AOS v5.4 구현을 위한 Sprint 순서, 의존관계, 완료 기준을 정의한다.
각 Sprint는 DOC-L2-INVARIANT-LENS의 불변량 렌즈 검사를 준수해야 한다.
Sprint 문서는 새 이론을 도입할 수 없으며, 상위 문서(DOC-L1-CONSTITUTION, L2 정책)의 정의를 재정의할 수 없다.

## 2. 본선 Sprint 일람 (11개)

| Sprint | ID | 핵심 축 | 대상 레이어 |
|--------|-----|---------|-------------|
| Sprint 1 | DOC-L3-SPRINT-1 | B1/Doctrine/Security 기초 | L1, L2, L3 |
| Sprint 2 | DOC-L3-SPRINT-2 | WorkState 21상태 머신 | Work State Machine |
| Sprint 3a | DOC-L3-SPRINT-3A | Judgement 축 (U-class/E-class) | L2, L13 |
| Sprint 3b1 | DOC-L3-SPRINT-3B1 | 상태 분리 축 (UncertaintyContext) | Work State, L22 |
| Sprint 3b2 | DOC-L3-SPRINT-3B2 | ForbiddenLedger + Forge→Lens→Council→Judge | L3, Ledger |
| Sprint 4a | DOC-L3-SPRINT-4A | Shadow Gate (G-01~G-08) | Gate Registry |
| Sprint 4b | DOC-L3-SPRINT-4B | Active Gate (G-16~G-27) | Gate Registry |
| Sprint 5 | DOC-L3-SPRINT-5 | 차단 축 (U3+outbound→LOCKDOWN) | Recovery, Security |
| Sprint 6-gate | DOC-L3-SPRINT-6-GATE | 개선 자격 축 | L9, Gate |
| Sprint 6 | DOC-L3-SPRINT-6 | 자가개선 제한 축 | L9, Self-Improvement |
| Sprint 7a | DOC-L3-SPRINT-7A | 확장 플레이스홀더 | 미정 |

## 3. 조건부 Sprint (7개)

조건부 Sprint는 DOC-L4-COND-* 잠금 문서로 관리된다.
해제 조건 충족 시 B1 비준을 거쳐 활성화된다.

| 조건부 문서 | unlock_reason_class | 활성화 전제 |
|------------|---------------------|-------------|
| cond-multi-exchange | SCALE_EXPANSION | 다중 거래소 운영 필요 시 |
| cond-live-trading | PHASE_TRANSITION | 실거래 전환 시 |
| cond-cross-strategy | STRATEGY_EVOLUTION | 교차 전략 필요 시 |
| cond-external-data | DATA_EXPANSION | 외부 데이터 소스 추가 시 |
| cond-model-upgrade | MODEL_EVOLUTION | 모델 업그레이드 시 |
| cond-regulatory | COMPLIANCE_EXPANSION | 규제 대응 필요 시 |
| cond-disaster-recovery | INFRASTRUCTURE_EXPANSION | 재해 복구 체계 구축 시 |

## 4. 의존관계도

Sprint 1 ──→ Sprint 2 ──→ Sprint 3a ──→ Sprint 3b1 ──→ Sprint 5
                  │                                        ↑
                  └──→ Sprint 3b2 ─────────────────────────┘
                  │
                  └──→ Sprint 4a ──→ Sprint 4b ──→ Sprint 6-gate ──→ Sprint 6
                                                                       │
                                                                       └──→ Sprint 7a

Sprint 1은 모든 후속 Sprint의 전제이다.
Sprint 3a, 3b1, 5는 순차 실행이 필수이다 (고밀도 축).
Sprint 4a → 4b → 6-gate → 6은 Gate 활성화 순서를 따른다.

## 5. Sprint 실행 규칙

- 각 Sprint 문서는 DOC-L2-SPRINT-PLAN을 parent로 참조한다.
- 각 Sprint는 `### Invariant Lens 반영` 소절(3~5줄)을 필수 포함한다.
- Sprint 문서는 상위 문서의 정의를 재정의하거나 새 이론을 도입할 수 없다.
- Sprint 내에서 Gate를 SHADOW → ACTIVE로 전환하려면 B1 비준이 필요하다.

## 6. Sprint 완료 기준

각 Sprint는 다음 조건을 모두 충족해야 완료로 인정된다:

1. Sprint 목표에 명시된 구현 과제가 모두 완료
2. 관련 Gate 평가가 통과 (해당 시)
3. Invariant Lens 반영 소절에 명시된 불변량이 유지됨을 확인
4. EvidenceBundle이 Sprint 실행 과정에서 생산됨 (D-002)
5. 상위 문서 교리 위반 없음 확인

## 7. DOC-L2-INVARIANT-LENS 인덱스

모든 Sprint의 Invariant Lens 반영 의무는 DOC-L2-INVARIANT-LENS §9에서 정의한다.
