# Observation Constitution

Effective: 2026-03-31
Status: ACTIVE
Scope: All observation/decision/review layers (L3-L6) and board response contract

---

## 1. Observation vs Decision Firewall

### Rule OC-01: Observation layer NEVER triggers actions

Observation layers (L3-L6) provide **factual data for operator awareness**.
They do NOT:
- Execute cleanup, deletion, or state transitions
- Trigger alerts, escalations, or auto-promotions
- Recommend specific actions with imperative language
- Predict future states or score probabilities

### Rule OC-02: Decision layer reads from Observation, never the reverse

```
L3 Cleanup Simulation → L4 Observation Summary → L5 Decision Summary → L6 Decision Card
                                                 ↘ REVIEW Volume
```

Data flows **downward only**. Decision layer may read observation data.
Observation layer MUST NOT import from or depend on decision layer.

### Rule OC-03: Only Decision layer may carry action_allowed

- `action_allowed` field exists ONLY in DecisionSafety / SafetyBar
- Observation layers use: `read_only`, `simulation_only`, `no_action_executed`, `no_prediction`
- `action_allowed` is ALWAYS False (constitutional constraint)

---

## 2. Safety Invariant Standard

### Rule OC-04: Observation layer safety standard (4 fields)

All observation-layer schemas MUST include a safety sub-model with:

| Field | Value | Meaning |
|-------|-------|---------|
| `read_only` | True | No mutations performed |
| `simulation_only` | True | No cleanup executed |
| `no_action_executed` | True | No state transitions triggered |
| `no_prediction` | True | No forecasting |

These are **structural defaults**, not computed values. NEVER set to False.

### Rule OC-05: Decision layer safety standard (3 fields)

| Field | Value | Meaning |
|-------|-------|---------|
| `action_allowed` | False | Constitutional constraint. NEVER True. |
| `suggestion_only` | True | Guidance, not instruction |
| `read_only` | True | No mutations performed |

---

## 3. Description Wording Rules

### Rule OC-06: No imperative verbs in descriptions

Forbidden patterns:
- "You should...", "You must...", "Execute...", "Delete..."
- "Escalate immediately", "Take action", "Resolve now"
- "We recommend...", "It is advised..."

Allowed patterns:
- "X REVIEW candidate(s) observed."
- "Concentrated in Y tier."
- "Operator review recommended." (passive advisory)
- "No cleanup candidates identified."

### Rule OC-07: No prediction language

Forbidden:
- "Will likely...", "Expected to...", "Probability of..."
- "Trending toward...", "Forecast shows..."
- Score/percentage-based risk predictions

Allowed:
- Factual counts and ratios
- Band classification (early/review/prolonged)
- Concentration detection (>66% in single tier)

### Rule OC-08: Description templates are preferred over free-form

Density signal descriptions use pattern-based templates:

| Condition | Template |
|-----------|----------|
| No candidates | "No REVIEW candidates." |
| Concentrated only | "{N} REVIEW candidate(s). Concentrated in {tier} tier ({count}/{total}, {ratio})." |
| Prolonged only | "{N} REVIEW candidate(s). {P} in prolonged band (>=3x threshold)." |
| Both | "{N} REVIEW candidate(s). Concentrated in {tier} tier (...). {P} in prolonged band (...)." |

---

## 4. Schema Design Rules

### Rule OC-09: All board fields MUST be typed schema

- `dict` fields are forbidden in `FourTierBoardResponse`
- All new observation fields MUST use Pydantic BaseModel
- `list[dict]` MUST be replaced with `list[TypedModel]`

### Rule OC-10: Schema changes require contract test + drift sentinel

Any schema modification MUST include:
1. Updated drift sentinel (field count/name snapshot test)
2. Contract test verifying field types and defaults
3. Backward compatibility review

### Rule OC-11: Additive changes only (unless explicitly approved)

- Adding fields: allowed
- Removing fields: forbidden without A/B/C review
- Changing field types: forbidden without A/B/C review
- Renaming fields: forbidden (treat as remove + add)

### Rule OC-12: use_enum_values=True for all schemas with enums

Ensures JSON serialization produces string values, not enum objects.

---

## 5. Board Contract Rules

### Rule OC-13: External API returns typed schema only

- `to_schema()` is the only external contract path
- `to_dict()` is legacy internal path only
- New code MUST NOT use `to_dict()` for board/API responses

### Rule OC-14: Board response field inventory (as of 2026-03-31)

