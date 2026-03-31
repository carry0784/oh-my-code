# D-2: Operator Interpretation Pack

Effective: 2026-03-31
Status: **ACTIVE** (Phase D-2)
Author: B (Implementer)
Scope: Anti-misinterpretation guidance for all observation cards

---

## 1. Purpose

Prevent operators from misreading observation cards as predictions,
recommendations, or alerts. Each card has a structured interpretation
entry covering what it means, what it does not mean, and what is forbidden.

---

## 2. Card Interpretation Guide

### 2.1 Trend Observation (HIGHEST RISK)

| Aspect | Content |
|--------|---------|
| **What it means** | Compares count-based metrics between the current 60-minute window and the previous 60-minute window. Shows whether blocked, pending-retry, review, and watch counts are increasing, decreasing, or stable. |
| **What it does NOT mean** | It does NOT predict future values. "Increasing" means "count went up vs. prior window" — it does NOT mean "count will continue to rise." |
| **When to look** | When you want to understand whether the current snapshot is better, worse, or similar to the recent past. |
| **Common misreadings** | (1) "Increasing blockage means the system is failing" — No, it means the count is higher than last window. (2) "Stable means everything is fine" — No, stable only means unchanged. A high stable count is still high. |
| **Forbidden interpretations** | "Will continue to...", "trending toward...", "improving", "worsening", "deteriorating", "recovering" |
| **Volatility** | Data is in-memory only. Restarts clear all history. Do not treat as persistent analytics. |
| **Safety** | read_only=True, simulation_only=True, no_action_executed=True, no_prediction=True |

### 2.2 Latency Observation

| Aspect | Content |
|--------|---------|
| **What it means** | Shows per-tier elapsed time (median, min, max) from proposal creation to receipt/completion. Measures how long proposals spend in each tier. |
| **What it does NOT mean** | It does NOT measure end-to-end pipeline latency. Each tier is measured independently. It does NOT set SLA thresholds or judge whether times are "good" or "bad." |
| **When to look** | When you suspect a specific tier is slow, or when investigating why proposals are aging. |
| **Common misreadings** | (1) "High median = the tier is broken" — No, high median means proposals take longer in that tier. The cause could be normal. (2) "Orders tier latency = exchange latency" — No, Orders tier measures internal processing only. |
| **Forbidden interpretations** | "Too slow", "within SLA", "healthy latency", "degraded performance" |
| **Scope limit (v1)** | Per-tier only. No percentiles (p95/p99). No mean. No end-to-end. No cross-tier aggregation. |
| **Safety** | read_only=True, simulation_only=True, no_action_executed=True, no_prediction=True |

### 2.3 Blockage Summary

| Aspect | Content |
|--------|---------|
| **What it means** | Shows per-tier blockage rate (blocked / total) and the top reasons proposals are blocked. Identifies which tier has the highest concentration of blocked proposals. |
| **What it does NOT mean** | It does NOT diagnose the root cause of blockage. It does NOT recommend actions to unblock proposals. A high blockage rate is a factual observation, not an alarm. |
| **When to look** | When the tier status shows blocked proposals and you need to understand where and why they are blocked. |
| **Common misreadings** | (1) "High blockage rate = system malfunction" — No, blockage can be normal (e.g., guard checks correctly blocking risky proposals). (2) "Concentrated in one tier = that tier is failing" — No, it means most blocks happen there. |
| **Forbidden interpretations** | "Critical blockage", "unhealthy pipeline", "needs immediate intervention" |
| **Safety** | read_only=True, simulation_only=True, no_action_executed=True, no_prediction=True |

### 2.4 Retry Pressure

