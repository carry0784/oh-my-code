# CR-046 SOL C1 — SKIP_SIGNAL_NONE 원인 분석 리포트

**상태:** CONDITIONAL ACCEPT → 4개 정정 반영 완료 → **SEALED**
**작성일:** 2026-04-08
**근거:** Stage B 24-bar PASS-SEALED (2026-04-07 13:50 ~ 2026-04-08 13:50 UTC)

---

## 3줄 요약

1. 24-bar 연속 SKIP_SIGNAL_NONE은 전략의 **2/2 consensus + last-bar-only 판정** 구조에서 발생하는 **예측 가능한 정상 동작**이며, 버그가 아니다.
2. Phase 3 백테스트 기준 단순 근사로 24-bar 무신호는 드문 사건이 아니다 (bar당 0.9%, 독립 가정 시 ~80%). **단, 이는 iid 근사 참고 기준선이며 봉인 근거는 아니다.**
3. receipt에 smc_sig/wt_sig/wt1/wt2 값이 미기록되어 **탈락 원인을 사후 감사할 수 없으며**, 이것이 운영상 실질적 병목이다.

---

## 필수 산출물 1 — 리포트 본문

### (1) 해석 및 요약

24개 연속 bar에서 `strategy.analyze()`가 None을 반환했다. 핵심 판정 라인 (`smc_wavetrend_strategy.py:233`):

```python
if smc_sig == 0 or wt_sig == 0 or smc_sig != wt_sig:
    return None  # → SKIP_SIGNAL_NONE
```

None 반환 3가지 경우:
- **SMC가 0**: 해당 bar에서 BOS/CHoCH 돌파 미발생
- **WaveTrend가 0**: 해당 bar에서 wt1/wt2 cross 미발생
- **방향 불일치**: SMC와 WT가 반대 방향

Phase 3 기반 역산 (참고 기준선, 봉인 근거 아님):
- SOL: 4,320 bars / 39 trades = bar당 신호 확률 ~0.9%
- 독립 가정 시 24-bar 연속 무신호 확률 ~80%
- **live 레짐과 백테스트 레짐 차이가 있으므로, 이 수치는 설명용 baseline이지 운영 봉인 증거가 아니다**

현재 receipt에는 `consensus_pass=False`만 기록되고, smc_sig/wt_sig/wt1/wt2 값이 **누락**되어 "어떤 조건이 병목인지" 사후 판별 불가.

### (2) 장점/단점

**장점:**
- fail-closed 원칙 철저 적용 (None → 즉시 SKIP, 후속 경로 안전 차단)
- dry_run=True 하드코딩 → 실거래 위험 없음
- 2/2 consensus는 false positive 억제 → Phase 4 Sharpe 0.76~1.24 보존

**단점:**
- `analyze()`가 None/signal dict 이진 구조 → None일 때 원인 분해 불가
- 마지막 bar에서만 판정 → near-miss(거의 신호가 날 뻔한 상태) 포착 불가
- receipt에 전략 중간 계산값 미저장 → 시장 평탄 vs 지표 계산 오류 구분 불가
- preflight checklist 4.1에 "per-bar 지표값 기록" 명시했으나 **실제 구현과 괴리**

### (3) 이유/근거

**구조적 원인 3가지:**

| 원인 | 메커니즘 | 영향 |
|------|---------|------|
| A. SMC 구조적 희소성 | internal_length=5 → 최소 10-bar lookback, close가 swing high/low 돌파 시에만 signal≠0, 돌파 후 리셋 | 횡보 시장에서 연속 0 |
| B. WaveTrend cross-only | wt1/wt2 cross는 추세 전환 시점에서만 발생, n1=10/n2=21 smoothing으로 cross 빈도 저하 | 추세 지속 중 연속 0 |
| C. 동시 발생 확률 | 독립 가정 시 ~0.245%, 실측 0.9% (레짐 상관 클러스터링). **참고 수치, 봉인 근거 아님** | 신호가 클러스터로 발생하고 무신호 구간이 길게 지속 |

