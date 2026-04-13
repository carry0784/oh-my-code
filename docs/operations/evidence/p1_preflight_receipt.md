# P1-SYNTHETIC-E2E-RECEIPT — SOL/USDT 1H 400-Day OHLCV

## Receipt Classification: `P1-SYNTHETIC-E2E-RECEIPT`

> 이 receipt는 운영 승인 receipt가 아니라 synthetic E2E 검증 receipt입니다.
> Real-data receipt는 별도로 `P1-REAL-DATA-PREFLIGHT-RECEIPT` 등급으로 발행되어야 합니다.

## Verdict: CONDITIONAL PASS (Synthetic E2E)

## Data Provenance Ratio (Fixed Field)

| Field | Value |
|-------|-------|
| real_count | 290 |
| synthetic_count | 9310 |
| real_ratio | 3.02% |
| synthetic_ratio | 96.98% |
| **provenance_gate** | **FAIL (real_ratio < 1.0 → P2 FORBIDDEN)** |

| Field | Value |
|-------|-------|
| Symbol | SOL/USDT |
| Exchange | binance |
| Timeframe | 1h |
| Candle Count | 9600 |
| Coverage | 100.00% |
| Days Covered | 400.0 |
| Gap Count | 0 |
| Duplicate Count | 0 |
| Misaligned Count | 0 |
| First Timestamp | 2025-03-09T13:00:00Z (1741525200000) |
| Last Timestamp | 2026-04-13T12:00:00Z (1776081600000) |
| Data Hash | `1c5c8fc84e57db52d21d6df99ccd2279435d7803357d50d5f51f43bea8dd5636` |
| Execution Time | 2026-04-13 22:10:29 KST |

## Per-Check Results

| Check | Result |
|-------|--------|
| symbol_lock | PASS |
| coverage | PASS |
| gap_count | PASS |
| no_duplicates | PASS |
| timestamp_alignment | PASS |

## Data Provenance

| Segment | Candles | Source | Notes |
|---------|---------|--------|-------|
| Real (testnet) | 290 | Binance testnet `fetch_ohlcv` | ~12 days, most recent candles |
| Synthetic | 9310 | numpy random walk (seed=42, base=120, vol=1.5%) | Pipeline E2E validation only |

**Total: 9600 candles = 290 real + 9310 synthetic**

### Synthetic Data Parameters
- Generator: numpy random walk
- Random seed: 42 (deterministic)
- Base price: 120.0 USDT
- Volatility: 1.5% per candle
- Volume: random uniform [100, 10000]
- OHLC: derived from close with random wick offsets

## Source Reachability Ledger

| Source | Endpoint | Region | Reachable | Returned | Expected | Failure |
|--------|----------|--------|-----------|----------|----------|---------|
| Binance testnet | testnet.binancefuture.com | KR | YES | 290 | 9600 | Testnet data limited (~12 days) |
| Binance mainnet | api.binance.com | KR | NO | 0 | 9600 | DNS resolution failure (regional block) |
| Binance alt 1-4 | api1-4.binance.com | KR | NO | 0 | 9600 | DNS resolution failure |
| Bitget mainnet | api.bitget.com | KR | NO | 0 | 9600 | DNS resolution failure |
| OKX mainnet | okx.com | KR | NO | 0 | 9600 | DNS resolution failure |
| All external DNS | * | KR | NO | - | - | Complete external internet isolation |

## Governance Determination

### What this receipt proves:
1. Preflight validator pipeline runs end-to-end correctly
2. All 5 checks (symbol_lock, coverage, gap_count, no_duplicates, timestamp_alignment) function as designed
3. HistoryDataManager ingest + check_coverage integration works
4. Data hash is deterministic and reproducible
5. Fail-closed gate logic correctly returns PASS when all criteria are met

### What this receipt does NOT prove:
1. Real market data quality (96.97% of data is synthetic)
2. Actual SOL/USDT price history integrity
3. Exchange data source reliability over 400 days
4. Gap patterns in real market data
5. Data alignment with actual exchange trading sessions

### P1 Status: CONDITIONAL PASS

- **Pipeline E2E**: PASS (validator + ingest + coverage + all checks operational)
- **Real Data**: PENDING (blocked by network isolation)
- **P2 Entry**: FORBIDDEN (requires real data P1 PASS)

### Next Action Required:
- When external network access is restored:
  1. Re-run P1 with real exchange data (Bitget mainnet recommended as 1st candidate)
  2. Obtain fresh P1 receipt with 100% real data provenance
  3. Only then evaluate P1→P2 transition

## Prohibited Actions (Reinforced)
- P2 (baseline freeze/seal) entry on synthetic data: **FORBIDDEN**
- Baseline freeze on current dataset: **FORBIDDEN**
- VAL-PDC-002 issuance: **FORBIDDEN**
- Interpreting this CONDITIONAL PASS as production readiness: **FORBIDDEN**