| Aspect | Content |
|--------|---------|
| **What it means** | Shows the retry backlog: how many proposals are pending retry, their status distribution (pending/active/completed/failed), channel distribution, and severity distribution. |
| **What it does NOT mean** | It does NOT indicate that retries will succeed or fail. It does NOT recommend retry strategies. A large backlog is a count, not a verdict. |
| **When to look** | When you want to understand whether the notification/retry system is keeping up with demand. |
| **Common misreadings** | (1) "Large backlog = system is overwhelmed" — No, it means there are many items to retry. Some may be low-severity. (2) "All retries failed = notification system broken" — No, check the channel and severity distributions for context. |
| **Forbidden interpretations** | "Retry storm", "system overloaded", "notification failure" |
| **Safety** | read_only=True, simulation_only=True, no_action_executed=True, no_prediction=True |

### 2.5 REVIEW Volume

| Aspect | Content |
|--------|---------|
| **What it means** | Shows the count and distribution of proposals classified as ACTION_REVIEW (requires operator review). Breaks down by tier, reason, and staleness band. Includes density signal (concentration and prolonged detection). |
| **What it does NOT mean** | It does NOT recommend which proposals to review first. It does NOT escalate. The density signal is descriptive, not prescriptive. |
| **When to look** | When the observation summary shows elevated pressure and you want to drill into the REVIEW subset specifically. |
| **Common misreadings** | (1) "Concentrated = urgent" — No, concentrated means most REVIEW proposals are in one tier. Urgency is an operator judgment. (2) "Prolonged = overdue" — No, prolonged means the proposal has been in REVIEW state longer than 3x threshold. |
| **Forbidden interpretations** | "Urgent review needed", "overdue proposals", "escalation required" |
| **Safety** | read_only=True, simulation_only=True, no_action_executed=True, no_prediction=True |

### 2.6 WATCH Volume

| Aspect | Content |
|--------|---------|
| **What it means** | Shows the count and distribution of proposals classified as ACTION_WATCH (monitor, no immediate action). Same structure as REVIEW Volume but for the WATCH subset. |
| **What it does NOT mean** | It does NOT mean these proposals are safe to ignore. WATCH is a classification, not a safety assessment. |
| **When to look** | When you want to understand the monitoring backlog — proposals that are aging but not yet in REVIEW. |
| **Common misreadings** | (1) "WATCH = safe" — No, WATCH means "monitor". Some may escalate to REVIEW. (2) "Low WATCH count = good" — Not necessarily. It could mean proposals are skipping WATCH and going straight to REVIEW. |
| **Forbidden interpretations** | "Safe to ignore", "no action needed", "low risk" |
| **Safety** | read_only=True, simulation_only=True, no_action_executed=True, no_prediction=True |

### 2.7 Observation Summary

| Aspect | Content |
|--------|---------|
| **What it means** | Aggregates all observation data into a pressure level (LOW/MODERATE/HIGH/CRITICAL), distribution by tier, reason-action matrix, and priority ranking of candidates. |
| **What it does NOT mean** | Pressure level is a classification based on counts, not a system health judgment. CRITICAL pressure means "many candidates" — not "system is failing." |
| **When to look** | As the primary overview before drilling into specific cards. |
| **Common misreadings** | (1) "CRITICAL = emergency" — No, CRITICAL is a count-based classification. (2) "Priority ranking = action order" — No, priority ranking describes which candidates are most stale, not which to act on first. |
| **Forbidden interpretations** | "Emergency", "system failure", "must act now" |
| **Safety** | read_only=True, simulation_only=True, no_action_executed=True, no_prediction=True |

### 2.8 Decision Summary

| Aspect | Content |
|--------|---------|
| **What it means** | Synthesizes observation data into a decision posture (MONITOR/REVIEW/INTERVENE/ESCALATE) with risk level and reason chain. |
| **What it does NOT mean** | The posture is a suggestion, not an instruction. INTERVENE does NOT mean "intervene now" — it means "the data suggests intervention may be warranted." |
| **When to look** | After reviewing the observation summary, to understand the system's suggested posture. |
| **Common misreadings** | (1) "ESCALATE = must escalate" — No, it is a posture suggestion only. (2) "Risk level = probability" — No, risk level is a classification, not a probability. |
| **Forbidden interpretations** | "Must escalate", "required action", "guaranteed outcome" |
| **Safety** | action_allowed=False, suggestion_only=True, read_only=True |

