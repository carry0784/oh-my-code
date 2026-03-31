# CR-031 — Steady-State Reopen Trigger Protocol

Effective: 2026-05-14
Status: **ACTIVE**
Author: B (Implementer)
Reviewer: A (Designer)
Scope: CR-027~030 봉인 이후 관찰 체계 및 재개시 조건

---

## 1. Purpose

CR-027(복구) → CR-028(정리) → CR-029(방지) → CR-030(장기 검토) 4연속 봉인 완료 후,
**"후속 구현 카드 없음" 상태를 운영 규칙으로 봉인**한다.

새 CR은 **정의된 트리거가 충족될 때만** 열 수 있다.
감, 불안, 체감만으로 구조 변경 카드를 개시할 수 없다.

---

## 2. 봉인 기준선 참조표

| CR | 카드 | 핵심 성과 | 기준선 |
|----|------|-----------|--------|
| CR-027 | evidence hot path 성능 복구 | 196s→0.059s | ops-status cold ≤0.5s, warm ≤0.05s |
| CR-028 | backend abstraction 정리 | `_bundles` 직접 접근 0건 | `store._bundles` 참조 금지 |
| CR-029 | 성능 회귀 방지 가드 | 52개 guard tests | 3171/0/0 PASS |
| CR-030 | 장기 설계 검토 | A안(현행 유지) 채택 | 재검토 트리거 0/4 |

**이 기준선은 트리거 충족 전까지 변경 금지.**

---

## 3. 관찰 지표

### 3.1 일간 관찰 (Daily Light Check)

기존 Mode 1 daily check에 포함. 추가 행동 불필요.

| 지표 | 관찰 방법 | 정상 범위 |
|------|-----------|-----------|
| ops-status 응답시간 | dashboard 로드 체감 | cold < 0.5s |
| Safety 7/7 | dashboard safety panel | 7/7 전부 True |
| evidence 누적 건수 | ops-aggregate evidence_summary | 단조 증가, 급등 없음 |

### 3.2 주간 관찰 (Weekly Governance Review)

| 지표 | 관찰 방법 | 정상 범위 |
|------|-----------|-----------|
| orphan_detected | governance summary panel | False |
| forbidden pattern 회귀 | `pytest tests/test_evidence_performance_guard.py -k Forbidden` | 21/21 PASS |
| hot path budget | `pytest tests/test_evidence_performance_guard.py -k Budget` | 5/5 PASS |
| SQLite smoke | `pytest tests/test_evidence_performance_guard.py -k SQLite` | 7/7 PASS |

### 3.3 월간 관찰 (Monthly Audit)

| 지표 | 관찰 방법 | 정상 범위 | 경고 임계 |
|------|-----------|-----------|-----------|
| evidence 총 건수 | `store.count()` | 단조 증가 | 월 증가율 > 200% |
| phase-tagged evidence 건수 | 수동 확인 또는 `count_orphan_pre()` 호출 | Mode 1: 0건 | > 0건 (Mode 2 전환 징후) |
| orphan count | `count_orphan_pre()` | 0 | > 0 |
| count_orphan_pre() 소요시간 | 수동 측정 | < 0.01s | > 0.1s |
| 전체 테스트 수 | `pytest tests/ -q` | ≥ 3171 | 감소 시 즉시 조사 |

---

## 4. 재개시 트리거 표

새 evidence/performance 관련 구현 CR을 열려면 아래 트리거 중 **최소 1개 충족**이 필요하다.

| # | 트리거 | 임계값 | 요구 증거 |
|---|--------|--------|-----------|
| T-1 | orphan count latency 초과 | `count_orphan_pre()` > 0.5s (실측, 3회 연속) | 실측 로그 3회분 + evidence 건수 |
| T-2 | phase-tagged evidence 급증 | > 10,000건 누적 | `store.count()` + phase 비율 |
| T-3 | orphan_detected 비정상 패턴 | 연속 3일 orphan_detected=True | governance summary 로그 3일분 |
| T-4 | hot path budget 위반 재발 | ops-status > 0.5s (실측, 3회 연속) | curl 실측 로그 3회분 |
| T-5 | forbidden pattern 회귀 검출 | AXIS 3 테스트 1건 이상 FAIL | pytest 출력 |
| T-6 | evidence volume 설계 범위 초과 | 총 evidence > 5,000,000건 | `store.count()` 실측 |

### 트리거 충족 없이 열 수 있는 예외

| 예외 | 조건 |
|------|------|
| 보안 인시던트 | security_state = LOCKDOWN 발생 시 |
| 헌법 위반 발견 | safety invariant 위반 검출 시 |
| A의 명시적 긴급 지시 | A가 근거와 함께 트리거 우회를 선언 |

---

## 5. 재개시 판정 절차

### Step 1: 트리거 충족 확인

- 관찰자(B)가 트리거 충족을 감지
- 요구 증거를 수집하여 A에게 보고

### Step 2: A의 재개시 승인

- A가 증거를 검토
- 판정: **재개시 GO** 또는 **관찰 유지**
- GO인 경우 카드 유형 지정: L1(문서) / L2(코드) / 설계 검토

### Step 3: CR 등록

- CR-032+로 intake registry에 등록
- 기존 CR-031 트리거 참조 명시
- 범위 제한: 트리거에 해당하는 부분만

### 판정 기준

| 조건 | 판정 |
|------|------|
| 트리거 1개 충족 + 증거 제출 | **재개시 검토 가능** |
| 트리거 2개 이상 충족 | **재개시 강력 권고** |
| 트리거 0개 | **재개시 금지** |

---

## 6. 트리거 미충족 시 금지 행위

| # | 금지 행위 | 이유 |
|---|-----------|------|
| F-1 | 트리거 미충족 상태에서 evidence 구조 변경 카드 개시 | 과잉 대응 |
| F-2 | 체감 불안만으로 materialization/link table 구현 | 근거 없는 구조 변경 |
| F-3 | synthetic 수치만 보고 production 구조 변경 | 대표성 부족 |
| F-4 | "나중에 필요할 것 같아서" 식 선행 구현 | premature optimization |
| F-5 | CR-029 guard test를 느슨하게 수정 | 방어선 약화 |
| F-6 | CR-028 facade를 우회하는 새 코드 추가 | 추상화 경계 위반 |

---

## 7. 30일 무변경 관찰 기간

CR-031 봉인 후 최소 **30일간 무변경 관찰 기간**을 둔다.

| 항목 | 규칙 |
|------|------|
| 기간 | 2026-05-14 ~ 2026-06-13 |
| 코드 변경 | evidence/performance 관련 금지 |
| 테스트 변경 | CR-029 guard 수정 금지 |
| 문서 변경 | 관찰 기록만 허용 |
| 트리거 충족 시 | 30일 대기 면제, 즉시 재개시 절차 진입 |

30일 후:
- 트리거 0건 → 관찰 유지, 추가 60일 연장 검토
- 트리거 1건+ → 재개시 절차 진입

---

## 8. 헌법 조항 대조

| 규칙 | 준수 | 비고 |
|------|------|------|
| Append-only evidence | ✅ | 코드 변경 없음 |
| Read-only 원칙 | ✅ | 관찰만 |
| Fail-closed | ✅ | 기존 유지 |
| 운영 의미 변경 | ✅ | 없음 |
| Mode 1 Steady-State | ✅ | 보호 강화 |

---

## A 판단용 1문장 결론

**현재는 구현 금지 / 관찰 유지가 맞으며, 정의된 6개 트리거 중 1개 이상 충족 시에만 새 CR을 열 수 있다.**
