# Baseline Hold 해제 조건 평가서

**문서 ID:** BASELINE-HOLD-RELEASE-EVAL-001
**작성일:** 2026-04-03
**작성자:** System (A 지시에 의거)
**판정 권한:** A
**문서 성격:** 해제 "평가" — 해제 "실행"이 아님

---

## 1. 해석 및 요약

### 현재 상태

| 항목 | 값 |
|------|-----|
| Baseline Hold | **ACTIVE** |
| Gate | **LOCKED** |
| operational_mode | `BASELINE_HOLD` |
| exchange_mode | `DATA_ONLY` |
| binance_testnet | `True` |
| blocked_api_count | 5 |
| disabled_beat_tasks | 3 |
| 전체 회귀 | **4444/4444 PASS** |
| 신규 실패 | **0건** |
| 운영 코드 변경 | **0건** |

### Hold 기간 작업 요약

| 작업 | 리스크 등급 | 결과 |
|------|-----------|------|
| 거버넌스 상태 가시화 (ops_state.json, API, startup log) | L2 | 완료 |
| 기준선 점검 자동화 (`/baseline-check`) | L2 | ACCEPTED |
| 재기동/복구 Drill (17 tests) | L1 | ACCEPTED |
| 변경 재진입 Gate (`/change-gate`, L0-L4) | L2 | ACCEPTED |
| TEST-ORDERDEP-001 정리 | L1 | RESOLVED |
| 기존 실패 2건 수정 (CR-036, CR-043) | L1 | RESOLVED |
| 증빙 문서 봉인 | L0 | 완료 |

**핵심 판단:** Hold 기간 동안 수행된 모든 작업은 L0-L2 범위였으며, L3-L4 변경은 0건입니다. 운영 경로(exchange, order, position)는 일체 변경되지 않았습니다.

---

## 2. 장점 / 단점

### Hold 해제 시 장점

- **회귀 완전 녹색**: 4444/4444 PASS, 잔존 실패 0건
- **강화된 관측 체계**: 6항목 자동 점검, drift 감지, 변경 gate가 모두 작동 중
- **재오염 방지 봉합**: TEST-ORDERDEP-001 2계층 방어 완료
- **문서/증빙 정비 완료**: runbook, change gate policy, scope matrix 등 정책 문서 확립
- 다음 CR 착수를 위한 **기반 준비 완료** 상태

### Hold 해제 시 단점/리스크

- CR-046 SOL Stage B 테스트넷 복구가 미완 (3회 연속 connectivity 미달성)
- Hold 해제 직후 L3-L4 변경이 성급하게 유입될 가능성
- Gate를 동시에 열면 변경 통제력이 일시적으로 약해질 수 있음

### Hold 유지 시 장점

- 추가 안정 관찰 기간 확보
- CR-046 테스트넷 복구까지 자연 대기

### Hold 유지 시 단점

- 이미 기술적으로 해제 가능 상태이므로 불필요한 지연
- 개선/확장 작업 착수 불가 지속

---

## 3. 이유 / 근거

### 판정 근거 1 — Hold 설정 사유 전수 재점검

| Hold 설정 사유 | 현재 상태 | 해소 여부 |
|---------------|----------|:---------:|
| 신규 CR 봉인 후 안정화 필요 (CR-038, CR-048계열, CR-049) | 봉인 5건 확인, 기준선 안정 | **해소** |
| exchange_mode DATA_ONLY 계약 준수 확인 필요 | 설정값 DATA_ONLY 확인, BL-EXMODE01 25 adapter tests PASS | **해소** |
| 금지 beat task 미발송 확인 필요 | schedule 미등록, Flower 미발견 확인 | **해소** |
| blocked API 5건 유지 확인 | blocked_api_count=5 확인 | **해소** |
| TEST-ORDERDEP-001 테스트 오염 | 2계층 방어 봉합, 4444/4444 PASS | **해소** |
| CR-049 Phase 3 (PAPER/LIVE) 구현 보류 | DESIGN_ONLY 상태 유지, 구현 미착수 | **별도 관리** |
| CR-046 SOL Stage B 테스트넷 복구 | 3회 연속 connectivity 미달성 | **별도 관측** |

