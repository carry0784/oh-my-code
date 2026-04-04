# CR-048 Stage 4A: Fail-Closed Matrix

**문서 ID:** STAGE4A-FAILCLOSED-001
**작성일:** 2026-04-03

---

## 1. 실패 지점 × 행동

| # | 실패 지점 | 입력 조건 | fail-closed 행동 | Verdict | downstream 차단 |
|---|-----------|-----------|-----------------|---------|:---------------:|
| FC-1 | TransformResult reject | `decision ∈ _REJECT_DECISIONS` | screen() 미호출 | `DATA_REJECTED` | screen + qualify |
| FC-2 | TransformResult None input | `screening_input is None` | screen() 미호출 | `DATA_REJECTED` | screen + qualify |
| FC-3 | Screening 미통과 | `ScreeningOutput.all_passed == False` | qualify() 미호출 | `SCREEN_FAILED` | qualify |
| FC-4 | Qualification 미통과 | `QualificationOutput.all_passed == False` | 결과 기록만 | `QUALIFY_FAILED` | — |
| FC-5 | Unknown decision | `decision not in known set` | `raise ValueError` | (예외) | 전체 |

---

## 2. Failure Mode → Verdict 매핑

### Stage 3B-2 F1-F9 → Pipeline Verdict

| Failure Mode | TransformResult.decision | Pipeline Verdict |
|:------------:|--------------------------|:----------------:|
| F1 (empty) | PARTIAL_REJECT | `DATA_REJECTED` |
| F2 (partial mandatory) | PARTIAL_REJECT | `DATA_REJECTED` |
| F3 (partial optional) | PARTIAL_USABLE | 계속 → screen 결과에 따름 |
| F4 (stale) | STALE_REJECT | `DATA_REJECTED` |
| F5 (insufficient bars) | OK | 계속 → stage 5에서 SCREEN_FAILED 가능 |
| F6 (no listing age) | OK | 계속 → stage 1에서 SCREEN_FAILED 가능 (listing_age_days=None) |
| F7 (namespace) | SYMBOL_NAMESPACE_ERROR | `DATA_REJECTED` |
| F8 (timeout) | PARTIAL_REJECT or SYMBOL_NAMESPACE_ERROR | `DATA_REJECTED` |
| F9 (degraded) | PARTIAL_USABLE | 계속 → screen 결과에 따름 |

### Screening Stage → Pipeline Verdict

| Screening Stage | 실패 조건 | Pipeline Verdict |
|:---------------:|-----------|:----------------:|
| Stage 1 (Exclusion) | excluded sector/low market cap/young listing | `SCREEN_FAILED` |
| Stage 2 (Liquidity) | low volume/high spread | `SCREEN_FAILED` |
| Stage 3 (Technical) | ATR out of range/low ADX | `SCREEN_FAILED` |
| Stage 4 (Fundamental) | high PER/low ROE/low TVL | `SCREEN_FAILED` |
| Stage 5 (Backtest) | low bars/negative Sharpe/high missing | `SCREEN_FAILED` |

### Qualification Check → Pipeline Verdict

| Qualification Check | 실패 조건 | Pipeline Verdict |
|:-------------------:|-----------|:----------------:|
| Check 1 (data compat) | asset class mismatch | `QUALIFY_FAILED` |
| Check 2 (warmup) | insufficient warmup | `QUALIFY_FAILED` |
| Check 3 (leakage) | future data leak detected | `QUALIFY_FAILED` |
| Check 4 (data quality) | high missing/disorder/duplicates | `QUALIFY_FAILED` |
| Check 5 (min bars) | bars < 500 | `QUALIFY_FAILED` |
| Check 6 (performance) | negative Sharpe or excessive DD | `QUALIFY_FAILED` |
| Check 7 (cost sanity) | post-cost Sharpe/turnover fail | `QUALIFY_FAILED` |

---

## 3. 단계 도달 보장

| Verdict | transform 실행 | screen 실행 | qualify 실행 |
|---------|:--------------:|:-----------:|:------------:|
| `DATA_REJECTED` | YES | **NO** | **NO** |
| `SCREEN_FAILED` | YES | YES | **NO** |
| `QUALIFY_FAILED` | YES | YES | YES |
| `QUALIFIED` | YES | YES | YES |

---

## 4. PipelineResult Invariants

| Invariant | 검증 방법 |
|-----------|-----------|
| `DATA_REJECTED` → `screening_output is None and qualification_output is None` | 테스트 (F1/F2/F4/F7/F8) |
| `SCREEN_FAILED` → `screening_output is not None and qualification_output is None` | 테스트 (threshold 미달) |
| `QUALIFY_FAILED` → `screening_output is not None and qualification_output is not None` | 테스트 (bars/sharpe) |
| `QUALIFIED` → `둘 다 not None and 둘 다 all_passed=True` | 테스트 (golden set) |
| `result.symbol == evidence.symbol` | 모든 테스트에서 확인 |

---

## 5. 경계 조건 (Edge Cases)

| Case | 입력 | 예상 Verdict |
|------|------|:------------:|
| PARTIAL_USABLE + all screen thresholds pass + qualify pass | F3/F9 fixture | `QUALIFIED` |
| PARTIAL_USABLE + screen stage 3 fail (low ADX) | 커스텀 fixture | `SCREEN_FAILED` |
| OK + screen pass + qualify check 6 fail (negative Sharpe) | 커스텀 fixture | `QUALIFY_FAILED` |
| OK + bars=100 (stage 5 fail) | F5 fixture | `SCREEN_FAILED` |
| OK + listing_age=None + min_listing_age threshold hit | F6 fixture | `SCREEN_FAILED` |
| TransformResult(decision=OK, screening_input=None) | 방어 케이스 | `DATA_REJECTED` |

---

```
Fail-Closed Matrix v1.0
5 failure points, 4 verdicts, 0 silent failures
```
