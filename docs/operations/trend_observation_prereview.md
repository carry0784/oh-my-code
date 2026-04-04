# Trend Observation Pre-Review

Effective: 2026-03-31
Status: **IMPLEMENTED (v1)** — approved Phase C-Next-7
Author: B (Implementer)
C Inspector: CONDITIONAL GO → GO (2026-03-31)

---

## 1. Purpose

Define the requirements, risks, and design constraints for a potential
Trend Observation card before any implementation.

Trend is the **only remaining gap** in the observation coverage map (12/13 STRONG).
However, it is also the **highest-risk candidate** because:

- Time-series observation introduces interpretation complexity
- Window definitions create implicit assumptions
- Comparison to baselines can appear predictive
- Operator may misread trends as recommendations

This document does NOT propose implementation. It defines what would need to be
resolved FIRST if implementation were ever approved.

---

## 2. What "Trend" Means in This Context

### Definition

Trend observation = **comparing the same metric across two or more time windows**
to describe whether it is increasing, decreasing, or stable.

### Examples of what trend could observe

| Metric | Window A | Window B | Trend |
|--------|----------|----------|-------|
| Pending count | Last 1h | Previous 1h | "Pending count: 15 → 22 (+46%)" |
| Blockage rate | Last 1h | Previous 1h | "Blockage rate: 12% → 8% (-33%)" |
| Retry backlog | Last 1h | Previous 1h | "Backlog: 5 → 5 (stable)" |

### What trend is NOT

| Not this | Why |
|----------|-----|
| Prediction | "Backlog will reach 50 by midnight" |
| Recommendation | "Consider scaling notification workers" |
| Alert | "Blockage rate exceeding threshold" |
| Score | "Pipeline health: 7/10" |

---

## 3. Prerequisites (Must Be Resolved Before Implementation)

### P-1: Time Window Policy

**Question**: What time windows do we use?

| Option | Pro | Con |
|--------|-----|-----|
| Fixed 1h / 1h | Simple, predictable | Arbitrary boundary, may miss short spikes |
| Configurable | Flexible | Complexity, operator confusion |
| Multiple (1h, 6h, 24h) | Rich context | 3x data, UI complexity, interpretation overload |

**Recommendation**: Start with fixed 1h / 1h if approved. Single window, no configurability.

**Open question**: Where does the historical data come from? Current ledgers are
in-memory and do not persist across restarts. Trend requires either:

- (a) In-memory ring buffer with periodic snapshots
- (b) External time-series store (new dependency)
- (c) Periodic board snapshot persistence

None of these exist today. **This is the hardest prerequisite.**

### P-2: Data Persistence

**Current state**: All ledgers are in-memory. Board is computed on-demand.
There is no historical store.

**What trend needs**: At minimum, a snapshot of key metrics at regular intervals.

| Approach | New dependency | Complexity | Risk |
|----------|---------------|------------|------|
| In-memory ring buffer | None | Low | Lost on restart |
| SQLite/file snapshots | Filesystem | Medium | Disk I/O, rotation |
| Redis time-series | Redis (exists) | Medium | New data path |
| PostgreSQL snapshots | PostgreSQL (exists) | Medium | Schema migration |

**Recommendation**: If approved, start with in-memory ring buffer (simplest, no new deps).
Accept that trend resets on restart. This is consistent with "observational" nature —
trend is "what I can see since I started watching", not "guaranteed historical record".

### P-3: Comparison Baseline

**Question**: What does "previous window" mean?

| Approach | Definition |
|----------|-----------|
| Rolling | Compare last 1h to the 1h before that |
| Fixed epoch | Compare to a "baseline" snapshot taken at deploy time |
| Session-relative | Compare to state when the current process started |

**Recommendation**: Rolling (most recent complete window vs. current incomplete window).
Session-relative is too fragile. Fixed epoch requires manual baseline management.

### P-4: Sample Consistency

**Question**: What if Window A has 100 proposals and Window B has 5?

