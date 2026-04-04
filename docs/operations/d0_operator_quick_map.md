# Operator Quick Map

**Phase D — One-Page Reference**
24 board fields / 11 observation cards / 5 families / all read-only

---

## Board Field Reference

| # | Field | Family | One-Line Meaning | Never Misread As |
|---|-------|--------|-----------------|------------------|
| 1 | `agent_tier` | Seal Chain | Tier 1 (Agent) proposal status | — |
| 2 | `execution_tier` | Seal Chain | Tier 2 (Execution) proposal status | — |
| 3 | `submit_tier` | Seal Chain | Tier 3 (Submit) proposal status | — |
| 4 | `order_tier` | Seal Chain | Tier 4 (Orders) execution status | — |
| 5 | `derived_flags` | Seal Chain | Cross-tier readiness flags | — |
| 6 | `seal_chain_complete` | Seal Chain | Chain integrity (always True) | — |
| 7 | `cross_tier_orphan_count` | Infrastructure | Count of proposals missing parent | "errors" |
| 8 | `cross_tier_orphan_detail` | Infrastructure | Orphan breakdown | "things to delete" |
| 9 | `cleanup_candidate_count` | Infrastructure | Count of stale proposals | "things to clean up" |
| 10 | `cleanup_action_summary` | Infrastructure | Band breakdown (INFO/WATCH/REVIEW/MANUAL) | "cleanup instructions" |
| 11 | `cleanup_simulation_only` | Infrastructure | Always True — no cleanup executed | — |
| 12 | `recent_lineage` | Infrastructure | Last 10 proposal traces | — |
| 13 | `top_block_reasons_all` | Infrastructure | Top 10 block reasons across all tiers | "error list" |
| 14 | `observation_summary` | Summary | Pressure + distribution + priority ranking | "system health score" |
| 15 | `decision_summary` | Summary | Posture + risk level + reason chain | "mandatory instruction" |
| 16 | `decision_card` | Summary | Visual badge display | "alert" |
| 17 | `review_volume` | Volume | REVIEW subset count + distribution | "urgent items" |
| 18 | `watch_volume` | Volume | WATCH subset count + distribution | "safe items" |
| 19 | `blockage_summary` | Pipeline | Per-tier blockage rate + reasons | "system failure" |
| 20 | `retry_pressure` | Pipeline | Retry backlog + status/severity | "system overload" |
| 21 | `latency_observation` | Pipeline | Per-tier elapsed time (median/min/max) | "SLA violation" |
| 22 | `trend_observation` | Temporal | 60m vs 60m count comparison (volatile) | "prediction" |
| 23 | `total_guard_checks` | Meta | Guard check count (constant: 25) | — |
| 24 | `generated_at` | Meta | Board generation timestamp | — |

---

## 5 Rules for Operators

1. **Every card is observation, not instruction.** You decide what to do.
2. **"Increasing" means "went up."** It does NOT mean "will keep going up."
3. **CRITICAL pressure is a count label.** It is NOT an alarm.
4. **No card combination creates an alert.** You synthesize meaning.
5. **Trend data is volatile.** Restart clears history. Not persistent analytics.

---

## Family Map

```
Seal Chain ──── agent_tier, execution_tier, submit_tier, order_tier,
                derived_flags, seal_chain_complete

Infrastructure ─ orphan_count, orphan_detail, cleanup_count,
                 cleanup_summary, simulation_only, lineage, block_reasons

Summary ──────── observation_summary, decision_summary, decision_card

Volume ────────── review_volume, watch_volume

Pipeline ──────── blockage_summary, retry_pressure, latency_observation

Temporal ──────── trend_observation

Meta ──────────── total_guard_checks, generated_at
```

---

## Safety at a Glance

| Layer | Safety Fields | Key Constraint |
|-------|--------------|----------------|
| Observation (7 cards) | read_only, simulation_only, no_action_executed, no_prediction | All True, always |
| Decision (3 cards) | action_allowed, suggestion_only, read_only | action_allowed=False, always |
| Board | 0 dict fields, 24 typed | No mutations, no write path |
