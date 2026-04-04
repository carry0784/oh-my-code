# Observation Coverage Map

Effective: 2026-03-31 (Phase C)
Status: ACTIVE
Scope: All observation layers (L3-L6) and board response

---

## 1. Coverage Matrix

### Tier Coverage

| Tier | Stale | Orphan | Cleanup | Block Reason | Count | Status |
|------|-------|--------|---------|--------------|-------|--------|
| Agent (T1) | observed | observed | observed | observed | observed | **FULL** |
| Execution (T2) | observed | observed | observed | observed | observed | **FULL** |
| Submit (T3) | observed | observed | observed | observed | observed | **FULL** |
| Orders (T4) | N/A | N/A | N/A | N/A | observed | **FULL** (scope-appropriate) |

### Risk Dimension Coverage

| Dimension | Observed | Layer | Card | Strength |
|-----------|----------|-------|------|----------|
| Stale proposals | YES | L3 | Cleanup Simulation | band classification (INFO/WATCH/REVIEW/MANUAL) |
| Orphan proposals | YES | L2 | Orphan Detection | cross-tier parent linkage check |
| Cleanup candidates | YES | L3 | Cleanup Simulation | action class + threshold-based |
| Pressure level | YES | L4 | Observation Summary | LOW/MODERATE/HIGH/CRITICAL enum |
| Distribution by tier | YES | L4 | Observation Summary | stale_by_tier counts |
| Reason-action matrix | YES | L4 | Observation Summary | guard reason → action class mapping |
| Top priority candidates | YES | L4 | Observation Summary | ranked candidate list |
| REVIEW subset volume | YES | L4+ | REVIEW Volume | tier/reason/band distribution |
| REVIEW density signal | YES | L4+ | REVIEW Volume | concentration + prolonged detection |
| WATCH subset volume | YES | L4+ | WATCH Volume | tier/reason/band distribution |
| WATCH density signal | YES | L4+ | WATCH Volume | concentration + prolonged detection |
| Decision posture | YES | L5 | Decision Summary | posture enum + risk level |
| Decision reason chain | YES | L5 | Decision Summary | ordered reason list |
| Visual badges | YES | L6 | Decision Card | safety bar + badge display |
| Pipeline blockage rate | YES | L4+ | Blockage Summary | per-tier blockage rate + reason aggregation |
| Retry pressure | YES | L4+ | Retry Pressure | backlog/status/channel/severity distribution |
| Latency/duration | YES | L4+ | Latency Observation | per-tier elapsed time (median/min/max) |
| Time trend | YES | L4+ | Trend Observation | two-window count-based comparison (volatile) |
| MANUAL subset volume | **NO** | — | — | future candidate |
| Per-tier health score | **NO** | — | — | future candidate |

### Time Coverage

| Dimension | Observed | Notes |
|-----------|----------|-------|
| Snapshot (current state) | YES | All cards produce point-in-time snapshot |
| Trend (two-window) | YES | v1: 60m vs previous 60m, count-only, volatile buffer |
| Window (moving average) | **NO** | Risk of appearing predictive |

---

## 2. Current Observation Cards

### Card: Cleanup Simulation (L3)

| Property | Value |
|----------|-------|
| Service | `app/services/cleanup_simulation_service.py` |
| Schema | internal dataclass → `CleanupActionSummary` on board |
| Observes | stale proposals, action class, band, threshold ratios |
| Safety | simulation_only=True, never executes cleanup |
| Board fields | `cleanup_candidate_count`, `cleanup_action_summary`, `cleanup_simulation_only` |

### Card: Orphan Detection (L2)

| Property | Value |
|----------|-------|
| Service | `app/services/orphan_detection_service.py` |
| Schema | internal dataclass → `list[OrphanDetail]` on board |
| Observes | cross-tier parent linkage, missing parent identification |
| Safety | read-only scan, never deletes orphans |
| Board fields | `cross_tier_orphan_count`, `cross_tier_orphan_detail` |

### Card: Observation Summary (L4)

| Property | Value |
|----------|-------|
| Service | `app/services/observation_summary_service.py` |
| Schema | `ObservationSummarySchema` (typed Pydantic) |
| Observes | pressure, distribution, reason-action matrix, priority ranking |
| Safety | ObservationSafety (4 fields: read_only, simulation_only, no_action_executed, no_prediction) |
| Board field | `observation_summary` |

### Card: REVIEW Volume (L4+)

| Property | Value |
|----------|-------|
| Service | `app/services/review_volume_service.py` |
| Schema | `ReviewVolumeSchema` (typed Pydantic) |
| Observes | REVIEW-class subset: tier/reason/band distribution, density signal |
| Safety | ReviewVolumeSafety (4 fields, same as ObservationSafety) |
| Board field | `review_volume` |

### Card: Decision Summary (L5)