| Field | Type | Status |
|-------|------|--------|
| `agent_tier` | `TierSummary` | typed |
| `execution_tier` | `TierSummary` | typed |
| `submit_tier` | `TierSummary` | typed |
| `order_tier` | `OrderTierSummary` | typed |
| `derived_flags` | `DerivedFlags` | typed |
| `top_block_reasons_all` | `list[str]` | primitive |
| `recent_lineage` | `list[LineageEntry]` | typed |
| `cross_tier_orphan_count` | `int` | primitive |
| `cross_tier_orphan_detail` | `list[OrphanDetail]` | typed |
| `cleanup_candidate_count` | `int` | primitive |
| `cleanup_action_summary` | `CleanupActionSummary` | typed |
| `cleanup_simulation_only` | `bool` | primitive |
| `observation_summary` | `ObservationSummarySchema` | typed |
| `decision_summary` | `DecisionSummarySchema` | typed |
| `decision_card` | `Optional[DecisionCard]` | typed |
| `review_volume` | `ReviewVolumeSchema` | typed |
| `watch_volume` | `WatchVolumeSchema` | typed |
| `blockage_summary` | `BlockageSummarySchema` | typed |
| `retry_pressure` | `RetryPressureSchema` | typed |
| `latency_observation` | `LatencyObservationSchema` | typed |
| `trend_observation` | `TrendObservationSchema` | typed |
| `total_guard_checks` | `int` | primitive |
| `seal_chain_complete` | `bool` | primitive |
| `generated_at` | `str` | primitive |

**dict fields: 0** (as of Phase B normalization)

---

## 6. to_dict() Retirement Policy

### Rule OC-15: to_dict() is frozen — no new usage

- Existing `to_dict()` in sealed ledgers: **do not touch**
- Existing `to_dict()` in Observation/Decision dataclasses: **retain for internal use**
- New code: **MUST use to_schema() for external paths**
- Test-only usage: **allowed for backward compatibility verification**

### Retirement roadmap

| Phase | Action |
|-------|--------|
| Current | `to_dict()` frozen, `to_schema()` primary |
| Next | Remove `to_dict()` from Observation/Decision dataclasses |
| Final | Only sealed ledger `to_dict()` remains |

### Inventory (as of Phase C, 2026-03-31)

| Category | Files | Count | Retirement |
|----------|-------|-------|------------|
| Sealed Ledger internal | action_ledger, execution_ledger, submit_ledger | 6 | NEVER (sealed) |
| Orchestrator | orchestrator.py (proposal serialization) | 3 | Separate card |
| API Route | agents.py (report.to_dict()) | 1 | Separate card |
| Governance | governance_monitor_tasks.py | 2 | Separate card |
| Orphan/Cleanup internal | orphan_detection_service, cleanup_simulation_service | 3 | Phase C+ candidate |
| Notification/Retry | notification_flow, receipt_store, retry_plan_store, flow_log | 6 | Separate domain |
| Order Executor | order_executor.py | 1 | Separate card |
| Tests (backward compat) | 14 test files | 17 | Retain for verification |

**Total**: 39 references across 25 files
**Frozen**: No new usage since Phase A seal
**External board/API path**: 0 (all converted to to_schema())

---

## 7. Observation Coverage Map

### Currently observed

| Layer | Card | What it observes |
|-------|------|-----------------|
| L3 | Cleanup Simulation | Stale/orphan proposals, action class, band |
| L4 | Observation Summary | Pressure, distribution, priority ranking |
| L5 | Decision Summary | Posture, risk level, reason chain |
| L6 | Decision Card | Visual badges, safety bar |
| L4+ | REVIEW Volume | REVIEW subset: tier/reason/band/density |
| L4+ | WATCH Volume | WATCH subset: tier/reason/band/density |
| L4+ | Blockage Summary | Per-tier blockage rate, reason aggregation, density |
| L4+ | Retry Pressure | Retry backlog, status/channel/severity distribution, density |
| L4+ | Latency Observation | Per-tier proposal-to-receipt elapsed time (v1) |
| L4+ | Trend Observation | Two-window count comparison (volatile ring buffer, v1) |

### Not yet observed (future candidates)

| Candidate | Family | What it would observe | Status |
|-----------|--------|----------------------|--------|
| MANUAL Volume | Volume | MANUAL subset distribution | future |
| Tier Health | new | Per-tier operational health | future |
| Trend/Window | new | Time-series observation (requires careful design) | **DEFERRED** |

### Observation families

| Family | Cards | Status |
|--------|-------|--------|
| Volume | REVIEW Volume, WATCH Volume | **COMPLETE** (2/2) |
| Pipeline | Blockage Summary, Retry Pressure, Latency Observation | **COMPLETE** (3/3) |
| Temporal | Trend Observation | **COMPLETE** (1/1) |
| Summary/Decision | Observation Summary, Decision Summary, Decision Card | **COMPLETE** (3/3) |
| Infrastructure | Cleanup Simulation, Orphan Detection | **COMPLETE** (2/2) |

