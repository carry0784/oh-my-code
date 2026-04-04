# K-Dexter Operational Baseline Card

> **Date**: 2026-03-30
> **Version**: 1.0
> **Status**: BASELINE LOCKED

---

## System Architecture (1-page summary)

```
Signal
  │
  ▼
[Tier 1] GovernanceGate.pre_check()          10 checks
  │
  ▼
[Tier 2] Agent ActionLedger                   4 checks  │ AP-* │ AR-*
  │
  ▼
[Tier 3] ExecutionLedger                      5 checks  │ EP-* │ ER-*
  │         execution_ready = @property
  ▼
[Tier 4] SubmitLedger                         6 checks  │ SP-* │ SR-*
  │         submit_ready = @property
  ▼
[External] OrderExecutor                      dry_run default │ OX-*
  │
  ▼
Exchange API (Binance, UpBit, Bitget, KIS, Kiwoom)
```

---

## Supported Exchanges (SSOT)

| Category | Exchanges |
|----------|----------|
| Crypto | Binance, UpBit, Bitget |
| Stock | KIS (한국투자증권), Kiwoom (키움증���) |
| **Total** | **5** |

Defined in: `app/core/config.py` → `SUPPORTED_EXCHANGES_ALL`

---

## Guard Checks by Tier

| Tier | Checks | Total |
|------|--------|-------|
| GovernanceGate | FORBIDDEN, MANDATORY, COMPLIANCE, DRIFT, CONFLICT, PATTERN, BUDGET, TRUST, LOOP, LOCK | 10 |
| Agent | RISK_APPROVED, GOVERNANCE_CLEAR, SIZE_BOUND, COST_BUDGET | 4 |
| Execution | AGENT_RECEIPTED, GOVERNANCE_CLEAR, COST_WITHIN_BUDGET, LOCKDOWN_CHECK, SIZE_FINAL_CHECK | 5 |
| Submit | EXEC_RECEIPTED, GOVERNANCE_FINAL, COST_FINAL, LOCKDOWN_FINAL, EXCHANGE_ALLOWED, SIZE_SUBMIT_CHECK | 6 |
| **Total** | | **25** |

---

## Derived Properties

| Property | Location | Condition |
|----------|----------|-----------|
| `execution_ready` | ExecutionLedger | `status == "EXEC_RECEIPTED"` |
| `submit_ready` | SubmitLedger | `status == "SUBMIT_RECEIPTED"` |

Both are `@property` — cannot be directly assigned.

---

## Test Summary

| Suite | Tests |
|-------|-------|
| GovernanceGate | 29 |
| Agent ActionLedger | 31 |
| Execution Ledger | 32 |
| Submit Ledger | 34 |
| Order Executor | 23 |
| 4-Tier Board | 26 |
| Cleanup Policy | 31 |
| Orphan Detection | 33 |
| Cleanup Simulation | 42 |
| Observation Summary | 28 |
| Operator Decision | 29 |
| Decision Card Visual | 36 |
| Decision Schema Typing | 40 |
| Threshold Calibration | 33 |
| Stale Contract | 44 |
| Observation Summary Schema | 43 |
| Review Volume | 46 |
| Market Feed + SSOT | 22 |
| 4-State Regression | 14 |
| Governance Monitor | 11 |
| **Control Total** | **614** |
| **Full Suite** | **2845** |

---

## Seal Documents

| Document | Prohibitions |
|----------|-------------|
| Skill Loop Seal | P-01~P-06 |
| Agent Boundary Seal | AB-01~AB-06 |
| Execution Boundary Seal | EB-01~EB-07 |
| Submit Boundary Seal | SB-01~SB-08 |
| OKX Removal Seal | Whitelist fixed |
| Order Executor Design | OE-01~OE-07 (safety, not seal) |

---

## Key Safety Defaults

| Setting | Value | Reason |
|---------|-------|--------|
| `dry_run` | `True` (default) | Prevents accidental real execution |
| `governance_enabled` | `True` (default) | Gate=None → RuntimeError |
| Unsupported exchange | `ValueError` | Explicit rejection with supported list |

---

## Next Priorities

| # | Task | Status |
|---|------|--------|
| 1 | Dashboard 4-Tier Board | **COMPLETE** (26 tests) |
| 2 | Orphan/Stale Cleanup Policy | **COMPLETE** (31 tests, C-GO) |
| 3 | Orphan Detection Policy | **COMPLETE** (33 tests, C-GO) |
| 4 | Cleanup Simulation Policy | **COMPLETE** (42 tests, C-GO) |
| 5 | Dashboard Observation Upgrade | **COMPLETE** (28 tests, C-GO) |
| 6 | Operator Decision Layer | **COMPLETE** (29 tests, C-GO) |
| 7 | Rejected/Unsupported Audit | PLANNED |
| 8 | Decision/Board 시각화 고도화 | **COMPLETE** (36 tests, C-GO) |
| 9 | Pre-existing 12 fail 정리 | **COMPLETE** (0 fail achieved, C-GO) |
| 10 | Decision Schema Typing | **COMPLETE** (40 tests, C-GO) |
| 11 | Threshold Calibration | **COMPLETE** (33 tests, C-GO) |
| 12 | Stale Helper Consolidation | **COMPLETE** (44 tests, C-GO) |
| 13 | Observation Summary Schema | **COMPLETE** (43 tests, C-GO) |
| 14 | REVIEW Volume Observation | **COMPLETE** (39 tests) |
| 15 | Real execution integration test | PLANNED |

---

> Baseline locked: 2026-03-30 (updated)
> Full suite: 2845 passed, 0 failed, 0 warnings
> Control tests: 614 passed
> 4-Tier Seal Chain: COMPLETE
> Execution Layer: COMPLETE
> Observation Layer: COMPLETE (stale + orphan + cleanup simulation + observation summary)
> Operator Decision Layer: COMPLETE (posture + risk + reason chain, C-GO)
> Decision Card Visual: COMPLETE (36 tests, C-GO)
> Pre-existing Fail Cleanup: COMPLETE (12 → 0, C-GO)
> Decision Schema Typing: COMPLETE (40 tests, C-GO)
> Threshold Calibration: COMPLETE (33 tests, C-GO) — 2x→1.5x band, 3x prolonged
> Stale Helper Consolidation: COMPLETE (44 tests) — central contract, drift detection
> Pydantic Warning Zero: COMPLETE (instance→class model_fields access)
> Observation Summary Schema: COMPLETE (43 tests) — typed Layer 4 contract
> REVIEW Volume Observation: COMPLETE (46 tests) — factual volume/distribution/density + board integration
> A/B/C Harness: 12 cycles completed, 405 new tests, ALL GO
> Baseline: ZERO FAIL, ZERO WARNING (2845 PASS / 0 FAIL / 0 WARNING)