| Property | Value |
|----------|-------|
| Service | `app/services/operator_decision_service.py` |
| Schema | `DecisionSummarySchema` (typed Pydantic) |
| Observes | posture, risk level, reason chain, guard check summary |
| Safety | DecisionSafety (3 fields: action_allowed=False, suggestion_only, read_only) |
| Board field | `decision_summary` |

### Card: WATCH Volume (L4+)

| Property | Value |
|----------|-------|
| Service | `app/services/watch_volume_service.py` |
| Schema | `WatchVolumeSchema` (typed Pydantic) |
| Observes | WATCH-class subset: tier/reason/band distribution, density signal |
| Safety | WatchVolumeSafety (4 fields, same as ObservationSafety) |
| Board field | `watch_volume` |

### Card: Blockage Summary (L4+)

| Property | Value |
|----------|-------|
| Service | `app/services/blockage_summary_service.py` |
| Schema | `BlockageSummarySchema` (typed Pydantic) |
| Observes | per-tier blockage rate, reason aggregation, concentration detection |
| Safety | BlockageSafety (4 fields, same as ObservationSafety) |
| Board field | `blockage_summary` |

### Card: Retry Pressure (L4+)

| Property | Value |
|----------|-------|
| Service | `app/services/retry_pressure_service.py` |
| Schema | `RetryPressureSchema` (typed Pydantic) |
| Observes | retry backlog, status/channel/severity distribution, density signal |
| Safety | RetryPressureSafety (4 fields, same as ObservationSafety) |
| Board field | `retry_pressure` |

### Card: Latency Observation (L4+)

| Property | Value |
|----------|-------|
| Service | `app/services/latency_observation_service.py` |
| Schema | `LatencyObservationSchema` (typed Pydantic) |
| Observes | per-tier elapsed time: proposal→receipt median/min/max |
| Safety | LatencySafety (4 fields, same as ObservationSafety) |
| Board field | `latency_observation` |
| Scope | v1: per-tier only, no end-to-end, no percentiles, no mean |

### Card: Trend Observation (L4+)

| Property | Value |
|----------|-------|
| Service | `app/services/trend_observation_service.py` |
| Schema | `TrendObservationSchema` (typed Pydantic) |
| Observes | two-window count comparison (60m vs previous 60m), volatile ring buffer |
| Safety | TrendSafety (4 fields, same as ObservationSafety) |
| Board field | `trend_observation` |
| Scope | v1: count-only, fixed 60m, in-memory, no rates, no percentiles |

### Card: Decision Card (L6)

| Property | Value |
|----------|-------|
| Service | `app/services/decision_card_service.py` |
| Schema | `DecisionCard` (typed Pydantic) |
| Observes | visual badge set, safety bar, operator guidance |
| Safety | SafetyBar (3 fields, same as DecisionSafety) |
| Board field | `decision_card` |

---

## 3. Coverage Gaps

### ~~Gap 1: Retry Pressure~~ — **RESOLVED (Phase C-Next-3)**

### ~~Gap 2: WATCH Subset Volume~~ — **RESOLVED (Phase C-Next)**

### ~~Gap 3: Pipeline Blockage Rate~~ — **RESOLVED (Phase C-Next-2)**

### Gap 4: Time Trend (NOT APPROVED)

**What**: Time-series observation of any metric (stale count over time, pressure changes).
**Where**: Would require storage/windowing infrastructure.
**Risk if unobserved**: No historical context for operator decisions.
**Constitution compliance**: **REQUIRES A/B/C REVIEW** — time axis introduces interpretation complexity, risk of appearing predictive (OC-07). NOT approved for Phase C.

### Gap 5: Latency/Duration (NOT OBSERVED)

**What**: Proposal lifecycle duration, time-to-receipt, guard evaluation latency.
**Where**: Proposals have `created_at` timestamps but duration is not computed.
**Risk if unobserved**: Operator cannot detect slow pipeline segments.
**Constitution compliance**: Factual elapsed time is descriptive, not predictive. Requires careful wording. CONDITIONALLY SAFE.

---

## 4. Expansion Priority (Phase C candidates)

| Priority | Card | Pattern | Risk | Effort |
|----------|------|---------|------|--------|
| ~~1~~ | ~~WATCH Volume~~ | ~~Clone REVIEW Volume~~ | ~~Low~~ | **DONE (Phase C-Next)** |
| ~~2~~ | ~~Pipeline Blockage Summary~~ | ~~New aggregation~~ | ~~Low~~ | **DONE (Phase C-Next-2)** |
| ~~3~~ | ~~Retry Pressure Observation~~ | ~~New card~~ | ~~Medium~~ | **DONE (Phase C-Next-3)** |
| ~~4~~ | ~~Latency Observation~~ | ~~New card~~ | ~~Medium~~ | **DONE (Phase C-Next-5)** |
| ~~5~~ | ~~Time Trend~~ | ~~New infrastructure~~ | ~~High~~ | **DONE (Phase C-Next-7)** |

### Expansion rules (per Observation Constitution)

