---
document_id: DOC-L1-CONSTITUTION
title: "K-Dexter AOS 헌법"
level: L1
authority_mode: CONSTITUTIONAL
parent: null
version: "1.0.0"
last_updated: "2026-03-21"
defines: [CI-001, CI-002, D-001, D-002, D-003, D-004, D-005, D-006, D-007, D-008, D-009, D-010, SecurityStateEnum, GovernanceTier, ChangeAuthority, ForbiddenAction]
may_reference: []
may_not_define: [M-xx, G-xx, WorkStateEnum, Sprint]
authority_delegates: [DOC-L2-SPRINT-PLAN, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
---

# K-Dexter AOS 헌법

## 1. 전문

본 문서는 K-Dexter AOS의 최상위 거버넌스 문서이다.
모든 하위 문서는 본 헌법의 정의를 구체화할 수 있으나, 재정의하거나 예외를 생성할 수 없다.
본 헌법에서 정의한 불변량, 교리, 보안 상태, 거버넌스 티어는 런타임에서 변경할 수 없다.
정책 수준의 세부 사항은 authority_delegates에 명시된 L2 문서에 위임한다.

## 2. 거버넌스 티어 (B1 / B2 / A)

| 티어 | 이름 | 역할 | 실행 여부 | Ledger 쓰기 |
|------|------|------|-----------|-------------|
| B1 | Constitutional Foundry | 헌법 제정, 교리 비준, 정당성 검증 | 금지 | Doctrine만 |
| B2 | Build Orchestration | Phase/Sandbox/Release/Rollback 관리 | 간접(빌드) | Rule Ledger(제한적) |
| A | Runtime Execution | 실제 트레이딩 실행, 감사 로그 | 허용 | Evidence Store만 |

변경 권한 원칙:
- B1 귀속 레이어 → B1 비준 없이 변경 불가
- B2 귀속 레이어 → B2 승인 + B1 교리 준수
- A 귀속 레이어 → B2 승인 (B1 교리 읽기 전용)
- 어떤 레이어도 B1 교리를 직접 수정할 수 없다

## 3. B1 귀속 레이어

| Layer | 이름 | 변경 권한 |
|-------|------|-----------|
| L1 | Human Decision | Human Only — 최상위 의사결정, 기계 변경 불가 |
| L2 | Doctrine & Policy | B1 비준 필수 — 교리 생성·비준·활성화 |
| L3 | Security & Isolation | B1 비준 필수 — 보안 정책은 헌법급 |
| L22 | Spec Lock System | B1 비준 필수 — 잠금 해제 승인 권한 |
| L27 | Override Controller | Human Only — LOCKDOWN 해제 권한 유일 보유 |

B2 귀속(21개): L4, L5, L9, L11~L21, L23~L25, L28~L30
A 귀속(5개): L6, L7, L8(+TCL), L10, L26

## 4. 헌법 불변량

**CI-001 — Core doctrine presence**
최소 10개의 핵심 교리(D-001~D-010)가 항상 존재해야 한다.
B1Constitution.enforce()가 매 거버넌스 사이클마다 검증한다.

**CI-002 — Core doctrine ratification**
모든 핵심 교리 D-001~D-010은 RATIFIED 상태여야 한다.
DRAFT, SUSPENDED, RETIRED 상태의 핵심 교리는 헌법 위반이다.

## 5. 핵심 교리 (D-001 ~ D-010)

**D-001 — TCL-only execution** (CONSTITUTIONAL)
모든 거래소 상호작용은 TCL을 통해야 한다. 어떤 레이어도 거래소 API를 직접 호출할 수 없다.
위반 시 즉시 LOCKDOWN. 관련: M-07.

**D-002 — Evidence on every change** (CONSTITUTIONAL)
모든 상태 전이, 게이트 평가, TCL 명령은 EvidenceBundle을 생산해야 한다.
위반 시 즉시 LOCKDOWN. 관련: M-07.

**D-003 — Provenance required** (CONSTITUTIONAL)
모든 Rule Ledger 쓰기는 RuleProvenance를 포함해야 한다. 익명 규칙 변경은 금지된다.
위반 시 즉시 LOCKDOWN. 관련: M-10.

**D-004 — Human-only LOCKDOWN release** (CONSTITUTIONAL)
L27 Override Controller(Human)만 LOCKDOWN을 해제할 수 있다.
자동화된 프로세스는 LOCKDOWN 상태를 해제할 수 없다.

**D-005 — B1 immutability** (CONSTITUTIONAL)
B1 레이어 코드와 교리는 B2 또는 A가 수정할 수 없다.
Human(L1)만 B1 변경을 비준할 수 있다.

**D-006 — Recovery loop ceiling** (CRITICAL)
Recovery Loop는 사고당 최대 3회 복구를 시도할 수 있다.
초과 시 Human Override가 필요하다. 관련: M-14.

**D-007 — Intent clarification mandatory** (CRITICAL)
명시적 의도 명확화 없이 실행을 시작할 수 없다.
CLARIFYING 상태에서 의도가 설정되어야 진행 가능하다. 관련: M-01.

**D-008 — Risk check before execution** (CRITICAL)
리스크 평가(M-03)가 VALIDATING 상태 전에 완료되어야 한다.
리스크 승인 없이 실행할 수 없다. 관련: M-03.

**D-009 — Forbidden action zero tolerance** (CONSTITUTIONAL)
Forbidden Ledger에서 LOCKDOWN 심각도 위반이 감지되면 즉시 시스템 잠금.
예외 없음.

**D-010 — Concurrent write serialization** (CRITICAL)
모든 Rule Ledger 쓰기는 RuleLedgerLock을 통해 직렬화되어야 한다.
복수 루프의 동시 쓰기는 금지된다. 관련: M-10.

## 6. 보안 상태 모델

| 상태 | 의미 | 허용 범위 |
|------|------|-----------|
| NORMAL | 모든 작업 허용 | 전체 실행 |
| RESTRICTED | 실행에 승인 필요 | 제한적 실행 |
| QUARANTINED | 샌드박스만 허용 | 격리 실행 |
| LOCKDOWN | Human Override만 가능 | 자동 작업 전면 금지 |

에스컬레이션은 단방향이다: NORMAL → RESTRICTED → QUARANTINED → LOCKDOWN.
이미 동일하거나 상위 제한 상태에 있으면 에스컬레이션은 no-op이다.

## 7. 에스컬레이션 규칙 및 LOCKDOWN 해제

CONSTITUTIONAL 교리 위반 → 즉시 LOCKDOWN 에스컬레이션.
CRITICAL 교리 위반 → QUARANTINED 에스컬레이션.
Forbidden Ledger LOCKDOWN 심각도 위반 → 즉시 LOCKDOWN.
실패 심각도(Failure Taxonomy)에 따른 에스컬레이션은 DOC-L2-EXT-API-GOV에서 정의한다.

LOCKDOWN 해제: L27 Override Controller(Human)만 가능하다.
authorized_by가 "HUMAN_OVERRIDE"가 아니면 UnauthorizedDeEscalationError가 발생한다.

## 8. 추론 계층 분리 원칙

B1은 "무엇이 허용되는가"를 정의한다.
B2는 "어떻게 구현할 것인가"를 결정한다.
A는 "실행하고 증거를 남긴다."
어떤 하위 계층도 상위 계층의 결정을 무효화할 수 없다.

## 9. 외부 실행 경계면

> 경계선 선언: 본 헌법(DOC-L1-CONSTITUTION)은 외부 실행의 원칙만 선언한다. 외부 실행/API의 구체적 거버넌스 정책은 DOC-L2-EXT-API-GOV에서 정의한다.

모든 외부 실행(거래소 API, 외부 데이터 소스)은 TCL 계층을 통해야 한다(D-001).
외부 실행 결과는 반드시 EvidenceBundle로 기록되어야 한다(D-002).
외부 실행 전 Forbidden Ledger 검사가 선행되어야 한다(D-009).
외부 실행 경계의 세부 정책, 게이트 기준, 실패 분류는 DOC-L2-EXT-API-GOV가 관할한다.
TCL은 A 계층 인프라이며, L8 Execution Cell의 하위 컴포넌트이다.
상위 레이어의 직접 API 호출은 금지된다.

## 10. 권한 위임

본 헌법은 다음 L2 문서에 정책 수준의 권한을 위임한다:

- **DOC-L2-SPRINT-PLAN**: Sprint 계획, 순서, 의존관계, 완료 기준
- **DOC-L2-EXT-API-GOV**: WorkState 정책, Gate Registry, Mandatory 집행점, 실패 분류, 루프 라우팅
- **DOC-L2-INVARIANT-LENS**: 불변량 범주, 구조적/행위적/정량적 경계 정책, Sprint 불변량 렌즈 의무

위임받은 문서는 본 헌법의 교리와 불변량을 준수해야 하며, 재정의할 수 없다.

## 11. 정규 용어 대장 (Canonical Phrase Ledger)

| 정규 용어 | 약어 | 정의 문서 |
|-----------|------|-----------|
| Constitutional Invariant | CI-xxx | DOC-L1-CONSTITUTION |
| Doctrine Article | D-xxx | DOC-L1-CONSTITUTION |
| Security State | SecurityStateEnum | DOC-L1-CONSTITUTION |
| Governance Tier | B1/B2/A | DOC-L1-CONSTITUTION |
| Forbidden Action | FA-xxx | DOC-L1-CONSTITUTION |
| Mandatory Item | M-xx | DOC-L2-EXT-API-GOV |
| Governance Gate | G-xx | DOC-L2-EXT-API-GOV |
| Invariant Lens | — | DOC-L2-INVARIANT-LENS |