> Full family taxonomy: `docs/operations/observation_coverage_map.md` §7

### Observation boundary

Trend/time-series observation is **not yet approved**.
It requires separate A/B/C review because:
- Time axis introduces interpretation complexity
- Risk of appearing "predictive"
- Window definition must be explicit and non-arbitrary

> Full coverage map: `docs/operations/observation_coverage_map.md`

---

## 8. Schema Versioning Rules

### Rule OC-16: Additive-only field changes

New fields MAY be added to any observation schema with:
1. A default value (zero, empty, or False)
2. A drift sentinel update (field count + name snapshot test)
3. A contract test verifying the new field type and default

Existing fields MUST NOT be removed, renamed, or have their type changed
without explicit A/B/C review and approval.

### Rule OC-17: No silent mutation of defaults

Changing a field's default value is a **behavioral change**, not a cosmetic one.
Default value changes require:
1. Explicit justification in the commit message
2. Updated contract test asserting the new default
3. Backward compatibility analysis (does any consumer rely on the old default?)

### Rule OC-18: Enum expansion is additive-only

New enum members MAY be added to existing enums (e.g., PressureEnum).
Existing enum members MUST NOT be removed or renamed.
All schemas using enums MUST have `use_enum_values=True` (OC-12).

### Rule OC-19: Board field addition protocol

Adding a new field to `FourTierBoardResponse` requires:
1. Typed schema (no dict, no Any) — per OC-09
2. Default value (field must be optional or have factory default)
3. Drift sentinel update (field count + name snapshot)
4. Coverage map update (`docs/operations/observation_coverage_map.md`)
5. Constitution inventory update (OC-14 table)

### Rule OC-20: Backward compatibility guarantee

All schema changes MUST maintain JSON backward compatibility:
- New fields with defaults: consumers that ignore new fields continue to work
- No field removal: existing consumers never see missing fields
- No type narrowing: a field that was `Optional[X]` MUST NOT become `X` without migration

### Rule OC-21: Deprecation protocol

To deprecate a field (preparation for future removal):
1. Add `deprecated=True` in Field metadata
2. Keep the field and its default for at least 1 full phase
3. Document in constitution changelog
4. Only remove after A/B/C approval in a subsequent phase

---

## 9. Phase C Closure Declaration

Effective: 2026-03-31
Status: **SEALED**

### Coverage

Phase C expanded the observation layer from 8/13 to **13/13 FULL coverage**.
All 5 observation families are COMPLETE. All 11 observation cards are implemented,
tested, and governed. The board response has **24 typed fields, 0 dict fields**.

### What Was Built

| Phase | Cards Added |
|-------|-------------|
| Pre-Phase C | Cleanup Simulation, Orphan Detection, Observation Summary, REVIEW Volume, Decision Summary, Decision Card |
| Phase C | WATCH Volume, Blockage Summary, Retry Pressure, Latency Observation (v1), Trend Observation (v1) |

### Free Expansion Is Terminated

As of 2026-03-31, the observation layer is **closed to free expansion**.
No new observation cards, board fields, or observation families may be added
without a **new A/B/C review cycle**.

This means:
- Proposing a new card requires a pre-review document (like Latency and Trend had)
- The pre-review must receive C inspector GO before any implementation begins
- Each new board field must follow OC-19 (5-step addition protocol)
- "Good idea" is not sufficient justification — operational need must be demonstrated

### What Is Frozen

| Element | Rule |
|---------|------|
| Existing card schemas | Additive-only changes (OC-16) |
| Safety invariant fields | Cannot be removed or set to False |
| Board field count (24) | Cannot increase without A/B/C review |
| Observation family list (5) | Cannot expand without A/B/C review |
| `action_allowed` exclusion | Observation cards NEVER get this field (OC-03) |
| Template-locked descriptions | No free-form text in observation cards (OC-08) |

### v1 Scope Locks (Require Separate A/B/C Review to Change)

| Card | v1 Scope | Forbidden Without Review |
|------|----------|--------------------------|
| Latency Observation | Per-tier elapsed, median/min/max | Percentiles, mean, end-to-end, SLA thresholds |
| Trend Observation | 60m count-only, volatile buffer | Rates, percentages, persistent storage, configurable windows |

### Governance Verification

```
60 governance tests / 8 axes / 0 FAILED / 0 WARNING
3119 total tests / 0 FAILED
```

### Declaration

SAFE expansion complete. Trend approved under strict v1 scope as final card.
All observation dimensions covered. Future changes require new A/B/C review.
Free expansion terminated. Constitution enforcement continues.
