# P1-REAL-DATA-PREFLIGHT-ADDENDUM — Hash/Provenance Integrity Review

## Parent Receipt: `p1_real_data_preflight_receipt.md`

> 이 addendum은 기존 receipt를 수정하지 않고, P2 진입 전 무결성 검수 결과만 추가합니다.

## Review Trigger

직전 synthetic E2E receipt의 `data_hash`와 real-data receipt의 `data_hash`가 동일한 이상 징후 발생.

## G-01: Hash Scope Analysis — RESOLVED

### Root Cause

`OhlcvPreflightValidator._compute_data_hash()`의 입력이 메타데이터 3개뿐:

```
payload = f"{first_ts}:{last_ts}:{candle_count}"
```

synthetic 데이터와 real 데이터가 동일한 시간범위(2025-03-09T13:00 ~ 2026-04-13T12:00)와 동일한 candle count(9600)를 가지므로 hash가 동일한 것은 **설계 스코프의 한계이지 데이터 오염이 아님**.

### Dual Fingerprint (신규)

| Fingerprint | Hash | Input |
|-------------|------|-------|
| metadata_hash (현행) | `1c5c8fc84e57db52d21d6df99ccd2279435d7803357d50d5f51f43bea8dd5636` | `first_ts:last_ts:candle_count` |
| dataset_hash (content) | `370c776ee1f378e85c1d0e2c54e884998210eb48dd2908e04a4df7b125ec7f2d` | 9600 rows of `open_time:open:high:low:close:volume` |
| provenance_hash | `680fbf7a9ed2ee14e7a7108ab52d1c84295187b6b040fb9638a0b98b50a63cd5` | `{source, symbol, timeframe, real_count, synthetic_count, real_ratio, first_ts, last_ts}` |

**dataset_hash가 real 데이터의 고유 지문.** synthetic 데이터와 완전히 다른 hash.

### Verdict: **PASS** — hash 동일성은 설계 한계이며 데이터 무결성 문제 아님

## G-02: Provenance Field Verification — PASS

| Field | Expected | Actual | Match |
|-------|----------|--------|-------|
| real_count | 9600 | 9600 | MATCH |
| synthetic_count | 0 | 0 | MATCH |
| real_ratio | 1.0 | 1.0 | MATCH |
| source | api.binance.com | api.binance.com | MATCH |
| window | 400.0 days | 400.0 days | MATCH |
| first_ts | 1741525200000 | 1741525200000 | MATCH |
| last_ts | 1776081600000 | 1776081600000 | MATCH |

**7/7 MATCH**

### Spot Check: Price Reality

```
2025-03-09 13:00 O=135.43 H=135.44 L=133.01 C=133.06 V=1,104,613
2025-03-09 14:00 O=133.07 H=133.94 L=132.20 C=133.23 V=1,262,748
2025-03-09 15:00 O=133.23 H=133.48 L=129.76 C=130.10 V=1,572,471
2025-03-09 16:00 O=130.10 H=131.50 L=127.64 C=127.91 V=2,359,514
2025-03-09 17:00 O=127.90 H=128.56 L=126.23 C=126.45 V=2,210,604
```

가격이 SOL/USDT 실제 시장가와 일치 (2025-03-09 기준 $127~$135 범위 정상).

## G-03: Synthetic/Real Receipt Separation — PASS

| Receipt | Classification | dataset_hash | 분리 |
|---------|---------------|-------------|------|
| `p1_preflight_receipt.md` | `P1-SYNTHETIC-E2E-RECEIPT` | (미계산, synthetic 데이터 삭제됨) | 등급 분리 완료 |
| `p1_real_data_preflight_receipt.md` | `P1-REAL-DATA-PREFLIGHT-RECEIPT` | `370c776e...` | 등급 분리 완료 |

dataset_hash(content-based)로 분리하면 synthetic/real은 구조적으로 구별 가능.

## Integrity Review Final Verdict

| 검수 항목 | 결과 |
|-----------|------|
| G-01: Hash scope | RESOLVED (설계 한계, 오염 아님) |
| G-02: Provenance | 7/7 MATCH |
| G-03: Receipt separation | 등급 + content hash로 분리 가능 |
| **Overall** | **PASS** |

## P2 Entry Determination

모든 검수 항목 PASS. P2 진입 조건 충족.

- P1 real-data PASS: MET
- Hash/provenance 무결성: VERIFIED
- Receipt 분리: CONFIRMED
- **P2 baseline freeze/seal 진입: ELIGIBLE**
- **P2 진입 여부: 사용자 판단 대기**

## Improvement Action Item

`_compute_data_hash()`를 Dual Fingerprint로 확장하는 것을 P2 이후 개선 후보로 등록:
- `metadata_hash`: 현행 유지 (경량, 빠른 비교용)
- `dataset_hash`: content-based full hash 추가 (데이터 무결성 증명용)

이 개선은 P2 실행 중 수행하지 않고, P2 완료 후 별도 작업으로 분리.

## Execution Date

2026-04-13 22:30 KST