### (4) 실현/구현 대책

**대책 1 — 진단 로그 확장 (Diagnostic Receipt Extension)**

signal_result가 None일 때도 전략 중간값을 receipt에 기록. **현재 `analyze()` 계약(`None | signal_dict`)은 유지하고, 진단 수집은 receipt builder 측에서 별도 수행한다 (거래 판단 계약과 진단 계약 분리 원칙).**

필수 추가 필드:

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `smc_sig_raw` | int | SMC signal (0, 1, -1) |
| `wt_sig_raw` | int | WT signal (0, 1, -1) |
| `wt1_val` | float | WT wt1 마지막 bar |
| `wt2_val` | float | WT wt2 마지막 bar |
| `smc_trend_val` | int | SMC trend (0, 1, -1) |
| `skip_reason_codes` | list[str] | 탈락 사유 코드 목록 (아래 참조) |

`skip_reason_codes` 정의 (리스트형 단일 필드, 복수 코드 허용):
- `SMC_ZERO`: smc_sig == 0
- `WT_ZERO`: wt_sig == 0
- `DIRECTION_MISMATCH`: smc_sig != 0 and wt_sig != 0 and smc_sig != wt_sig
- `DATA_INSUFFICIENT`: len(ohlcv) < min_bars

> ~~BOTH_ZERO 제거~~: `[SMC_ZERO, WT_ZERO]` 조합으로 표현. 중복 코드 불필요.

**대책 2 — 기대 빈도 기준선 명문화**

| 임계 | 값 | 의미 | 근거 등급 |
|------|-----|------|-----------|
| 평균 신호 간격 | 110 bars (4.6일) | Phase 3 기반 | inferred_from_backtest |
| 경보 임계 | 168 bars (7일) | SIGNAL_DROUGHT_WARN | inferred_from_backtest |
| 정지 임계 | 336 bars (14일) | HALT_REVIEW_REQUIRED | inferred_from_backtest |

### (5) 실행방법

| 순서 | 작업 | 코드 수정 여부 |
|------|------|---------------|
| 1 | **C1-B: 24-bar OHLCV 재현 검증** — 실제 탈락 원인 1회성 확인 | 없음 (스크립트 실행) |
| 2 | C1-B 결과를 반영하여 진단 필드 설계서 확정 | 없음 (설계만) |
| 3 | A 승인 후 진단 필드 구현 | **별도 GO** |
| 4 | 168-bar 관측 후 비율 집계 | 없음 (관측) |
| 5 | Phase 3 대조 리포트 | 없음 |

### (6) 더 좋은 아이디어

**A — Near-Miss 3단계 분리:** `SMC_ONLY` / `WT_ONLY` / `DIR_MISMATCH`로 세분화. skip_reason_codes와 정합적. **추가 반영: 산출물 5 필드 정의에 candidate_long/candidate_short로 반영 완료.**

**B — Evidence Grade 필드:** 각 결론을 `inferred_from_backtest` / `observed_from_live_receipt` / `observed_from_replay`로 구분. **추가 반영: 기대 빈도 기준선 표에 근거 등급 컬럼 추가.**

**C — Diagnostic Scope Lock:** receipt 확장에 `diagnostic_only=true` 메타 필드를 두어 자가진화 엔진의 오연결 방지. **추가 반영: 산출물 6 금지영역에 반영.**

---

## 필수 산출물 2 — 고정 골격 매핑

### Observation
24-bar 연속 SKIP_SIGNAL_NONE 관측. ERROR=0, halt=0, dry_run=True 전 bar. consensus_pass=False 전 bar. **receipt에 smc_sig/wt_sig 원시값 미기록.** Phase 3 기준 24-bar 무신호는 기대 범위 내 (참고 기준선).

