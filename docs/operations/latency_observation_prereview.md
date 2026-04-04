# Latency Observation Pre-Review

Effective: 2026-03-31
Status: **IMPLEMENTED (v1)** — approved Phase C-Next-5
Author: B (Implementer)
C Inspector: GO (2026-03-31)

---

## 1. Purpose

Define the measurement contract for a Latency Observation card before implementation.
This document answers the C inspector's pre-review requirements:

1. Source contract definition
2. Latency measurement boundary definition
3. Partial/zero-safe rules
4. Descriptive wording rules
5. Operator misinterpretation prevention

No code will be written until this document receives C inspector GO.

---

## 2. Source Contract

### Available Timestamp Fields (per tier)

| Tier | Start Field | End Field | Source Object |
|------|-------------|-----------|---------------|
| Agent (T1) | `ActionProposal.created_at` | `ActionReceipt.created_at` | `ActionLedger` |
| Execution (T2) | `ExecutionProposal.created_at` | `ExecutionReceipt.execution_ready_at` | `ExecutionLedger` |
| Submit (T3) | `SubmitProposal.created_at` | `SubmitReceipt.submit_ready_at` | `SubmitLedger` |
| Orders (T4) | `OrderResult.created_at` | `OrderResult.executed_at` | `OrderExecutor` |

### Source Access Pattern

All reads use existing public methods:

| Method | Tier | Returns |
|--------|------|---------|
| `action_ledger.get_proposals()` | T1 | list of proposal dicts |
| `action_ledger.get_receipts()` | T1 | list of receipt dicts |
| `execution_ledger.get_proposals()` | T2 | list of proposal dicts |
| `execution_ledger.get_receipts()` | T2 | list of receipt dicts |
| `submit_ledger.get_proposals()` | T3 | list of proposal dicts |
| `submit_ledger.get_receipts()` | T3 | list of receipt dicts |
| `order_executor.get_history()` | T4 | list of order dicts |

No new ledger methods required. Read-only access only.

---

## 3. Measurement Boundary Definition

### Per-Tier Latency

Each tier measures elapsed time from proposal creation to receipt/completion.

```
Tier 1 (Agent):     ActionProposal.created_at → ActionReceipt.created_at
Tier 2 (Execution): ExecutionProposal.created_at → ExecutionReceipt.execution_ready_at
Tier 3 (Submit):    SubmitProposal.created_at → SubmitReceipt.submit_ready_at
Tier 4 (Orders):    OrderResult.created_at → OrderResult.executed_at
```

### Measurement Unit

All latencies expressed in **seconds** (float, 3 decimal places).

### What Is NOT Measured

The following are explicitly excluded from scope:

| Excluded | Reason |
|----------|--------|
| End-to-end latency (T1→T4) | Requires cross-tier lineage join; complex, deferred |
| Inter-tier gap (T1 end → T2 start) | Requires matching proposal chains; complex, deferred |
| Guard evaluation time | Not timestamped separately; would need ledger change |
| LLM call duration | Outside observation layer scope |
| Network latency | Outside observation layer scope |

### Matching Strategy

Per-tier latency requires pairing proposals with receipts.

**Matching key**: `proposal_id` field present on both proposal and receipt objects.

**Unmatched proposals** (no receipt yet) are excluded from latency calculation but counted as `pending_count` — the card already knows about these via existing board data.

---

## 4. Partial/Zero-Safe Rules

### Rule 1: All ledgers optional

```
build_latency_observation(
    action_ledger=None,       # → tier skipped
    execution_ledger=None,    # → tier skipped
    submit_ledger=None,       # → tier skipped
    order_executor=None,      # → tier skipped
)
```

Returns zero-safe schema with all latencies = 0.0 and `measured=False` per tier.

### Rule 2: Empty ledger = zero-safe

A connected ledger with 0 proposals returns `measured=False`, latency=0.0 for that tier.

### Rule 3: Unparseable timestamps

If `created_at` cannot be parsed as ISO datetime, that proposal is **skipped** (not error).
The `skipped_count` field tracks how many proposals were excluded due to parse failure.

### Rule 4: Negative elapsed time

If end < start (clock skew), elapsed time is clamped to 0.0 and counted in `skipped_count`.