**Hold 설정 사유 5/5 해소. 잔여 2건은 Hold 해제와 독립적인 별도 트랙.**

### 판정 근거 2 — 6항목 기준선 완전 일치

| # | 항목 | 기대값 | 실측값 | 판정 |
|---|------|--------|--------|------|
| 1 | operational_mode | BASELINE_HOLD | BASELINE_HOLD | PASS |
| 2 | exchange_mode | DATA_ONLY | DATA_ONLY | PASS |
| 3 | blocked_api_count | >= 5 | 5 | PASS |
| 4 | disabled_beat_tasks | >= 3 | 3 | PASS |
| 5 | forbidden_beat_tasks_absent | True | True (schedule 미등록) | PASS |
| 6 | startup_log_consistency | True | True (양쪽 BASELINE_HOLD) | PASS |

**Drift 판정: HOLD (정상 — drift 없음)**

### 판정 근거 3 — 회귀 테스트 완전 녹색

```
4444 passed, 0 failed (172.61s)
```

- 신규 실패: 0건
- 기존 실패 2건: RESOLVED (테스트만 수정, 운영 코드 무변경)
- TEST-ORDERDEP-001: RESOLVED (합동 75/75, 전체 4444/4444)

### 판정 근거 4 — 운영 리스크 잔존 여부

| 리스크 항목 | 상태 | Hold 해제 영향 |
|------------|------|:-------------:|
| exchange_mode 변경 가능성 | DATA_ONLY 고정, BL-EXMODE01 적용 중 | 없음 |
| private API 호출 가능성 | 5개 차단, guard 적용 중 | 없음 |
| 금지 task 재등장 가능성 | schedule 미등록, beat 미발송 | 없음 |
| 운영 코드 변경 | 0건 (이번 전체 작업 기간 중) | 없음 |
| 실주문 경로 | 차단 유지 | 없음 |
| CR-046 SOL Stage B | 별도 관측 트랙, Hold 해제와 독립 | 없음 |
| CR-049 Phase 3 | DESIGN_ONLY, 구현 HOLD 별도 유지 | 없음 |

**운영 write path에 대한 잔존 리스크: 없음.**

---

## 4. 실현 / 구현 대책

### Gate 재진입 조건 점검

| 질문 | 답변 |
|------|------|
| Hold 해제 시 Gate도 OPEN으로 전환할지? | **아니오** — Guarded Release 권고 |
| Hold만 해제하고 Gate는 LOCKED 유지할지? | **권고 옵션** (아래 상세) |
| 해제 시 허용 범위를 어디까지 열 것인지? | L0-L2 즉시, L3는 A 승인, L4는 별도 CR |

### 분리 유지 항목

Hold 해제와 무관하게 **계속 별도 관리하는 항목:**

| 항목 | 관리 방식 |
|------|-----------|
| CR-046 SOL Stage B 테스트넷 모니터링 | 관측만 유지, 3회 연속 connectivity 성공 전까지 상태 변화 없음 |
| CR-049 Phase 3 (PAPER/LIVE) | DESIGN_ONLY 유지, 별도 CR로 구현 착수 시 A 승인 필수 |
| ETH 운영 경로 금지 | CR-046 정책 그대로 유지 |
| ops_state.json open_issues 갱신 | A 편집 권한 (TEST-ORDERDEP-001 제거) |

---

## 5. 실행방법

### A. 해제 시 권고 절차

| 단계 | 행동 | 주체 |
|------|------|------|
| 1 | 본 평가서 검토 | A |
| 2 | 해제 판정 선언 | A |
| 3 | ops_state.json `operational_mode` 변경 | A (직접 편집) |
| 4 | ops_state.json `open_issues`에서 TEST-ORDERDEP-001 제거 | A (직접 편집) |
| 5 | baseline-check 재측정 (새 기준값 반영 확인) | System |
| 6 | 전체 회귀 1회 재확인 | System |
| 7 | 해제 증빙 문서 작성 | System |