### Interpretation
전략의 2/2 consensus + last-bar-only 판정 구조에서 발생하는 정상 동작. 그러나 **탈락 원인을 SMC/WT/방향불일치로 분해할 데이터 없음** → 정상 확인과 이상 탐지 구분 불가.

### Decision
(1) 24-bar 무신호를 정상으로 공식 확인 (2) 진단 로그 확장을 **C1-A 진단 관측성 확장**으로 설계 제출 (3) 파라미터/전략 수정 수행 안 함 (4) 기대 빈도 기준선 명문화.

### Execution
C1-B 재현 검증 먼저 수행 → 결과를 반영하여 진단 필드 설계서 확정 → A 승인 → 구현. 현 Stage B는 진단 로그 없이 계속 관측. 168-bar 무신호 시 파이프라인 점검 트리거. 코드 수정은 별도 GO에서 수행.

### Learning
(1) 백테스트 신호 빈도와 live 기대치를 사전 문서화 필요 (2) analyze()가 None 반환 시에도 진단 정보 노출 구조가 paper 단계에서 필수 (3) preflight checklist와 실제 구현 간 gap 확인됨.

### Evolution
(1) analyze() → always-return-diagnostic 구조는 **진화 후보로만 유지** (즉시 구현 아님, 현재 계약 유지) (2) near-miss 카운터 운영 보조 지표 도입 후보 (3) regime snapshot receipt 추가 후보.

### Constitution
- 2/2 consensus 완화 불가 (canonical core v2)
- 파라미터 변경은 full CR cycle 필요
- Track C v1 regime filter 적용 금지 (FAIL 판정)
- dry_run=True 해제는 A 명시 승인 없이 불가
- 진단 로그 추가는 receipt "확장"이므로 breaking change가 아닌 한 CR-046 범위 내 가능
- **analyze() 계약 변경(always-return-diagnostic)은 진화 후보로만 유지, 즉시 구현 대상 아님**

---

## 필수 산출물 3 — 슬롯 분해

### 관측 규칙
- **OBS-1:** 매 bar receipt에 smc_sig_raw, wt_sig_raw, wt1_val, wt2_val, smc_trend_val 기록
- **OBS-2:** skip_reason_codes (리스트형 단일 필드): SMC_ZERO / WT_ZERO / DIRECTION_MISMATCH
- **OBS-3:** near-miss 3단계 분리: SMC_ONLY / WT_ONLY / DIR_MISMATCH

### 해석 규칙
- **INT-1:** 24-bar 무신호는 기대 빈도 기준선 내 정상 (참고 수치, 봉인 근거 아님)
- **INT-2:** 168-bar 연속 무신호 → "경보 임계" → 파이프라인 점검 촉발
- **INT-3:** smc_sig=0 비율 >95% → "SMC 병목"
- **INT-4:** wt_sig=0 비율 >95% → "WT 병목"

### 상태 전이 규칙
- **ST-1:** SKIP_SIGNAL_NONE 168-bar 초과 → ALERT_NO_SIGNAL
- **ST-2:** ALERT_NO_SIGNAL + 신호 1회 → NORMAL 복귀
- **ST-3:** ALERT_NO_SIGNAL 336-bar 초과 → HALT_REVIEW_REQUIRED

### 시나리오 규칙
- **SC-1:** SMC 병목 — 횡보 레짐에서 swing 돌파 미발생
- **SC-2:** WT 병목 — 강한 추세에서 wt1/wt2 발산, cross 미발생
- **SC-3:** 방향 불일치 — SMC bullish BOS + WT bearish cross

### 실행 제한 규칙
- **EX-1:** 진단 로그 추가 시 기존 receipt 읽기 호환성 보장 필수 (append-only)
- **EX-2:** **analyze() 시그니처/계약 변경은 즉시 구현 대상 아님** — 진단 수집은 receipt builder 측에서 별도 수행
- **EX-3:** 진단 필드는 운영 판단 보조용 — 자동 파라미터 조정에 사용 금지
- **EX-4:** `diagnostic_only=true` 메타 태그로 진단 필드와 거래 필드 구분 강제

