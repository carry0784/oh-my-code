# CR-019: Cold-Start Observation Expansion Pack

Effective: 2026-05-08
Status: **SCOPED — awaiting A approval for implementation**
Author: B (Implementer)
CR-ID: CR-019
Category: L2 (conditional — code touches read-only observation layer)
Baseline check required: Yes (832/0/0)

---

## 1. Problem Statement

The 4-tier board has operated in cold-start state for 30+ days:

| Observation | Cold-Start Value | Meaning |
|------------|-----------------|---------|
| `TierLatency.measured` | False (all 4 tiers) | No proposal timestamps collected |
| `LatencyDensitySignal.has_measurements` | False | No latency data available |
| `MetricComparison.insufficient_data` | True (all 4 metrics) | Not enough history for comparison |
| `TrendDensitySignal.trend_available` | False | Cannot compare 60m windows |
| `stale_total` | 0 | No proposals exist to become stale |
| `orphan_total` | 0 | No proposals exist to become orphaned |

This is correct behavior — no live trading data flows through the
pipeline, so no observations can be made. The board accurately
reports "nothing to observe."

---

## 2. Expansion Scope (Read-Only Only)

### 2.1 What This Pack Covers

Connecting the observation layer to live data sources so that board
fields transition from cold-start defaults to actual measurements.

| Area | Current | Target |
|------|---------|--------|
| Latency | measured=False (all tiers) | measured=True when proposals exist |
| Trend | trend_available=False | trend_available=True when snapshot buffer fills |
| Freshness | stale_total=0 | stale_total reflects actual staleness |
| Orphans | orphan_total=0 | orphan_total reflects actual orphan state |

### 2.2 What This Pack Does NOT Cover

| Excluded | Reason | Level |
|----------|--------|-------|
| action_allowed changes | Safety invariant | L3 prohibited |
| Write paths | Read-only seal | L3 prohibited |
| Prediction language | Red line 4 | L3 prohibited |
| New board fields | Sealed at 24 | L3 prohibited |
| New observation cards | Free expansion terminated | L3 prohibited |
| Alert triggers | Red line 10 | L3 prohibited |
| Execution path changes | Safety boundary | L3 prohibited |

---

## 3. Architecture Analysis

### 3.1 Latency Observation Connection

**Current flow** (`build_latency_observation()` in `four_tier_board_service.py`):
```
action_ledger → TierLatency(tier=1)
execution_ledger → TierLatency(tier=2)
submit_ledger → TierLatency(tier=3)
order_executor → TierLatency(tier=4)
```

**Cold-start reason**: All ledgers are `None` when passed to the function
because no proposals have been created. The function correctly returns
`measured=False` for all tiers.

**To activate**: Proposals must flow through the pipeline. Each ledger
records timestamps. When `sample_size > 0`, `measured` becomes `True`.

**No code change needed** for this transition — the existing code already
handles the warm-start case. The transition happens naturally when live
trading begins.

### 3.2 Trend Observation Connection

**Current flow** (`build_trend_observation()` with `snapshot_buffer`):
```
snapshot_buffer → MetricComparison (4 metrics)
                → TrendDensitySignal
```

**Cold-start reason**: The `snapshot_buffer` is in-memory only and starts
empty on each process restart. It needs ≥5 snapshots per window (60 min)
to declare `trend_available=True`.

**To activate**: The Celery beat scheduler must be running to periodically
capture board snapshots. After ~2 hours of uptime with beat running,
trends will naturally populate.

**No code change needed** — the existing architecture already supports
warm-start. The transition is operational (start the scheduler), not code.

### 3.3 Freshness/Stale Detection

**Current flow**: `_collect_stale_by_tier()` checks each proposal's
`created_at` against `stale_threshold_seconds`.

**Cold-start reason**: No proposals exist, so nothing can become stale.

**To activate**: Submit proposals through the pipeline. Stale detection
activates automatically.

### 3.4 Orphan Detection

**Current flow**: `detect_orphans()` checks cross-tier proposal
consistency (proposal exists in tier N but not in tier N+1).

**Cold-start reason**: No proposals exist, so no orphans possible.

**To activate**: Submit proposals. Orphan detection activates automatically.

---

## 4. Key Finding

**The observation layer is already fully implemented for warm-start.**

The cold-start state is not a code gap — it is an operational state.
The transition from cold-start to warm-start requires:

1. **Live trading data** (proposals flowing through the pipeline)
2. **Celery beat running** (for snapshot buffer and trend calculation)
3. **Process uptime** (~2 hours for trend window to fill)

No code changes to the observation layer are needed to resolve cold-start.

---

## 5. Visibility Enhancement Opportunities (L2)

While the core observation layer needs no changes, these L2 enhancements
could improve operator visibility during cold-start:

| Enhancement | Description | Category |
|-------------|-------------|----------|
| Cold-start indicator | Add `cold_start: bool` field to board meta | L3 (new field) — BLOCKED |
| Uptime display | Show process uptime in `generated_at` area | L2 — possible |
| Snapshot buffer status | Show buffer fill level for trend | L2 — possible |
| Last proposal timestamp | Show when last proposal was seen | L2 — possible |

**Recommendation**: All useful enhancements require either new board
fields (L3, prohibited) or modifying existing field semantics. Given the
sealed state, the most practical approach is to **wait for live trading
activation** rather than adding cold-start-specific indicators.

---

## 6. Implementation Decision

### Option A: No Code Changes (Recommended)

The observation layer is complete. Cold-start resolves when:
- Live trading data flows through the pipeline
- Celery infrastructure is fully running

**Advantages**: Zero risk, 832/0/0 preserved, no sealed system changes.

### Option B: Dashboard-Layer Indicators (Alternative)

Add cold-start visibility to the dashboard API layer (not the observation
layer). This is outside the sealed scope.

**If pursued**: Separate CR required, Category B, L2 conditional.

### Recommendation

**Option A.** The sealed observation system is complete and correct.
Cold-start is an operational state, not a code deficiency. When A
decides to activate live trading, the board will automatically
transition to warm-start with no code changes needed.

---

## 7. Pre-Activation Checklist (For When Live Trading Begins)

When A authorizes live trading activation:

```
[ ] 1. Verify all infrastructure running (Postgres, Redis, Celery worker, Celery beat)
[ ] 2. Confirm exchange credentials configured (Binance testnet)
[ ] 3. Submit first test proposal through pipeline
[ ] 4. Wait 5 minutes, then board read: verify at least one TierLatency.measured=True
[ ] 5. Wait 2 hours, then board read: verify trend_available=True
[ ] 6. Run 832/0/0 baseline test (should still pass — observation is read-only)
[ ] 7. Record warm-start transition in operations log
[ ] 8. Begin daily board reads with live data
```

---

## 8. Conclusion

CR-019 scope analysis is complete. The cold-start state is an **operational
condition**, not a **code deficiency**. The sealed observation system already
contains all the code needed for warm-start operation.

**No code changes recommended at this time.**

The next milestone for cold-start resolution is A's decision to activate
live trading infrastructure, at which point the board will automatically
begin producing real observations.
