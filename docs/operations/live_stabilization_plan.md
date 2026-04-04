# Live Stabilization Plan
## 실거래 안정화 계획 v1.0

**Document Path:** `docs/operations/live_stabilization_plan.md`
**Parent Authority:** `Operating Constitution v1.0`
**Status:** ACTIVE
**Scope:** 4단계 실거래 안정화 절차·승격/강등 조건 세부화
**역참조:** 제32조~제40조

---

## 제약 선언

- 본 문서는 상위 헌법의 구현 세부화 문서이다.
- 본 문서는 새 권한을 추가하지 않는다.
- 본 문서는 자동 실행 권한을 부여하지 않는다.
- 본 문서는 상위 헌법과 충돌해서는 안 된다.

---

## 1. 목적 (제32조)

실거래 안정화의 목적은 수익 극대화가 아니라 **운영 신뢰도 축적**이다.
실거래는 증거 기반으로만 승격되어야 하며, 이상 발생 시 즉시 보수적으로 강등되어야 한다.

---

## 2. 원칙 (제33조)

| 원칙 | 설명 |
|------|------|
| **Promotion by Evidence** | 승격은 증거에 의해서만 허용 |
| **Minimal Blast Radius** | 영향 범위를 최소화 |
| **Any Critical Defect Resets Trust** | 치명 결함 발생 시 신뢰 즉시 리셋 |
| **No Silent Expansion** | 별도 심사 없는 확장 금지 |
| **Controlled Degradation** | 제어된 강등 수행 |

---

## 3. 4단계 구조 (제34조)

| 단계 | 목적 | 역참조 |
|------|------|--------|
| 1. Frozen Observation | 운영 체계 검증 | 제35조 |
| 2. Micro Live | 최소 규모 실거래 검증 | 제36조 |
| 3. Controlled Live | 제한 확장 안정성 검증 | 제37조 |
| 4. Evidence-Based Expansion | 증거 기반 점진 확장 | 제38조 |

---

## 4. Frozen Observation (제35조)

이 단계에서는 다음을 우선한다.

- 대시보드 신뢰성 검증
- 알림 체계 검증
- 자동 점검 체계 검증
- 사고 탐지/기록 흐름 검증
- 운영 결함 제거

실거래는 수행하지 않는다.

---

## 5. Micro Live (제36조)

- 최소 자본, 최소 전략, 최소 포지션 수로만 운영한다.
- 이 단계의 목적은 수익이 아니라 실거래 환경에서 통제 체계가 유지되는지 확인하는 것이다.

---

## 6. Controlled Live (제37조)

- 제한적 범위에서 자본, 주문 수, 거래 시간대를 소폭 확장하여 안정성을 재검증하는 단계다.

---

## 7. Evidence-Based Expansion (제38조)

- 누적 증거가 충분할 때만 수행할 수 있다.
- 확장은 항상 작은 단위로 점진 수행해야 한다.
- 별도 심사 없이는 자본 확대를 허용할 수 없다.
- 승격 심사는 `promotion_review_template.md` 양식을 사용한다.

---

## 8. 승격 조건 (제39조)

다음 7개 조건을 **모두** 충족한 경우에만 다음 단계 승격을 검토할 수 있다.

1. CRITICAL 0
2. Ghost order 의심 0
3. 핵심 정합성 위반 0
4. evidence 누락 0
5. 자동 점검 연속 통과
6. UNVERIFIED 상태 거래 허용 이력 0
7. 운영자 수동 개입 감소 추세

---

## 9. 강등 조건 (제40조)

다음 중 **하나라도** 발생하면 즉시 강등 또는 재관찰을 검토해야 한다.

1. CRITICAL 발생
2. LOCKDOWN 진입
3. Ghost order 의심
4. Snapshot mismatch
5. evidence 누락
6. 복구 미검증 상태 거래 지속
7. 대시보드/알림/점검 상태 모순
8. 거래 허용 기준 위반

---

## 10. 승격 금지 규칙

- 자동 승격 금지
- 자동 자본 확대 금지
- 치명 결함 이후 신뢰 유지 금지
- 실거래 확대를 수익 목표 중심으로 서술하는 정책 금지
- 강등 조건 완화 또는 삭제 금지
- 관찰 단계 생략 금지

---

## 11. Promotion Review 연계

단계 전환 및 자본 확대 판단 시 반드시 `docs/operations/promotion_review_template.md` 표준 양식을 사용해야 한다.
승격 심사 완료가 자동 승격을 의미하지 않는다.