### 학습 항목
- **LN-1:** 백테스트 신호 빈도 → live 기대 빈도 매핑 방법론 수립
- **LN-2:** preflight checklist ↔ 실제 구현 gap analysis 프로세스
- **LN-3:** None 반환 함수의 진단 정보 노출 패턴 표준화

### 진화 후보 규칙
- **EV-1:** analyze() → always-return-diagnostic (None 폐기) — **진화 후보로만 유지, 즉시 구현 대상 아님**
- **EV-2:** rolling signal density metric (최근 N bar 중 signal≠0 비율)
- **EV-3:** regime-aware 기대 빈도 (bear → 높은 기대, sideways → 낮은 기대)

### 헌법/거버넌스 제한 규칙
- **GOV-1:** 2/2 consensus 완화는 canonical core v2 위반 → 금지
- **GOV-2:** 파라미터 변경은 full CR cycle 없이 금지
- **GOV-3:** 진단 로그가 진입/퇴출 로직을 변경하면 안 됨 (순수 관측 확장만)
- **GOV-4:** Track C v1 regime filter 우회 도입도 금지

---

## 필수 산출물 4 — 병목 분해표

| 조건명 | 역할 | 관측 가능 | 탈락 추적 가능 | 병목 가능성 | 추가 로그 필요 | shadow/paper 검증 |
|--------|------|-----------|---------------|-------------|---------------|------------------|
| `smc_sig == 0` | BOS/CHoCH 돌파 미발생 | **불가** | **불가** | **높음** | **필요** (smc_sig_raw) | paper 7일 관측 |
| `wt_sig == 0` | wt1/wt2 cross 미발생 | **불가** | **불가** | **중간** | **필요** (wt_sig_raw, wt1/wt2) | paper 7일 관측 |
| `smc_sig != wt_sig` | 방향 불일치 | **불가** | **불가** | **낮음~중간** | **필요** (skip_reason_codes) | paper 확인 가능 |
| `len(ohlcv) < min_bars` | 데이터 부족 | 가능 | 가능 | **없음** (200 fetch, min=26) | 불필요 | 해당 없음 |
| OHLCV fetch 실패 | API 장애 | 가능 | 가능 | **없음** (ERROR=0) | 불필요 | 해당 없음 |
| kill-switch | 세션 정지 | 가능 | 가능 | **없음** (halt=0) | 불필요 | 해당 없음 |
| wt1/wt2 크로스 근접도 | cross "거의" 발생 | **불가** | **불가** | **판단 불가** | **필요** (wt1_val, wt2_val) | paper 관측 |
| smc_trend 방향 | 현재 추세 | **불가** | **불가** | **판단 불가** | **필요** (smc_trend_val) | paper 관측 |

---

## 필수 산출물 5 — 데이터/상태/이벤트 정의

### 확장 Receipt 필드

| 필드명 | 타입 | 기본값 | 설명 | 근거 등급 |
|--------|------|--------|------|-----------|
| `regime_snapshot` | dict | `{}` | `{volatility_pctile, directional_efficiency, trend_label}` | observed_from_live_receipt |
| `candidate_long` | bool | False | SMC 또는 WT 중 하나라도 long(+1) 생성 여부 | observed_from_live_receipt |
| `candidate_short` | bool | False | SMC 또는 WT 중 하나라도 short(-1) 생성 여부 | observed_from_live_receipt |
| `smc_filter_pass` | bool | False | `smc_sig != 0` | observed_from_live_receipt |
| `wavetrend_filter_pass` | bool | False | `wt_sig != 0` | observed_from_live_receipt |
| `skip_reason_codes` | list[str] | [] | `[SMC_ZERO, WT_ZERO, DIRECTION_MISMATCH]` (리스트형 단일 필드) | observed_from_live_receipt |
| `market_context_bucket` | str | "unknown" | bear_strong / bear_weak / sideways / bull_strong | observed_from_live_receipt |
| `audit_trace_id` | str | UUID | receipt_id와 동일 (향후 trace chain 확장 시 parent/root 관계 추가) | observed_from_live_receipt |
| `diagnostic_only` | bool | true | 진단 전용 필드 표식 — 자가진화 엔진 오연결 방지 | meta |

