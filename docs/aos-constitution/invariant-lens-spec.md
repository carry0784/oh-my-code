---
document_id: DOC-L2-INVARIANT-LENS
title: "Invariant Lens 정책 스펙"
level: L2
authority_mode: POLICY
authority_scope: policy_rules_only
parent: DOC-L1-CONSTITUTION
version: "1.0.0"
last_updated: "2026-03-21"
defines: [Invariant Lens, Forge-Lens-Council-Judge 파이프라인, U0-U3, C0-C3, E0-E4, 구조적 불변량, 행위적 불변량, 정량적 경계 정책, Sprint Invariant Lens 의무]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum 값, 코드, 스키마, 필드 타입, 수치 임계값, 구현 절차, 테스트]
---

# Invariant Lens 정책 스펙

> 범위 고정문: 본 문서는 정책 수준의 불변량 렌즈를 정의한다. 허용 범위는 4계층 역할, U·C·E 상태, 전이 원칙, 기존 구조 결합, Sprint 매핑, 운영 규칙, 한계이다. 코드, 스키마, 필드 타입, 수치 임계값, 구현 절차, 테스트는 본 문서의 범위 밖이다.

## 1. 목적

Invariant Lens는 모든 Sprint 구현이 헌법 불변량과 교리를 위반하지 않는지 검증하기 위한 정책 프레임워크이다.
Sprint 문서는 본 문서의 불변량 렌즈를 통과해야 하며, 각 Sprint는 어떤 불변량이 행사되는지를 명시해야 한다.
본 문서는 "무엇이 유지되어야 하는가"를 정의하며, "어떻게 구현할 것인가"는 Sprint 문서와 소스 코드의 영역이다.

## 2. Forge → Lens → Council → Judge 파이프라인

Invariant Lens는 4계층 파이프라인을 통해 작동한다:

**Forge** — 변경 제안을 생성하는 단계. Sprint 구현, 규칙 변경, 자가개선 결과가 여기서 생산된다.
**Lens** — 변경 제안을 불변량 렌즈에 비추어 검사하는 단계. 구조적, 행위적, 정량적 불변량을 확인한다.
**Council** — Lens 검사 결과를 종합하여 승인/보류/거부 판정을 내리는 단계. U·C·E 상태를 기반으로 판단한다.
**Judge** — 최종 헌법 적합성을 판정하는 단계. Constitutional Judge는 D-001~D-010 준수를 최종 확인한다.

Forge에서 생산된 변경은 반드시 Lens → Council → Judge를 순서대로 통과해야 한다.
Judge가 거부하면 변경은 폐기되며, EvidenceBundle에 거부 사유가 기록된다.

## 3. 구조적 불변량

3.1 거버넌스 계층 불변: B1 > B2 > A 계층 구조는 변경할 수 없다.
3.2 교리 읽기 전용: B2와 A는 B1 교리를 읽을 수만 있고 수정할 수 없다.
3.3 LOCKDOWN 해제 제한: LOCKDOWN 해제는 Human(L27)만 가능하다(D-004).
3.4 증거 의무: 모든 상태 전이는 EvidenceBundle을 생산해야 한다(D-002).
3.5 TCL 전용 실행: 모든 외부 실행은 TCL을 통해야 한다(D-001).
3.6 출처 의무: 모든 Rule Ledger 쓰기는 RuleProvenance를 포함해야 한다(D-003).

## 4. 행위적 불변량

4.1 의도 선행: 실행 전 의도 명확화가 반드시 선행되어야 한다(D-007).
4.2 스펙 쌍 선행: 계획 전 Spec Twin이 생성되어야 한다(M-02).
4.3 리스크/보안 선행: VALIDATING 진입 전 리스크 평가와 보안 검사가 완료되어야 한다(D-008).
4.4 VALIDATING 전체 통과: 10개 체크가 모두 PASS여야 RUNNING으로 전이할 수 있다.
4.5 복구 상한: Recovery Loop는 사고당 최대 3회 복구를 시도할 수 있다(D-006).
4.6 동시 쓰기 직렬화: Rule Ledger 동시 쓰기는 RuleLedgerLock으로 직렬화해야 한다(D-010).

## 5. 정량적 경계 정책

본 절은 정량적 경계의 정책적 의미만 정의한다. 구체적 수치 임계값은 Sprint 구현과 운영 데이터를 통해 확정한다.

