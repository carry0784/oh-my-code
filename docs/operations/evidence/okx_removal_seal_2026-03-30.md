# OKX Exchange Removal Seal

> **Status**: SEALED
> **Date**: 2026-03-30
> **Type**: Exchange Whitelist Consolidation
> **Sealed By**: K-Dexter Governance Process

---

## 1. Purpose

This document seals the removal of OKX exchange from the K-Dexter codebase and establishes the **Supported Exchanges Whitelist** as a fixed SSOT (Single Source of Truth).

---

## 2. Supported Exchanges (SSOT)

Defined in `app/core/config.py`:

| Category | Exchange | Config Key |
|----------|----------|-----------|
| CRYPTO | Binance | `SUPPORTED_EXCHANGES_CRYPTO` |
| CRYPTO | UpBit | `SUPPORTED_EXCHANGES_CRYPTO` |
| CRYPTO | Bitget | `SUPPORTED_EXCHANGES_CRYPTO` |
| STOCK | KIS (한국투자증권) | `SUPPORTED_EXCHANGES_STOCK` |
| STOCK | Kiwoom (키움증권) | `SUPPORTED_EXCHANGES_STOCK` |

**Total: 5 exchanges. Any exchange not in this list is UNSUPPORTED.**

---

## 3. Removal Inventory

### 3.1 Code (Previously Removed)

OKX was already removed from core code prior to this session:
- `exchanges/okx.py` -- **DELETED** (prior session)
- `app/exchanges/okx.py` -- **DELETED** (prior session)
- `exchanges/factory.py` -- OKX branch already removed (prior session)
- `app/core/config.py` -- OKX fields already removed (prior session)

### 3.2 This Session -- Remaining References Removed

| Location | Change | Count |
|----------|--------|-------|
| Test `_STUB_MODULES` lists | Removed `"app.exchanges.okx"` | 28 files |
| `.env` | Removed `OKX_SANDBOX=false` | 1 |
| `.env.production` | Removed `OKX_SANDBOX=false` | 1 |
| `.env.staging` | Removed `OKX_SANDBOX=true` | 1 |
| `exchanges/__pycache__/okx.cpython-314.pyc` | **DELETED** | 1 |

### 3.3 Intentionally Retained (Audit Trail)

| File | Reason |
|------|--------|
| `docs/ai_governance_ops_baseline.md` | Historical record of removal |
| `docs/checkpoint_2026-03-29.md` | Audit checkpoint |
| `docs/operations/evidence/b17_receipt_2026-03-25.md` | Receipt evidence (RESOLVED) |
| Test files (`test_market_feed.py`) | "okx not in list" assertions (enforcement) |

---

## 4. SSOT Architecture

### Before (Scattered)
```
market_feed_service.py: _SUPPORTED_EXCHANGES = ["binance", "upbit", "bitget"]
factory.py: elif "okx": ... elif "binance": ...
config.py: okx_api_key, okx_api_secret, ...
.env: OKX_SANDBOX=false
```

### After (Centralized SSOT)
```
config.py:
  SUPPORTED_EXCHANGES_CRYPTO = ("binance", "upbit", "bitget")
  SUPPORTED_EXCHANGES_STOCK  = ("kis", "kiwoom")
  SUPPORTED_EXCHANGES_ALL    = CRYPTO + STOCK

market_feed_service.py: _SUPPORTED_EXCHANGES = list(SUPPORTED_EXCHANGES_CRYPTO)
factory.py: _FACTORY_REGISTRY = {name: Class for each supported}
```

### Fail-Closed Behavior
```python
# factory.py -- unsupported exchange raises explicit error
raise ValueError(
    f"Unsupported exchange: '{exchange_name}'. "
    f"Supported: {sorted(_FACTORY_REGISTRY.keys())}. "
    f"If this exchange was previously supported, it has been removed."
)
```

- No silent fallback
- No None auto-replacement
- Explicit error with supported list

---

## 5. Test Enforcement

| Test | What It Verifies |
|------|-----------------|
| `test_ssot_crypto_list` | CRYPTO = {binance, upbit, bitget} |
| `test_ssot_stock_list` | STOCK = {kis, kiwoom} |
| `test_ssot_all_list` | ALL = 5 exchanges |
| `test_okx_not_in_any_list` | OKX excluded from SSOT |
| `test_factory_source_has_no_okx` | Factory source has no OKX reference |
| `test_factory_registry_no_okx` | Factory registry has no OKX + has Unsupported error |
| `test_supported_exchanges_crypto_only` | Market feed uses CRYPTO only, excludes okx/kis/kiwoom |

---

## 6. Residual OKX References After Cleanup

| Category | Count | Status |
|----------|-------|--------|
| Code (`app/`, `exchanges/`, `workers/`) | 0 | CLEAN |
| Config (`.env*`) | 0 | CLEAN |
| Test `_STUB_MODULES` | 0 | CLEAN |
| Test enforcement (intentional "okx" in assertions) | 5 | EXPECTED |
| Documentation (audit trail) | 4 | RETAINED |

---

## 7. Prohibited Changes

1. Adding OKX back without governance approval
2. Adding any exchange without updating `SUPPORTED_EXCHANGES_*` in config.py
3. Silent fallback for unsupported exchanges (must raise ValueError)
4. Hardcoding exchange lists outside the SSOT (all must reference config.py)
5. Re-introducing OKX env vars without corresponding code support

---

## 8. Verification Checklist

- [x] `grep -ri "okx" app/ exchanges/ workers/ --include="*.py"` = 0 results
- [x] `grep -ri "okx" .env .env.production .env.staging` = 0 results
- [x] `grep -ri "app.exchanges.okx" tests/` = 0 results (from _STUB_MODULES)
- [x] Factory raises ValueError for "okx"
- [x] SSOT defined in single location (config.py)
- [x] All tests pass (excluding pre-existing test_c13 issue)

---

> Sealed: 2026-03-30
> Related: ai_governance_ops_baseline.md (OKX removal history)
> Next review: Upon exchange addition/removal request