> **volatility_filter_pass 제거됨:** Track C v2 예약 필드는 현재 C1 범위 밖. 미래 확장 시 별도 CR에서 추가.

### 추가 진단 필드 (receipt.data JSON)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `smc_sig_raw` | int | SMC signal (-1, 0, 1) |
| `wt_sig_raw` | int | WT signal (-1, 0, 1) |
| `smc_trend_raw` | int | SMC trend (-1, 0, 1) |
| `wt1_val` / `wt2_val` | float | WT 마지막 bar 값 |
| `wt_cross_distance` | float | `abs(wt1 - wt2)` |
| `close_price` | float | 현재 bar close |

### 이벤트 정의

| 이벤트명 | 트리거 조건 | 액션 |
|----------|-------------|------|
| `SIGNAL_DROUGHT_WARN` | 연속 168 bars 무신호 | WARN + 운영자 알림 |
| `SIGNAL_DROUGHT_HALT` | 연속 336 bars 무신호 | ERROR + 파이프라인 점검 + A 통보 |
| `NEAR_MISS_CLUSTER` | 최근 24 bars 중 candidate_long/short ≥ 3회 | INFO — 신호 근접 상태 |
| `REGIME_SHIFT_DETECTED` | market_context_bucket 변경 | INFO + regime 전환 기록 |

---

## 필수 산출물 6 — 금지영역

| 금지 항목 | 근거 | 위반 시 영향 |
|-----------|------|-------------|
| 2/2 consensus → 1/2 완화 | canonical core v2 | Phase 4 Sharpe 무효화, 전체 검증 재수행 |
| 파라미터 변경 | rollout plan 8항 | Phase 2/3/4 재수행 |
| Track C v1 filter 적용 | Track C report: FAIL | 검증 실패 필터 적용 → 품질 저하 |
| 진단 로그 → 자동 파라미터 조정 | canonical core 5항 + diagnostic_only 원칙 | 선택 편향 내재 |
| near-miss → 진입 조건 승격 | consensus 우회 | 2/2 원칙 위반 |
| dry_run=False 전환 | rollout plan 8항 | A 명시 승인 없이 절대 금지 |
| ETH 배포 | CR-046: research only | Phase 3 FAIL (Sharpe -3.88) |
| receipt 스키마 breaking change | append-only 원칙 | 기존 24-bar 데이터 접근 불가 |
| analyze() 계약 변경 즉시 구현 | EX-2, BTC task 동기화 리스크 | **진화 후보로만 유지** |
| diagnostic 필드를 자가진화 엔진에 직접 연결 | diagnostic_only 원칙 | 관측 확장이 제어 루프로 전환됨 |

---

## 필수 산출물 7 — 다음 단계 분기안

### C1-B: 24-bar OHLCV 재현 검증 (우선순위 1 — 즉시 수행)

| 단계 | 작업 |
|------|------|
| B-1 | 24-bar 구간 OHLCV 데이터를 exchange에서 재요청 |
| B-2 | analyze()에 직접 투입 → smc_sig, wt_sig, wt1, wt2 값 확인 |
| B-3 | skip_reason_codes 분포 집계 (SMC_ZERO / WT_ZERO / DIRECTION_MISMATCH) |
| B-4 | 결과를 C1-A 설계에 반영 |

**이유:** 코드 수정 없이 즉시 탈락 원인의 1회성 진실표본 확보. C1-A 설계 전 과잉 설계 방지.

### C1-A: 진단 관측성 확장 (우선순위 2 — C1-B 후)