### 2.9 Decision Card

| Aspect | Content |
|--------|---------|
| **What it means** | Visual badge display summarizing the decision posture. Safety bar and badge set for at-a-glance status. |
| **What it does NOT mean** | Badges are visual summaries. They do NOT trigger actions or represent binding decisions. |
| **When to look** | For quick visual assessment of overall system posture. |
| **Safety** | action_allowed=False, suggestion_only=True, read_only=True |

### 2.10 Cleanup Simulation

| Aspect | Content |
|--------|---------|
| **What it means** | Identifies stale proposals that would be cleanup candidates, classified by action band (INFO/WATCH/REVIEW/MANUAL). Simulation only — no cleanup is ever executed. |
| **What it does NOT mean** | "Cleanup candidate" does NOT mean "should be cleaned up." It means "this proposal meets the staleness criteria for that action band." |
| **When to look** | When investigating stale proposal accumulation. |
| **Safety** | Cleanup is NEVER executed. `cleanup_simulation_only=True` always. |

### 2.11 Orphan Detection

| Aspect | Content |
|--------|---------|
| **What it means** | Identifies proposals in lower tiers whose parent proposal in the upper tier is missing. Cross-tier linkage check. |
| **What it does NOT mean** | Orphans are not necessarily errors. A missing parent could indicate normal proposal lifecycle (parent completed and was removed). |
| **When to look** | When cross-tier consistency needs verification. |
| **Safety** | Read-only scan. Never deletes orphans. |

---

## 3. Universal Anti-Misinterpretation Rules

### Rule D2-01: No card is an alarm

No observation card, regardless of its values, constitutes an alarm or alert.
All cards are factual descriptions. Operator judgment determines response.

### Rule D2-02: Counts are not verdicts

A high count (of blockages, retries, stale proposals) is a number.
It does not mean "bad." It does not require action. The operator decides.

### Rule D2-03: Direction is not prediction

"Increasing" means "the count went up." It does NOT mean "the count will
continue to go up." Never extrapolate from observation data.

### Rule D2-04: Classification is not assessment

Pressure level (LOW/MODERATE/HIGH/CRITICAL), decision posture
(MONITOR/REVIEW/INTERVENE/ESCALATE), and action band (INFO/WATCH/REVIEW/MANUAL)
are classification labels, not safety assessments.

### Rule D2-05: No card combination creates an alert

Observing HIGH pressure + increasing trend + concentrated blockage is a set of
factual observations. It does NOT constitute an automated alert condition.
The operator synthesizes meaning.

---

## 4. Priority Cards for Training

When onboarding operators, cover these cards first (highest misinterpretation risk):

| Priority | Card | Risk |
|----------|------|------|
| 1 | Trend Observation | Time-axis misread as prediction |
| 2 | Latency Observation | Elapsed time misread as SLA violation |
| 3 | Blockage Summary | Blockage rate misread as system failure |
| 4 | Retry Pressure | Backlog size misread as system overload |
| 5 | Decision Summary | Posture misread as mandatory instruction |

---

## 5. Forbidden Language Reference

Applies to ALL observation and decision cards.

| Category | Forbidden | Allowed |
|----------|-----------|---------|
| Prediction | "will", "expected to", "trending toward", "forecast" | "currently", "as of", "in this window" |
| Judgment | "good", "bad", "healthy", "unhealthy", "improving", "worsening" | "increasing", "decreasing", "stable", "higher", "lower" |
| Urgency | "critical failure", "emergency", "must act", "immediate" | "CRITICAL pressure" (as classification label only) |
| Recommendation | "should", "must", "recommend", "consider", "suggest" | "observed", "measured", "classified as" |
| Causation | "caused by", "due to", "because of", "resulting from" | "associated with", "co-occurring with" |