**Rule**: If either window has fewer than N samples (suggested: N=5),
mark that comparison as `insufficient_data=True` and suppress the trend description.
Never compute a ratio from < 5 samples.

### P-5: Partial/Zero-Safe Policy

| Scenario | Behavior |
|----------|----------|
| No historical data yet | `trend_available=False`, description: "Insufficient history." |
| Only 1 window complete | `trend_available=False`, description: "Waiting for comparison window." |
| Both windows but 0 proposals | `trend_available=False`, all deltas = 0 |
| One window has data, other empty | Mark `insufficient_data=True` |

### P-6: Descriptive Wording Rules

**Template candidates**:

```
_TEMPLATE_NONE = "Insufficient history for trend observation."
_TEMPLATE_WAITING = "Waiting for comparison window ({elapsed} of {window} elapsed)."
_TEMPLATE_STABLE = "{metric}: {current} (stable vs. prior window)."
_TEMPLATE_INCREASING = "{metric}: {prior} → {current} (+{delta_pct})."
_TEMPLATE_DECREASING = "{metric}: {prior} → {current} ({delta_pct})."
```

**Forbidden language**:

| Forbidden | Reason |
|-----------|--------|
| "improving" | Implies judgment (lower blockage = "better") |
| "worsening" | Implies judgment |
| "deteriorating" | Implies judgment |
| "recovering" | Implies prior state was bad |
| "healthy" / "unhealthy" | Direct judgment |
| "trending towards" | Implies prediction of future state |
| "expected to" | Prediction |
| "should" | Recommendation |

**Allowed**: "increasing", "decreasing", "stable", "changed", "prior window", "current window".

**Principle**: **State the direction. State the magnitude. Never interpret.**

### P-7: Prediction Misinterpretation Prevention

**Risk**: "Blockage rate: 8% → 12% (+50%)" could be read as
"blockage is getting worse and will continue to rise."

**Mitigations**:

1. Never extrapolate (no "if this continues...")
2. Never suggest cause (no "possibly due to...")
3. Always show both window values, not just delta
4. Always show sample sizes for both windows
5. Template-lock all descriptions (no free-form text)
6. `no_prediction=True` in safety invariant

---

## 4. Candidate Schema (NOT approved — for discussion only)

```python
class TrendWindow(BaseModel):
    window_label: str = ""           # "current" | "prior"
    window_start: str = ""           # ISO timestamp
    window_end: str = ""             # ISO timestamp
    sample_count: int = 0
    value: float = 0.0

class MetricTrend(BaseModel):
    metric_name: str = ""
    current_window: TrendWindow
    prior_window: TrendWindow
    delta: float = 0.0               # current - prior
    delta_ratio: float = 0.0         # (current - prior) / prior if prior > 0
    direction: str = ""              # "increasing" | "decreasing" | "stable"
    insufficient_data: bool = False
    description: str = ""

class TrendDensitySignal(BaseModel):
    trend_available: bool = False
    metrics_tracked: int = 0
    metrics_with_change: int = 0
    description: str = ""

class TrendSafety(BaseModel):
    read_only: bool = True
    simulation_only: bool = True
    no_action_executed: bool = True
    no_prediction: bool = True

class TrendObservationSchema(BaseModel):
    pending_trend: MetricTrend
    blockage_trend: MetricTrend
    retry_trend: MetricTrend
    density: TrendDensitySignal
    safety: TrendSafety
```

### Open Design Questions

| Question | Options | C Decision Needed |
|----------|---------|-------------------|
| Which metrics to trend? | pending, blockage, retry, latency | YES |
| Fixed or configurable window? | Fixed 1h | YES |
| Data storage approach? | In-memory ring buffer | YES |
| Minimum sample threshold? | 5 per window | YES |
| Direction classification? | ±5% = stable, else increasing/decreasing | YES |
| Board field name? | `trend_observation` | YES |

---