### B. 유지 시 필요 사항

추가 조건 없음. 현 상태 그대로 유지하면 됨.

---

## 6. 더 좋은 아이디어 — Guarded Release (보호된 해제)

**전면 해제도 아니고 계속 동결도 아닌 중간 해법:**

### Guarded Release 운용안

| 항목 | 규칙 |
|------|------|
| Hold 상태 | **해제** (`BASELINE_HOLD` → 새 모드명, 예: `GUARDED_OPS`) |
| Gate | **LOCKED 24시간 유지** → 이후 A 판단으로 단계 개방 |
| 허용 범위 (즉시) | L0 (문서) + L1 (테스트) |
| 허용 범위 (24시간 후 검토) | L2 (관측) 추가 개방 여부 A 판단 |
| L3 (런타임) | A 승인 필수 — Gate 개방과 무관하게 항상 A 승인 |
| L4 (정책/실행) | **별도 CR 필수** — Hold 해제만으로 허용되지 않음 |
| CR-046 관측 | 계속 별도 유지, Hold 해제와 무관 |
| CR-049 Phase 3 | DESIGN_ONLY 유지, 구현은 별도 승인 |
| 금지 사항 유지 | DATA_ONLY 계약, ETH 금지, 금지 task 미발송 — 전부 유지 |
| 전체 회귀 | 해제 직후 1회 재확인 |
| 복귀 조건 | drift 감지 시 즉시 Hold 재진입 |

### Guarded Release 장점

- Hold의 핵심 보호(DATA_ONLY, 금지 task, blocked API)는 **전부 유지**
- 단지 `operational_mode` 라벨이 바뀌어 **새 L0-L1 작업 착수가 가능**해짐
- L4 변경은 여전히 별도 CR 필수이므로 **정책 변경 위험 차단 유지**
- drift 감지 시 자동/수동 재진입 가능

### Guarded Release 단점

- 모드명이 하나 더 늘어남 (관리 복잡도 미세 증가)
- A가 원하지 않으면 불필요한 중간 단계

---

## 최종 판정

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Current:        Baseline Hold ACTIVE               │
│                  Gate LOCKED                         │
│                                                     │
│  Recommendation: RECOMMEND RELEASE                  │
│                  (Guarded Release 형태 권고)          │
│                                                     │
│  If Released:    L0/L1 즉시 허용                     │
│                  L2 24시간 후 A 검토                  │
│                  L3 A 승인 필수 (항상)                │
│                  L4 별도 CR 필수 (항상)               │
│                  Gate LOCKED 24시간 유지              │
│                                                     │
│  If Held:        추가 필요 조건 없음                  │
│                  현 상태 유지 시 기술적 문제 없음       │
│                                                     │
│  Separation:     CR-046 → 별도 관측 유지             │
│                  CR-049 Ph.3 → DESIGN_ONLY 유지      │
│                  DATA_ONLY 계약 → 유지               │
│                  금지 task/API → 유지                 │
│                                                     │
│  Evidence:       4444/4444 PASS                     │
│                  Hold 사유 5/5 해소                   │
│                  운영 코드 변경 0건                    │
│                  6항목 drift 없음                     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 판정 근거 한 줄 요약

> Hold를 설정했던 5가지 사유가 전부 해소되었고, 회귀 4444/4444 녹색, 운영 코드 변경 0건, 6항목 drift 없음. 잔여 2건(CR-046 관측, CR-049 Phase 3)은 Hold와 독립적인 별도 트랙. **Guarded Release 형태로 해제를 권고합니다.**

---

**본 문서는 해제 "평가"이며, 해제 "실행"은 A 판정 후에만 진행됩니다.**
**현재 상태: Baseline Hold ACTIVE / Gate LOCKED.**
