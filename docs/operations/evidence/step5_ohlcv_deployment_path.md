# OhlcvHistory Deployment Path — Step 5 G1

## Model Identity

| Field | Value |
|-------|-------|
| Table | `ohlcv_history` |
| Model | `app.models.ohlcv_history.OhlcvHistory` |
| Migration | `026_ohlcv_history_backtest_plane.py` |
| Unique Constraint | `uq_ohlcv_canonical_slot` (exchange, symbol, timeframe, open_time) |
| PR | #93 (feat/ppf-validation-chain-p3) |

## Deployment Steps

### 1. Migration Apply

```bash
alembic upgrade head   # applies 026 + 027
```

- Creates `ohlcv_history` table
- Creates `uq_ohlcv_canonical_slot` unique constraint
- Creates `ix_ohlcv_lookup` composite index
- No data migration (fresh table)

### 2. Data Ingestion Path

```
Exchange API (Binance) → HistoryDataManager.ingest_candles() → ohlcv_history
```

- Idempotent: ON CONFLICT DO NOTHING
- Bulk insert with UUID generation
- Requires `AsyncSession` from caller

### 3. Replay Path

```
ohlcv_history → HistoryDataManager.get_replay_candles() → BacktestingEngine/FullCycleBacktester
```

- Read-only, sorted by open_time ASC
- Returns `list[list]` compatible with `strategy.analyze(ohlcv)`

### 4. Coverage Validation Path

```
ohlcv_history → HistoryDataManager.check_coverage() → CoverageReport
ohlcv_history → OhlcvPreflightValidator.run() → PreflightResult
```

## Current Data State

| Symbol | Exchange | Timeframe | Candles | Coverage | Status |
|--------|----------|-----------|---------|----------|--------|
| SOL/USDT | binance | 1h | 9600 | 100% | P2 baseline sealed |

## Rollback Plan

```bash
alembic downgrade -1   # drops ohlcv_history table
```

No data preservation needed — backtest data is re-ingestable from exchange API.

## Dependency Chain

```
026_ohlcv_history_backtest_plane.py
  └── ohlcv_history table
      ├── HistoryDataManager (ingest/query/coverage)
      ├── OhlcvPreflightValidator (5-check validation)
      ├── FullCycleBacktester (4-segment replay)
      └── PPFIntegratedBacktester (bar-by-bar PPF replay)
```