## 5. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Operator reads trend as prediction | HIGH | Template-locked, no extrapolation |
| "Increasing" blockage triggers panic | HIGH | Show raw numbers, not just direction |
| Window boundary artifacts | MEDIUM | Use complete windows only |
| Restart loses all history | MEDIUM | Accept for v1; document behavior |
| Small sample produces noisy trend | MEDIUM | `insufficient_data` flag |
| Trend card scope creep into alert system | HIGH | Constitutional boundary: observation only |

---

## 6. Relationship to Other Cards

**Trend is NOT an extension of Latency, Blockage, or Retry.**

| Card | Scope | Time axis |
|------|-------|-----------|
| Blockage Summary | Current snapshot | None |
| Retry Pressure | Current snapshot | None |
| Latency Observation | Current snapshot (elapsed) | Per-proposal only |
| **Trend Observation** | **Window comparison** | **Cross-window** |

Trend is a **separate observation family** (or a new sub-family under a "Temporal" family).
It must NEVER be merged into existing snapshot cards.

---

## 7. Decision Required from C Inspector

| Question | Options |
|----------|---------|
| Approve pre-review document? | GO / CONDITIONAL GO / BLOCK |
| Approve ring buffer approach? | YES / NO / NEED MORE INFO |
| Approve fixed 1h window? | YES / NO / DIFFERENT WINDOW |
| Approve 3-metric scope (pending/blockage/retry)? | YES / NO / MODIFY |
| Can implementation proceed after pre-review? | YES / NEED SEPARATE APPROVAL |
| Family assignment (Temporal)? | YES / Pipeline / Other |

---

## 8. Recommendation

**B's assessment**: Trend is implementable but carries the highest interpretation risk
of any observation card. The hardest part is not the code — it's the **data persistence**
and **wording discipline**.

If C approves, I recommend:

1. Ring buffer approach (no new external deps)
2. Fixed 1h window (no configurability)
3. 3 metrics only (pending count, blockage rate, retry backlog)
4. Accept restart-clears-history for v1
5. Strict template locking with no interpretation language
6. Separate card, separate family, separate governance tests

If C blocks, the coverage map remains at 12/13 STRONG, which is already a very strong
position. Trend can be revisited in a future phase without any impact on current
operational capability.

---

## Appendix: v1 Volatile Interpretation Guide (post-implementation)

Added after C inspector approval (2026-03-31).

### Classification

> Trend Observation v1 is a **two-window comparative observation** (not a time-series trend).
> It compares count-based metrics between the current 60-minute window and the previous
> 60-minute window using a volatile in-memory ring buffer.

### Volatility Rules (always apply)

1. **Restart clears history** — the ring buffer is in-memory only.
   After restart, trend data is unavailable until enough snapshots accumulate.
2. **Startup-relative observation** — trend reflects only what happened since process start.
   It is NOT a persistent historical record.
3. **Not a persistent trend** — do not treat these numbers as durable analytics.
   They are ephemeral observations for the current operator session.

### Interpretation Guide

| Field | Meaning |
|-------|---------|
| `volatile=True` | Always true — data is in-memory only |
| `since_startup` | ISO timestamp of when the buffer was created |
| `insufficient_data=True` | Not enough snapshots in one or both windows |
| `direction="increasing"` | Current count > previous count (factual, not judgment) |
| `direction="decreasing"` | Current count < previous count (factual, not judgment) |
| `direction="stable"` | Current count == previous count |
| `delta` | Integer difference (current - previous), not a percentage |

### What This Card Does NOT Do

| Excluded | Reason |
|----------|--------|
| Predict future values | OC-07: no prediction |
| Compare to baselines/thresholds | Would imply judgment |
| Show percentage changes | C directive: count-only for v1 |
| Rate or ratio trends | C directive: count-only for v1 |
| Latency trending | Separate domain, requires separate approval |
| Persistent storage | Would change the "volatile observation" nature |

### v1 Boundary (frozen without A/B/C review)

The following are **forbidden without a new A/B/C review cycle**:

- Percent change in descriptions
- Rate/ratio metrics
- Latency or percentile trending
- Persistent storage for snapshots
- "Improving" / "worsening" language
- Configurable window sizes
- Automatic alerting based on direction