All new cards MUST:
- Be read-only (no mutations)
- Be descriptive only (no imperative verbs)
- Include safety invariant (4 fields for observation layer)
- Use typed Pydantic schema
- Pass governance tests (6 axes)
- Update drift sentinel (field count/name snapshot)
- Use `to_schema()` for board integration (never `to_dict()`)

---

## 5. Coverage Strength Assessment

```
            STRONG          MODERATE        WEAK            NONE
            ------          --------        ----            ----
Stale       [=========]
Orphan      [=========]
Cleanup     [=========]
Pressure    [=========]
Distribution[=========]
REVIEW Vol  [=========]
Decision    [=========]
Visual      [=========]
WATCH Vol   [=========]
Blockage    [=========]
Retry       [=========]
Latency     [=========]
Trend       [=========]
```

**Overall**: 13/13 dimensions STRONG. **FULL COVERAGE.**

---

## 6. Board Response Field Map

All 24 fields in `FourTierBoardResponse` mapped to observation source:

| Field | Type | Source Card |
|-------|------|-------------|
| `agent_tier` | TierSummary | ActionLedger.get_board() |
| `execution_tier` | TierSummary | ExecutionLedger.get_board() |
| `submit_tier` | TierSummary | SubmitLedger.get_board() |
| `order_tier` | OrderTierSummary | OrderExecutor.get_history() |
| `derived_flags` | DerivedFlags | Execution + Submit ledger |
| `top_block_reasons_all` | list[str] | Aggregated from tiers |
| `recent_lineage` | list[LineageEntry] | Submit + Order cross-ref |
| `cross_tier_orphan_count` | int | Orphan Detection |
| `cross_tier_orphan_detail` | list[OrphanDetail] | Orphan Detection |
| `cleanup_candidate_count` | int | Cleanup Simulation |
| `cleanup_action_summary` | CleanupActionSummary | Cleanup Simulation |
| `cleanup_simulation_only` | bool | Constant (True) |
| `observation_summary` | ObservationSummarySchema | Observation Summary |
| `decision_summary` | DecisionSummarySchema | Decision Summary |
| `decision_card` | Optional[DecisionCard] | Decision Card |
| `review_volume` | ReviewVolumeSchema | REVIEW Volume |
| `watch_volume` | WatchVolumeSchema | WATCH Volume |
| `blockage_summary` | BlockageSummarySchema | Blockage Summary |
| `retry_pressure` | RetryPressureSchema | Retry Pressure |
| `latency_observation` | LatencyObservationSchema | Latency Observation |
| `trend_observation` | TrendObservationSchema | Trend Observation |
| `total_guard_checks` | int | Constant (25) |
| `seal_chain_complete` | bool | Constant (True) |
| `generated_at` | str | Timestamp |

**dict fields: 0** | **typed models: 24/24** | **dict-free since Phase B**

---

## 7. Observation Family Taxonomy

Cards are grouped into families by domain and data source.

### Volume Family (cleanup simulation based)

| Card | Subset | Status |
|------|--------|--------|
| REVIEW Volume | `ACTION_REVIEW` candidates | **COMPLETE** |
| WATCH Volume | `ACTION_WATCH` candidates | **COMPLETE** |

Family status: **COMPLETE** (2/2). MANUAL Volume is a future candidate but not prioritized.

### Pipeline Family (tier/retry/latency based)

| Card | Source | Status |
|------|--------|--------|
| Blockage Summary | TierSummary blocked counts | **COMPLETE** |
| Retry Pressure | RetryPlanStore backlog | **COMPLETE** |
| Latency Observation | Ledger timestamp pairs | **COMPLETE** (v1) |

Family status: **COMPLETE** (3/3). All pipeline observation dimensions are covered.

### Summary/Decision Family (aggregation layers)

| Card | Layer | Status |
|------|-------|--------|
| Observation Summary | L4 | **COMPLETE** |
| Decision Summary | L5 | **COMPLETE** |
| Decision Card | L6 | **COMPLETE** |

Family status: **COMPLETE** (3/3).

### Infrastructure Family (cross-tier detection)

| Card | Source | Status |
|------|--------|--------|
| Cleanup Simulation | L3 stale scan | **COMPLETE** |
| Orphan Detection | L2 linkage scan | **COMPLETE** |

Family status: **COMPLETE** (2/2).

### Temporal Family (cross-cutting time observation)

| Card | Source | Status |
|------|--------|--------|
| Trend Observation | MetricSnapshotBuffer (volatile) | **COMPLETE** (v1) |

Family status: **COMPLETE** (1/1). Volatile in-memory buffer, restart clears history.

### Not yet assigned

| Candidate | Family | Status |
|-----------|--------|--------|
| ~~Latency Observation~~ | ~~Pipeline~~ | **DONE (Phase C-Next-5)** |
| ~~Time Trend~~ | ~~Temporal~~ | **DONE (Phase C-Next-7)** |