| 단계 | 작업 | 소요 |
|------|------|------|
| A-1 | C1-B 결과 반영하여 receipt 진단 필드 설계서 확정 | 1 session |
| A-2 | A 승인 후 진단 필드 구현 (receipt builder 확장) | 2 sessions |
| A-3 | 168-bar 관측 → smc_sig=0/wt_sig=0 비율 집계 | 7일 |
| A-4 | Phase 3 대조 리포트 | 1 session |

### C1-C: 이상 탐지 (조건부 발동, 우선순위 3)

**발동 조건:** C1-A의 A-3에서 smc_sig=0 비율이 99%+이고 Phase 3 대비 현저히 높을 때.

---

## 미해결 리스크

| ID | 리스크 | 심각도 | 상태 | 완화 방안 |
|----|--------|--------|------|-----------|
| R-1 | 진단 로그 미구현 → 탈락 원인 감사 불가 | **높음** | 미해결 | C1-A 구현 (A 승인 필요) |
| R-2 | testnet OHLCV ≠ mainnet 가능성 | **중간** | 미확인 | C1-C에서 확인 |
| R-3 | 168-bar 경보 임계값 미검증 | **낮음** | 추정 | 7일 관측 후 조정 |
| R-4 | preflight 4.1 ↔ 실제 구현 간 괴리 | **중간** | 확인됨 | 진단 로그 구현으로 해소 |
| R-5 | sideways 레짐 장기 무신호 | **중간** | 이론적 | regime_snapshot으로 사후 분석 |
| R-6 | analyze() 변경 시 BTC tasks 동기 수정 누락 | **중간** | 미발생 | 계약 변경은 진화 후보로만 유지하여 리스크 억제 |

---

## 헌법 조항 대조 검수본

| 조항 | 출처 | 준수 | 근거 |
|------|------|------|------|
| 2/2 consensus required | canonical core v2 | **준수** | 완화 미제안, 금지영역 명시 |
| SMC Version B (pure-causal) | canonical core v2 | **준수** | Version A 언급 없음 |
| Adaptive 3rd indicator forbidden | canonical core 5항 | **준수** | 자동 조정 금지 + diagnostic_only 원칙 명시 |
| Track C v1 NOT adopted | CLAUDE.md CR-046 | **준수** | 금지영역 명시 |
| dry_run=True paper only | rollout plan 1항/8항 | **준수** | 코드 수정 미제안 |
| ETH excluded | CR-046 current state | **준수** | 금지영역 명시 |
| Param change requires full CR | rollout plan 8항 | **준수** | 변경 미제안, 금지영역 명시 |
| fail-closed state machine | sol_paper_tasks 설계 | **준수** | 기존 경로 변경 미제안 |

**검수 결과: 8/8 조항 전수 준수 확인**

---

## 정정 이력

| # | 정정 항목 | 변경 전 | 변경 후 |
|---|----------|---------|---------|
| 1 | 확률 문구 강도 | "기대 범위 내" (봉인 근거처럼 사용) | "참고 기준선, 봉인 근거 아님" 명시 |
| 2 | 체인 명칭 | Decision에 "C2" 혼용 | 전부 "C1-A 진단 관측성 확장"으로 통일 |
| 3 | skip reason field | skip_reason_code(단일) + skip_reason_codes(리스트) 공존 | skip_reason_codes 리스트형 단일 필드, BOTH_ZERO 제거 |
| 4 | always-return-diagnostic | 대책 2로 즉시 구현 가능처럼 서술 | EV-1 진화 후보로만 유지, 현재 계약 유지 명시 |

추가 반영:
- Evidence Grade 필드 (근거 등급 컬럼) → 기대 빈도 표, receipt 필드 표
- Diagnostic Scope Lock (diagnostic_only) → 산출물 5, 6
- Near-Miss 3단계 분리 → 슬롯 OBS-3
- volatility_filter_pass 제거 (C1 범위 밖)
