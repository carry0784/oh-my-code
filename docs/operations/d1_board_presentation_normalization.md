# D-1: Board Presentation Normalization

Effective: 2026-03-31
Status: **ACTIVE** (Phase D-1)
Author: B (Implementer)
Scope: 24-field FourTierBoardResponse presentation layout

---

## 1. Purpose

Define how the 24 typed board fields are **grouped, ordered, and presented**
to the operator. The board is read-only — this document governs display logic only.

No new fields are added. No schema changes. No data mutations.

---

## 2. Family Layout

The 24 board fields are organized into **6 presentation sections**,
displayed in the order below. Each section maps to one observation family
or structural category.

### Section 1: Seal Chain (Tier Status)

**Purpose**: Show the 4-tier pipeline health at a glance.

| Order | Field | Type | Display Role |
|-------|-------|------|-------------|
| 1 | `agent_tier` | TierSummary | Tier 1 status |
| 2 | `execution_tier` | TierSummary | Tier 2 status |
| 3 | `submit_tier` | TierSummary | Tier 3 status |
| 4 | `order_tier` | OrderTierSummary | Tier 4 status |
| 5 | `derived_flags` | DerivedFlags | Cross-tier readiness |
| 6 | `seal_chain_complete` | bool | Chain integrity flag |

**Rationale**: The tier chain is the foundational view. Operators check this first.

### Section 2: Infrastructure (Cross-Tier Detection)

**Purpose**: Surface orphans, cleanup candidates, and lineage.

| Order | Field | Type | Display Role |
|-------|-------|------|-------------|
| 7 | `cross_tier_orphan_count` | int | Orphan count |
| 8 | `cross_tier_orphan_detail` | list[OrphanDetail] | Orphan breakdown |
| 9 | `cleanup_candidate_count` | int | Cleanup candidate count |
| 10 | `cleanup_action_summary` | CleanupActionSummary | Band breakdown (INFO/WATCH/REVIEW/MANUAL) |
| 11 | `cleanup_simulation_only` | bool | Safety marker (always True) |
| 12 | `recent_lineage` | list[LineageEntry] | Recent traces |
| 13 | `top_block_reasons_all` | list[str] | Top block reasons |

**Rationale**: Infrastructure issues (orphans, stale proposals, blocked reasons)
are the second thing an operator checks — "is the pipeline structurally sound?"

### Section 3: Summary / Decision

**Purpose**: Aggregated observation and decision posture.

| Order | Field | Type | Display Role |
|-------|-------|------|-------------|
| 14 | `observation_summary` | ObservationSummarySchema | L4 aggregation |
| 15 | `decision_summary` | DecisionSummarySchema | L5 posture |
| 16 | `decision_card` | Optional[DecisionCard] | L6 visual badge |

**Rationale**: Summary cards synthesize lower-layer data. They provide
the operator's primary "what should I pay attention to?" signal.

### Section 4: Volume

**Purpose**: Subset volume distribution by action class.

| Order | Field | Type | Display Role |
|-------|-------|------|-------------|
| 17 | `review_volume` | ReviewVolumeSchema | REVIEW subset |
| 18 | `watch_volume` | WatchVolumeSchema | WATCH subset |

**Rationale**: Volume cards are paired siblings. Always show together,
REVIEW before WATCH (higher severity first).

### Section 5: Pipeline

**Purpose**: Pipeline-specific metrics (blockage, retry, latency).

| Order | Field | Type | Display Role |
|-------|-------|------|-------------|
| 19 | `blockage_summary` | BlockageSummarySchema | Per-tier blockage rate |
| 20 | `retry_pressure` | RetryPressureSchema | Retry backlog |
| 21 | `latency_observation` | LatencyObservationSchema | Per-tier elapsed time |

**Rationale**: Pipeline cards diagnose flow health. Order follows
the diagnostic sequence: "is anything blocked?" -> "are retries piling up?" -> "how slow is it?"

### Section 6: Temporal + Meta

**Purpose**: Time-axis observation and system metadata.

| Order | Field | Type | Display Role |
|-------|-------|------|-------------|
| 22 | `trend_observation` | TrendObservationSchema | Two-window comparison |
| 23 | `total_guard_checks` | int | Guard check count |
| 24 | `generated_at` | str | Board generation timestamp |

**Rationale**: Trend is the newest and highest-risk card — placed last
so operators encounter it only after understanding the current snapshot.
Metadata fields close the response.

---

## 3. Display Order Rules

### Rule D1-01: Section order is fixed

Sections MUST appear in the order defined above (1-6).
Reordering sections requires A/B/C review.

### Rule D1-02: Fields within a section follow defined order

The field order within each section is fixed as shown in the tables above.

### Rule D1-03: No semantic-duplicate adjacency

Cards that observe the same underlying data from different angles
MUST NOT be placed adjacent without a section boundary between them.

| Pair | Relationship | Section Rule |
|------|-------------|--------------|
| Observation Summary + Decision Summary | L4 -> L5 | Same section (Summary/Decision) — allowed, sequential |
| REVIEW Volume + WATCH Volume | Sibling subsets | Same section (Volume) — allowed, paired |
| Blockage + Retry | Different pipeline metrics | Same section (Pipeline) — allowed, different data |
| Latency + Trend | Different time semantics | Different sections — required separation |

### Rule D1-04: Trend is always last observation card

Trend Observation MUST appear after all snapshot-based cards.
This prevents operators from seeing time-axis data before understanding
the current state.

### Rule D1-05: Visual overload prevention

No section should contain more than 7 fields. Current maximum is 7 (Infrastructure).
If a future expansion would push any section past 7, it MUST be split.

---

## 4. Section Labels (for UI rendering)

| Section | Label | Short Description |
|---------|-------|-------------------|
| 1 | Seal Chain | Pipeline tier status and integrity |
| 2 | Infrastructure | Orphans, cleanup, lineage, block reasons |
| 3 | Summary | Observation aggregation and decision posture |
| 4 | Volume | REVIEW and WATCH subset distribution |
| 5 | Pipeline | Blockage, retry pressure, elapsed time |
| 6 | Temporal | Time-window comparison and metadata |

---

## 5. Collapsed vs Expanded Default

| Section | Default State | Rationale |
|---------|---------------|-----------|
| Seal Chain | Expanded | Primary view — always visible |
| Infrastructure | Collapsed | Check when seal chain shows issues |
| Summary | Expanded | Primary decision-support view |
| Volume | Collapsed | Detail view for specific investigation |
| Pipeline | Collapsed | Detail view for flow diagnostics |
| Temporal | Collapsed | Highest interpretation risk — expand on demand |

**Rule**: Expanded sections show key numbers inline.
Collapsed sections show a one-line summary (e.g., "2 orphans, 0 cleanup candidates").

---

## 6. No New Fields

This document does NOT add any board fields.
It reorganizes the existing 24 fields into presentation sections.
All schema governance rules (OC-09 through OC-21) remain unchanged.
