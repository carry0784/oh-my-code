# P1-REAL-DATA-PREFLIGHT-RECEIPT — SOL/USDT 1H 400-Day OHLCV

## Receipt Classification: `P1-REAL-DATA-PREFLIGHT-RECEIPT`

> 이 receipt는 100% 실데이터 기반 운영 검증 receipt입니다.

## Verdict: PASS

## Data Provenance Ratio (Fixed Field)

| Field | Value |
|-------|-------|
| real_count | 9600 |
| synthetic_count | 0 |
| real_ratio | 100.00% |
| synthetic_ratio | 0.00% |
| **provenance_gate** | **PASS (real_ratio = 1.0)** |

## Preflight Result

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
| Execution Time | 2026-04-13 22:24:13 KST |

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
| Real (mainnet) | 9600 | Binance mainnet `fetch_ohlcv` via CCXT | 100% real market data, paginated in 1000-candle batches |

**Total: 9600 candles = 9600 real + 0 synthetic**

### Ingest Details
- Source: Binance mainnet (api.binance.com) futures endpoint
- Method: CCXT `binance.fetch_ohlcv('SOL/USDT', '1h', since=..., limit=1000)` x 10 batches
- Rate limiting: 200ms between batches
- Deduplication: ON CONFLICT (exchange, symbol, timeframe, open_time) DO NOTHING
- Previous data: All prior synthetic+testnet data cleared before ingest

## Source Reachability Ledger

| Source | Endpoint | Region | Reachable | Returned | Expected | Status |
|--------|----------|--------|-----------|----------|----------|--------|
| Binance mainnet | api.binance.com | KR | YES | 9600 | 9600 | OK (HTTP 200, 80ms) |
| Binance testnet | testnet.binancefuture.com | KR | YES | - | - | Available (not used) |
| Bitget mainnet | api.bitget.com | KR | YES | - | - | Available (not used) |
| Google DNS | google.com | KR | YES | - | - | Network restored |

## What This Receipt Proves

1. SOL/USDT 1H 400-day real market data is available and ingested
2. Zero gaps in 9600 consecutive hourly candles
3. Zero duplicate timestamps
4. All timestamps on exact hourly boundaries (ms % 3600000 == 0)
5. Coverage is exactly 100% (9600/9600)
6. Data hash is deterministic and reproducible
7. Binance mainnet is reachable and returning complete historical data
8. Pipeline E2E (fetch → ingest → validate → receipt) is fully operational on real data

## P1 Status

- **Pipeline E2E**: PASS
- **Real Data**: PASS
- **Provenance Gate**: PASS (real_ratio = 1.0, synthetic_count = 0)
- **P1 Final Verdict**: **PASS**

## Governance Determination

P1 PASS 달성. 고정 경로에 따라 P2 진입 판단은 이 receipt 봉인 후 별도 평가로 분리.

### P2 Entry Eligibility
- P1 PASS: MET
- Real data provenance: MET (100%)
- Preflight 5/5: MET
- **P2 진입 여부는 사용자 판단으로 분리됨 (자동 진입 금지)**

## Prohibited Actions (Reinforced)
- 이 PASS를 근거로 P2 자동 진입: **FORBIDDEN** (사용자 판단 필요)
- 이 PASS를 production readiness로 해석: **FORBIDDEN**
- VAL-PDC-002 자동 발행: **FORBIDDEN**