5.1 Intent Drift 정책: Drift score가 경계를 초과하면 실행을 보류하고 검토를 요구한다. 경계의 의미는 "원래 의도에서 실질적으로 이탈했음"이다.
5.2 Trust Decay 정책: Trust는 이벤트 기반 및 배경 감소로 변동하며, 경계 이하로 하락하면 격리 또는 차단한다. 경계의 의미는 "신뢰할 수 없는 상태"이다.
5.3 Loop Count 정책: 각 루프는 사고/일/주 단위 실행 상한을 가진다. 상한의 의미는 "무한 루프 방지"이다.
5.4 Completion Score 정책: 완성도 점수가 경계 이상이어야 VERIFY를 통과한다. 경계의 의미는 "충분히 검증됨"이다.
5.5 Budget 경계 정책: 잔여 예산이 실행 예상 비용 이상이어야 실행이 허용된다. 경계의 의미는 "비용 초과 방지"이다.

## 6. Uncertainty 상태 (U0 ~ U3)

Uncertainty는 시스템이 현재 상황에 대해 가진 불확실성 수준을 나타낸다.

- **U0 — Certain**: 불확실성 없음. 모든 판단 기준이 충족됨.
- **U1 — Low Uncertainty**: 경미한 불확실성. 추가 정보 수집 권고.
- **U2 — High Uncertainty**: 높은 불확실성. 실행 보류 및 검토 필요.
- **U3 — Maximum Uncertainty**: 최대 불확실성. 외부 실행 시 즉시 LOCKDOWN 대상.

> U 1줄 요약: 불확실성은 U0(확실)에서 U3(최대)까지 4단계이며, U3+outbound 조합은 LOCKDOWN을 유발한다.

## 7. Confidence 상태 (C0 ~ C3)

Confidence는 시스템 판단의 신뢰도 수준을 나타낸다.

- **C0 — No Confidence**: 신뢰 없음. 판단 근거 부재.
- **C1 — Low Confidence**: 낮은 신뢰. 제한적 근거만 존재.
- **C2 — Moderate Confidence**: 중간 신뢰. 대부분의 근거가 충족됨.
- **C3 — High Confidence**: 높은 신뢰. 모든 판단 근거가 충족됨.

> C 1줄 요약: 신뢰도는 C0(없음)에서 C3(높음)까지 4단계이며, Council 판정의 기반이 된다.

## 8. Evidence 상태 (E0 ~ E4)

Evidence는 판단을 뒷받침하는 증거의 완전성 수준을 나타낸다.

- **E0 — No Evidence**: 증거 없음.
- **E1 — Partial Evidence**: 부분적 증거. 일부 EvidenceBundle만 존재.
- **E2 — Sufficient Evidence**: 충분한 증거. 판단에 필요한 최소 증거 확보.
- **E3 — Complete Evidence**: 완전한 증거. 모든 관련 EvidenceBundle 확보.
- **E4 — Verified Evidence**: 검증된 증거. 완전한 증거 + 교차 검증 완료.

> E 1줄 요약: 증거 완전성은 E0(없음)에서 E4(검증 완료)까지 5단계이며, Judge 판정의 입력이 된다.

## 9. Sprint Invariant Lens 의무

모든 Sprint 문서(DOC-L3-SPRINT-*)는 다음 의무를 준수해야 한다:

1. `### Invariant Lens 반영` 소절을 3~5줄로 포함해야 한다.
2. 해당 소절에서 본 문서의 어떤 불변량(§3~§5)이 행사되는지 명시해야 한다.
3. Sprint는 불변량을 재정의하거나 새 불변량을 도입할 수 없다.
4. Sprint가 U·C·E 상태에 영향을 미치는 경우, 영향 범위를 소절에 명시해야 한다.

해당 Sprint: sprint-3a, sprint-3b1, sprint-3b2, sprint-5, sprint-6-gate, sprint-6, operator-runbook

## 10. 범위 고정문

본 문서의 범위는 다음으로 한정된다:
- 4계층 역할 정의 (Forge/Lens/Council/Judge)
- U·C·E 상태 정의 및 전이 원칙
- 구조적/행위적/정량적 불변량의 정책적 선언
- 기존 헌법 구조와의 결합 방식
- Sprint 매핑 의무
- 운영 규칙 및 한계

다음은 본 문서의 범위 밖이다:
- 코드 구현
- 데이터 스키마 또는 필드 타입 정의
- 수치 임계값 확정
- 구현 절차 또는 알고리즘
- 테스트 케이스 또는 검증 코드