### Rule 5: Sample limit

Like Retry Pressure, apply `limit=200` on proposals read. If more exist, `sample_limited=True`.

---

## 5. Schema Design (Candidate)

**Note**: This is a candidate design for C review. Not final.

```python
class TierLatency(BaseModel):
    tier_name: str = ""
    measured: bool = False
    sample_count: int = 0          # proposals with matched receipt
    skipped_count: int = 0         # parse failures + negative elapsed
    min_seconds: float = 0.0
    max_seconds: float = 0.0
    median_seconds: float = 0.0
    mean_seconds: float = 0.0

class LatencyDensitySignal(BaseModel):
    has_measurements: bool = False
    slowest_tier: str = ""
    slowest_median: float = 0.0
    description: str = ""          # template-locked (OC-08)

class LatencySafety(BaseModel):
    read_only: bool = True
    simulation_only: bool = True
    no_action_executed: bool = True
    no_prediction: bool = True

class LatencyObservationSchema(BaseModel):
    agent_latency: TierLatency
    execution_latency: TierLatency
    submit_latency: TierLatency
    order_latency: TierLatency
    density: LatencyDensitySignal
    safety: LatencySafety
```

Field count: 6 fields on main schema, 8 on TierLatency, 4 on density, 4 on safety.

### Open Questions for C Review

1. **Should we include percentiles (p50/p95/p99)?** Pro: richer signal. Con: more fields, risk of appearing as SLA metric.
2. **Should mean be included?** Pro: simple summary. Con: skewed by outliers, could look like a performance target.
3. **Should `sample_limited: bool` be on per-tier or top-level?** Per-tier is more accurate, top-level is simpler.

---

## 6. Descriptive Wording Rules

### Template Candidates (OC-08 compliant)

```python
_TEMPLATE_NONE = "No latency measurements available."
_TEMPLATE_SINGLE = "{count} tier(s) measured. Median latency: {median}s ({tier})."
_TEMPLATE_MULTI = "{count} tier(s) measured. Slowest median: {median}s ({tier})."
```

### Forbidden Language

The following words/patterns MUST NOT appear in description text:

| Forbidden | Reason |
|-----------|--------|
| "slow" | Implies judgment |
| "fast" | Implies judgment |
| "degraded" | Implies action needed |
| "SLA" | Implies contractual obligation |
| "target" | Implies performance goal |
| "breach" | Implies violation |
| "alert" | Implies action trigger |
| "warning" | Implies action trigger |
| "threshold exceeded" | Implies boundary judgment |
| "normal" / "abnormal" | Implies baseline comparison |

### Allowed Language

| Allowed | Example |
|---------|---------|
| "measured" | "4 tier(s) measured" |
| "median" | "Median latency: 2.5s" |
| "slowest median" | "Slowest median: 5.2s (Submit)" |
| "seconds" | Factual unit |
| tier names | "Agent", "Execution", "Submit", "Orders" |

### Principle

**State the number. Name the tier. Never judge.**

---

## 7. Operator Misinterpretation Prevention

### Risk 1: Latency numbers interpreted as SLA targets

**Mitigation**: No threshold comparison. No "green/yellow/red" classification.
Numbers are presented as raw measurements only.

### Risk 2: "Slowest tier" interpreted as action trigger

**Mitigation**: Description says "Slowest median: Xs (Tier)" — factual statement.
No "needs attention", "review recommended", or "escalate".

### Risk 3: Mean/percentile interpreted as performance benchmarks

**Mitigation**: If C approves percentiles, label them as "observed Nth percentile"
not "target" or "limit". Consider excluding mean entirely (median is more robust).

### Risk 4: Zero latency misinterpreted as "instant processing"

**Mitigation**: `measured=False` clearly indicates no data, not zero-time processing.
Description template for unmeasured tier: "No latency measurements available."

---

## 8. Family Assignment

Latency Observation would join the **Pipeline Family**:

| Card | Source | Status |
|------|--------|--------|
| Blockage Summary | TierSummary blocked counts | COMPLETE |
| Retry Pressure | RetryPlanStore backlog | COMPLETE |
| Latency Observation | Ledger timestamp pairs | **PRE-REVIEW** |

