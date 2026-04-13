# P2 Baseline Freeze/Seal Receipt — SOL/USDT 1H PPF Baseline

## Receipt Classification: `P2-BASELINE-FREEZE-SEAL-RECEIPT`

## Verdict: PASS — Baseline Frozen, Sealed, Verified

## Freeze Manifest

| Field | Value |
|-------|-------|
| baseline_id | `59510964-a975-4561-863d-e22584353eda` |
| source | Binance mainnet (api.binance.com) |
| symbol | SOL/USDT |
| timeframe | 1h |
| candle_count | 9600 |
| real_count | 9600 |
| synthetic_count | 0 |
| coverage_ratio | 1.0 |
| first_ts | 1741525200000 (2025-03-09T13:00:00Z) |
| last_ts | 1776081600000 (2026-04-13T12:00:00Z) |

### Triple Hash (Hash Priority Rule)

| Priority | Type | Hash | Purpose |
|----------|------|------|---------|
| 1 (Primary) | dataset_hash | `370c776ee1f378e85c1d0e2c54e884998210eb48dd2908e04a4df7b125ec7f2d` | OHLCV 본문 무결성 주지문 |
| 2 (Primary) | provenance_hash | `680fbf7a9ed2ee14e7a7108ab52d1c84295187b6b040fb9638a0b98b50a63cd5` | 출처/구성 무결성 주지문 |
| 3 (Auxiliary) | metadata_hash | `1c5c8fc84e57db52d21d6df99ccd2279435d7803357d50d5f51f43bea8dd5636` | 보조 지문 (first_ts:last_ts:count) |

### Seal Hashes

| Hash | Value |
|------|-------|
| seal_hash | `66727781ec0b309537eee69ac2ffd5b52556ef69a7b55e7c77649c73a7fe9062` |
| preflight_hash | `1c5c8fc84e57db52d21d6df99ccd2279435d7803357d50d5f51f43bea8dd5636` |

## Phase A Backtest Metrics

| Metric | Value |
|--------|-------|
| total_bars | 9600 |
| evaluated_bars | 9537 |
| warmup_skipped | 63 |
| allow_count | 0 |
| deny_count | 9537 |
| deny_rate | 1.0000 (100%) |
| novelty_count | 47 |
| novelty_rate | 0.004928 (0.49%) |
| fpr | 0.6596 (65.96%) |
| tp_count | 16 |
| fp_count | 31 |
| unresolved_count | 0 |
| ppf_params_hash | `default_params` (SHA-256 truncated) |
| replay_elapsed | 1922s (32min) |

### State Distribution

| State | Count | Ratio |
|-------|-------|-------|
| IDLE | 3188 | 33.4% |
| CANDIDATE | 5050 | 52.9% |
| WATCH | 1299 | 13.6% |

### Deny Reason Distribution

| Reason | Count | Ratio |
|--------|-------|-------|
| TREND_MISALIGN | 3663 | 38.4% |
| RISK_FILTER_FAIL | 2311 | 24.2% |
| UNKNOWN | 1838 | 19.3% |
| VOLUME_WEAK | 1387 | 14.5% |
| RR_FAIL | 201 | 2.1% |
| PATH_QUALITY_FAIL | 90 | 0.9% |
| NOVELTY_BRAKE | 47 | 0.5% |

## Lifecycle Status

| Field | Value |
|-------|-------|
| frozen | True |
| frozen_at | 2026-04-13T15:09:37Z |
| frozen_by | P2_operator |
| seal_hash | verified (stored == computed) |
| phase_b_started | False |
| invalidated | False |

## Execution Log

| Step | Timestamp | Status |
|------|-----------|--------|
| P1 Real Data Ingest | 2026-04-13 22:23 KST | 9600 candles ingested |
| P1 Preflight Validation | 2026-04-13 22:24 KST | 5/5 PASS |
| P1 Addendum (Hash Review) | 2026-04-13 22:30 KST | G-01/G-02/G-03 PASS |
| Phase A PPF Backtest | 2026-04-13 23:28~00:09 KST | 1922s, baseline persisted |
| P2 Freeze | 2026-04-14 00:09 KST | frozen=True, seal computed |
| P2 Seal Verify | 2026-04-14 00:09 KST | stored == computed, VALID |

## Baseline Interpretation Notes

- **deny_rate = 100%**: PPF gate denied all 9537 evaluated bars. This is expected in Phase A replay with `risk_filter_pass=False` — the gate's conservative behavior is by design.
- **novelty_count = 47**: 47 bars triggered the novelty brake across 400 days, approximately 1 per 8.5 days.
- **fpr = 65.96%**: Of 47 novelty events, 31 were false positives. This is the baseline measurement for Phase B comparison.
- **allow_count = 0**: No bars reached D6_EXECUTE_READY state. This is consistent with the gate evaluation running without a preceding strategy signal (risk_filter_pass=False).

## State Transition

```
P1_REALDATA_PASS
→ P1_ADDENDUM_PASS
→ P2_BASELINE_FREEZE_STARTED (Phase A backtest completed, baseline persisted)
→ P2_BASELINE_FROZEN (freeze() called, seal_hash computed)
→ P2_BASELINE_SEALED (seal_hash stored)
→ P2_BASELINE_VERIFIED (verify_seal() = VALID)
→ SHADOW_READY
```

## Receipt Chain

1. `p1_preflight_receipt.md` — P1-SYNTHETIC-E2E-RECEIPT (pipeline smoke)
2. `p1_real_data_preflight_receipt.md` — P1-REAL-DATA-PREFLIGHT-RECEIPT (real data PASS)
3. `p1_real_data_preflight_addendum.md` — Hash/Provenance integrity review
4. **`p2_baseline_freeze_seal_receipt.md`** — P2-BASELINE-FREEZE-SEAL-RECEIPT (this document)

## Prohibited Actions (P2 Complete, Still Enforced)

- Comparator 실행: **FORBIDDEN**
- VAL-PDC-002 발행: **FORBIDDEN**
- 신규 모듈 추가: **FORBIDDEN**
- baseline 수정: **FORBIDDEN** (frozen, immutable)
- P2 PASS를 production readiness로 해석: **FORBIDDEN**
- metadata_hash만을 유일한 봉인 지문으로 사용: **FORBIDDEN**

## Next Eligible Action

P2 complete. 상태는 `SHADOW_READY`. 다음 단계는 P3 shadow accumulation이나, 진입은 사용자 판단으로 분리됨.
