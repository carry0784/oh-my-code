---
document_id: DOC-L3-SPRINT-3A
title: "Sprint 3a — Judgement 축"
level: L3
authority_mode: SPRINT
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Sprint 3a 구현 과제, Judgement 축 검증 범위]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, Invariant Lens 정의, U-class 정의, E-class 정의, Constitutional Judge 정의]
---

# Sprint 3a — Judgement 축

> Scope Token: 본 Sprint는 Judgement 축의 검증에 한정한다. U-class/E-class 상태는 DOC-L2-INVARIANT-LENS에서 정의하며, 본 문서는 해당 정의를 참조만 한다.

> 경고: 본 Sprint는 고밀도 Sprint이다. 상위 문서의 정의를 재정의하거나 새 이론을 도입하지 않는다.

## 1. Sprint 목표

Judgement 축의 핵심 메커니즘을 검증한다.
B1Constitution.enforce()가 교리 준수를 판정하고, 위반에 따른 에스컬레이션을 수행하는 전체 경로를 확인한다.
DoctrineRegistry.check_compliance()가 context 기반으로 교리 위반을 감지하는 메커니즘을 검증한다.
U-class(Uncertainty) 상태에 따른 판정 우선순위와 Constitutional Judge의 최종 판정 역할을 확인한다.

## 2. 범위: 대상 레이어

| Layer | 이름 | 거버넌스 |
|-------|------|----------|
| L2 | Doctrine & Policy | B1 |
| L13 | Compliance Engine | B2 |

소스: b1_constitution.py enforce(), doctrine.py check_compliance()

## 3. 구현 과제

### 3.1 enforce() 판정 경로

1. B1Constitution.enforce(context)가 DoctrineRegistry.check_compliance(context)를 호출함을 확인
2. 반환된 DoctrineViolation 목록에 대해 severity별 에스컬레이션을 수행함을 확인:
   - CONSTITUTIONAL → SecurityStateEnum.LOCKDOWN
   - CRITICAL → SecurityStateEnum.QUARANTINED
   - ADVISORY → 경고만, 에스컬레이션 없음
3. 각 위반에 대해 EvidenceBundle이 생산됨을 확인
4. 위반이 없으면 빈 목록을 반환하고 에스컬레이션이 발생하지 않음을 확인

### 3.2 check_compliance() 교리 평가

1. 10개 핵심 교리(D-001~D-010) 각각의 constraint 평가가 정확함을 확인
2. RATIFIED 상태가 아닌 교리는 검사에서 제외됨을 확인
3. context dict의 키값이 constraint 표현식과 정확히 매핑됨을 확인
4. 알 수 없는 constraint는 fail-open(True 반환)으로 처리됨을 확인

### 3.3 U-class 판정 우선순위

UncertaintyContext 상태에 따른 판정 우선순위:
- U0(Certain): 정상 판정 — 모든 교리 검사를 수행하고 결과에 따라 처리
- U1(Low Uncertainty): 추가 정보 수집 권고 — 판정은 수행하되 검토 플래그 설정
- U2(High Uncertainty): 실행 보류 — 판정 결과와 무관하게 실행을 보류하고 review 상태로 전환
- U3(Maximum Uncertainty): 외부 실행 금지 — outbound 요청 시 즉시 LOCKDOWN 대상

dominant scenario 판정 기준:
- 복수의 교리 위반이 동시 감지된 경우, severity가 가장 높은 위반이 dominant scenario가 된다
- dominant scenario에 따라 에스컬레이션 수준이 결정된다
- 동일 severity의 복수 위반은 모두 기록되며, 첫 번째 감지된 위반이 에스컬레이션을 트리거한다

### 3.4 Constitutional Judge 역할

Constitutional Judge는 Forge→Lens→Council→Judge 파이프라인(DOC-L2-INVARIANT-LENS §2)의 최종 단계이다:
- Judge는 D-001~D-010 준수를 최종 확인한다
- Council에서 승인된 변경이라도 Judge가 교리 위반을 감지하면 거부한다
- Judge 거부 시 변경은 폐기되며, 거부 사유가 EvidenceBundle에 기록된다
- Judge는 새로운 교리를 생성하지 않으며, 기존 교리의 준수 여부만 판정한다

### 3.5 review/hold/forbidden 우선순위

판정 결과에 따른 행동 우선순위:
1. **forbidden** (최고 우선순위): ForbiddenLedger 위반 → 즉시 차단, VALIDATING [1]에서 처리
2. **hold**: CONSTITUTIONAL/CRITICAL 교리 위반 → 에스컬레이션 + 실행 중지
3. **review**: U2 상태 또는 ADVISORY 위반 → 실행 보류 + 검토 요청

이 우선순위는 VALIDATING 체크리스트의 [1] FORBIDDEN_CHECK가 최우선인 이유를 반영한다.

## 4. Gate 활성화

본 Sprint에서 직접 활성화하는 Gate는 없다.
G-04(Constitution Compliance)와 G-16(Compliance Gate)의 평가 기반을 마련한다.

## 5. Mandatory Items

| Mandatory | 관련 구현 과제 |
|-----------|---------------|
| M-04 | security check — enforce() 기반 보안 판정 |
| M-07 | evidence — 모든 위반에 대한 EvidenceBundle |
| M-09 | compliance check — check_compliance() 준수율 |

### Invariant Lens 반영

본 Sprint는 구조적 불변량 §3.1(거버넌스 계층 불변), §3.4(증거 의무)를 행사한다.
행위적 불변량 §4.4(VALIDATING 전체 통과)에서 Judgement 축이 핵심 검증 단계임을 확인한다.
Constitutional Judge(DOC-L2-INVARIANT-LENS §2)의 최종 판정 역할을 검증한다.
U-class 상태(DOC-L2-INVARIANT-LENS §6)에 따른 판정 우선순위를 준수한다.

## 6. 종료 기준

- enforce() → check_compliance() 전체 경로 검증 완료
- CONSTITUTIONAL → LOCKDOWN, CRITICAL → QUARANTINED 에스컬레이션 확인
- U0~U3 판정 우선순위 검증 완료
- dominant scenario 판정 작동 확인
- Constitutional Judge 거부 시 변경 폐기 확인
- forbidden > hold > review 우선순위 확인
- 모든 위반에서 EvidenceBundle 생산 확인

## 7. 의존관계

선행: Sprint 2
후행: Sprint 3b1