This fits because latency measures pipeline throughput time — a pipeline-domain concern.

---

## 9. OC-19 Checklist (Pre-Review)

| Step | Status | Notes |
|------|--------|-------|
| 1. Typed schema | CANDIDATE | Above design, pending C approval |
| 2. Default value | PLANNED | `Field(default_factory=LatencyObservationSchema)` |
| 3. Drift sentinel | PLANNED | Board field count 22→23 |
| 4. Coverage map | PLANNED | Latency: NONE→STRONG |
| 5. Constitution inventory | PLANNED | Add to OC-14 table |

---

## 10. Decision Required from C Inspector

| Question | Options |
|----------|---------|
| Approve pre-review? | GO / CONDITIONAL GO / BLOCK |
| Include percentiles (p95/p99)? | YES / NO / DEFER |
| Include mean? | YES / NO (median only) |
| End-to-end latency? | INCLUDE / DEFER |
| Sample limit field location? | PER_TIER / TOP_LEVEL |
| Family assignment correct? | YES / NO |

---

## Appendix: Existing Elapsed Time Patterns in Codebase

The codebase already computes elapsed time in these locations:

| Location | Pattern | Purpose |
|----------|---------|---------|
| `ActionLedger._is_stale()` | `(now - created).total_seconds()` | Stale detection (>600s) |
| `ExecutionLedger._is_stale()` | `(now - created).total_seconds()` | Stale detection (>300s) |
| `SubmitLedger._is_stale()` | `(now - created).total_seconds()` | Stale detection (>180s) |
| `cleanup_simulation_service` | `(now - created).total_seconds()` | Age-based band classification |
| `*_ledger._is_duplicate()` | `(now - last_dt).total_seconds()` | Fingerprint cooldown (60s) |

The Latency Observation card uses the same `(end - start).total_seconds()` pattern
but applied to **receipt timestamps** rather than staleness thresholds.

---

## Appendix B: v1 Interpretation Guide (post-implementation)

Added after C inspector approval (2026-03-31).

### Classification

> Latency Observation v1 is an **observational elapsed-time summary**,
> not a performance judgment layer.

This card reports factual elapsed seconds between proposal creation and receipt milestone.
It does NOT assess whether those times are "good" or "bad".

### Per-Tier Interpretation

| Tier | What it measures | What it does NOT measure |
|------|------------------|------------------------|
| Agent | Proposal → receipt elapsed | Guard evaluation time, LLM call time |
| Execution | Proposal → execution_ready elapsed | Tier-local processing time only |
| Submit | Proposal → submit_ready elapsed | Tier-local processing time only |
| Orders | Order creation → execution elapsed | Uses order lifecycle (different source contract) |

**Important**: Agent/Execution/Submit measure `proposal.created_at → receipt milestone`,
which is **cumulative elapsed from proposal birth**, not tier-local causal latency.
Do not use these numbers for precise performance decomposition.

### Orders Tier Note

Orders tier uses `order.created_at → executed_at`, which is a **different source contract**
from the proposal/receipt pattern used by T1-T3. These numbers are comparable within
the same tier across time, but **cross-tier comparison should be done with caution**.

### Sample Metadata Interpretation

| Field | Meaning |
|-------|---------|
| `sample_size` | Number of proposals with valid elapsed measurement |
| `excluded_count` | Proposals skipped (unparseable, negative, missing timestamp) |
| `sample_limited` | True if >200 proposals existed (only most recent 200 sampled) |

When `sample_limited=True`, the reported statistics reflect the **most recent 200 proposals**,
not the full history. When `excluded_count > 0`, some proposals could not be measured.

### v1 Boundary (what will NOT be added without separate A/B/C review)

| Feature | Status | Reason |
|---------|--------|--------|
| Percentiles (p95/p99) | EXCLUDED | Risk of appearing as performance target |
| Mean | EXCLUDED | Outlier-sensitive, misleading |
| End-to-end (T1→T4) | DEFERRED | Requires cross-tier join complexity |
| Trend over time | SEPARATE CARD | Latency ≠ Trend; separate domain |
| Threshold comparison | FORBIDDEN | Violates OC-07 (no judgment) |
