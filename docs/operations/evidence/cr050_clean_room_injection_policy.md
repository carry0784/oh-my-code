# CR-048: Clean-Room Injection Policy

Date: 2026-05-12
Canonical Core: **K-V3 4-Strategy (S1+S2+S3+S4)**
Authority: Operator (운영자)
Status: DRAFT — awaiting operator sign-off

---

## 1. APPLY_MODE Declaration

```
APPLY_MODE              = CLEAN_ROOM_CONCEPT_INJECTION
CODE_COPY               = FORBIDDEN
LICENSE_PROTECTION      = FORBIDDEN
TPM_CIRCUMVENTION       = FORBIDDEN
RUNTIME_PATCHING        = FORBIDDEN
CONCEPT_RESTATEMENT     = REQUIRED before any K-V3 implementation
TIER_CLASSIFICATION     = REQUIRED for every artifact element (per cr048_external_artifact_trust_map.md)
```

Every K-V3 module that derives any concept from the Uprich Future Bot artifact must operate under this APPLY_MODE. There is no exception.

---

## 2. Allowed Inputs

Inputs admitted into the K-V3 clean-room pipeline:

| Category | Example | Source Tier (cr048 trust map) | Verdict |
|----------|---------|-------------------------------|---------|
| Field / slot **names** | `LongUsdt`, `TrailingEntryEnabled`, `MaxDepthGap` | T1 | **ALLOWED** |
| Parameter slot **shapes** (type + range) | `int leverage in [1, 125]`, `bool enabled` | T1 | **ALLOWED** |
| **Concept descriptions** of risk patterns | "kill-switch on drawdown N%", "trailing-entry cooldown" | T1 / T2 | **ALLOWED** |
| **Behavior hypotheses** (re-derived) | "mean-reversion uses 1m/15m/1h/4h gates with per-TF thresholds" | T2 | **ALLOWED (must be re-derived)** |
| **Preset taxonomy** (categories only) | Aggressive / Neutral / Conservative / Custom | T1 | **ALLOWED** |
| Strategy **family labels** | mean_revert / breakout / aggressive_grid_like | T1 | **ALLOWED** |
| UI **layout patterns** (dashboard sections) | "positions / settings / records / logs" | T1 | **ALLOWED** |

All allowed inputs must pass through §4 (Three-Step Procedure) before reaching any K-V3 file.

---

## 3. Forbidden Inputs

Inputs **never admitted**, regardless of intent or framing:

| Category | Example | Source Tier | Verdict |
|----------|---------|-------------|---------|
| Decompiled C# / IL bodies pasted as-is | `Marshal.Copy(...)` lines | T2 / T3 | **FORBIDDEN** |
| Obfuscated identifier names | `tDo6wFPt5M1rBm3hKC.*`, `<Module>{...}` | T2 | **FORBIDDEN (as code, even in comments of K-V3 files)** |
| License-bypass logic | `if (trial) return licensed_true;` and equivalents | T4 | **FORBIDDEN** |
| TPM-circumvention code | DRM strip, anti-debug-removal, integrity-check skip | T3 | **FORBIDDEN** |
| Runtime patching | `DynamicMethod` patching ported to Python via `ctypes` / `numba` for the same purpose | T3 | **FORBIDDEN** |
| Telemetry payloads from T4 | `ServerCustomer` request body shape | T4 | **FORBIDDEN** |
| Hard-coded keys / tokens from artifact | Any embedded constants from T3/T4 paths | T3 / T4 | **FORBIDDEN** |
| Binary or obfuscated assemblies in repo | The Uprich `.exe`, decompiled `.cs`, or any reformat of either | All non-T0 | **FORBIDDEN** |

**Default rule.** If an input is neither in §2 nor §3, it is **forbidden** until tier-classified and re-evaluated.

---

## 4. Three-Step Procedure

Every accepted concept passes through three steps. Skipping any step disqualifies the result.

### Step A — Extract

1. Identify the artifact element (UI label, setting name, observed behavior).
2. Look up or assign its tier in `cr048_external_artifact_trust_map.md`.
3. If tier ∈ {T3, T4}, **stop** — element is boundary, not admissible.
4. If tier ∈ {T1, T2}, capture **only**: the name, the shape (type / range), and a one-line natural-language description.
5. Do **not** capture: method body, IL, control-flow, internal field layout, embedded constants.

### Step B — Restate

1. Rewrite the captured element in **K-V3 vocabulary** (English / Python identifiers).
2. Strip every artifact identifier. After restatement, the text must contain **zero** Uprich names.
3. For T2 elements, the behavior is **re-derived from the K-V3 canonical understanding of the concept**, not transcribed.
4. Restatement output must be reviewable as a standalone document with no reference back to the artifact.

### Step C — Implement

1. Author the implementation **from the restatement only**, in Python, in the K-V3 repository.
2. The author must not consult the decompiled source during this step.
3. The K-V3 implementation must compile / run / test independently of the artifact.
4. PR description records: `(extract_id, restatement_id, implementation_commit)` for audit.

| Step | Test | PASS Criterion |
|------|------|----------------|
| **Extract** | Tier check | Element is T1 or T2; no T3/T4 leakage |
| **Restate** | Vocabulary check | Zero Uprich identifiers, zero decompiled bodies, zero IL fragments |
| **Implement** | Origin check | Authored in Python from K-V3 vocabulary; runs independently |

---

## 5. Operator Responsibility Zone (Rev 3 §9.2)

The following activities are **operator-zone** — performed (if at all) outside the K-V3 automation pipeline, with no AI assistance for circumvention, and with results that do not auto-flow into K-V3 code:

| Activity | AI Assistance | K-V3 Code Impact |
|----------|---------------|------------------|
| Reading / studying T4 license / Trial logic | None for bypass; conceptual restatement only | None — operator may inform K-V3 telemetry policy in natural language only |
| Reading / studying T3 `DynamicMethod` / `Marshal` patterns | None for replication | None — operator may decide Python-idiom equivalents (e.g., explicit decorators) **for distinct purposes** |
| Confirming an element's tier (T3 vs T2 vs T1) | Read-only triage | Tier table entry only, via cr048 trust map |
| Legal review of artifact license / EULA | None | Sign-off recorded in `cr048_operator_responsibility_zone_v1.md` (forthcoming) |

The carve-out **never authorizes** generation of bypass / circumvention / replication code. Forbidden inputs (§3) remain forbidden inside and outside the operator zone.

---

## 6. K-V3 7-Layer Mapping

Each admitted concept is routed to exactly one K-V3 layer, with allowed source tiers:

| K-V3 Layer | Accepts Concepts From | Example Routing |
|------------|------------------------|-----------------|
| **Observation** | T1 (data field slots) | symbol, price, balance, position fields → K-V3 observation schema |
| **Interpretation** | T1 / T2 (signal patterns, regime labels) | "preset = aggressive/neutral/conservative" → K-V3 risk-score interpreter |
| **Decision** | T1 / T2 (gate / filter policy concepts) | "block entry if funding-rate > threshold" → K-V3 RiskControlGate decision |
| **Execution** | T1 (parameter slot shapes) | order parameter shapes (size, leverage, TP/SL) → K-V3 execution schema |
| **Learning** | T2 (failure-mode patterns, observed) | "trailing-entry timeout pattern" → K-V3 learning case template |
| **Evolution** | — | **No artifact concepts accepted** — Evolution rules are K-V3 native |
| **Constitution** | — | **No artifact concepts accepted** — Constitutional articles are K-V3 native |

**Hard rule.** Evolution and Constitution layers receive **no input** from the external artifact, at any tier. They evolve only through K-V3 native deliberation and CR-process amendments.

---

## 7. Audit and Verdict Criteria

Every PR that touches K-V3 code under CR-048 must include an audit block in its description:

```
CR-048 CLEAN-ROOM AUDIT
- Concepts injected:        <list of restatement IDs>
- Source tier (each):       T1 | T2
- Forbidden inputs (§3):    NONE
- Operator-zone reliance:   YES | NO
- 7-layer routing:          <Observation|Interpretation|Decision|Execution|Learning>
- Independence test:        PASS (implementation runs without artifact reference)
- Tier-classification doc:  cr048_external_artifact_trust_map.md @ <commit/section>
```

**Per-PR verdict gates:**

| Gate | PASS Criterion | Action on FAIL |
|------|----------------|----------------|
| Tier classification | Every injected concept has a tier entry | Reject PR; add entry to trust map first |
| Forbidden-input scan | No T3/T4 leakage, no decompiled bodies, no obfuscated names | Reject PR; restate from scratch |
| Vocabulary check | Zero Uprich identifiers in K-V3 code or comments | Reject PR; reword |
| Independence | Code runs / tests pass without artifact in tree | Reject PR; remove implicit dependencies |
| 7-layer routing | Concept routed to allowed layer (not Evolution / Constitution) | Reject PR; reroute or reject concept |

A single failing gate **blocks** the PR. There is no partial pass.

---

## 8. Cross-References

**Companion documents (CR-048 set):**

- `cr048_external_artifact_trust_map.md` — tier definitions consumed by this policy (T0–T4)
- `cr048_constitution_amendment_v1.md` (forthcoming) — C7' / C12 / C13 binding
- `cr048_operator_responsibility_zone_v1.md` (forthcoming) — fuller operator-zone scope
- `cr048_phase_f_parallel_validation_design.md` (forthcoming) — paper validation consumes this policy
- `cr048_risk_control_slots_v1.md` (forthcoming) — first downstream slot set, must pass §4 & §7
- `cr048_strategy_parameter_slots_v1.md` (forthcoming) — strategy slot set, must pass §4 & §7
- `cr048_telegram_notification_policy_v1.md` (forthcoming) — T4-boundary-aware telemetry policy

**Pattern source / authority:**

- `cr046_three_tier_judgment.md` — evidence document conventions
- `docs/system_final_constitution.md` — supreme governance authority
- `strategies/ppf/constitution.py` — C1–C11 invariant pattern that this policy operates beneath

---

## Signature

```
CR-048 Clean-Room Injection Policy
Canonical Core: K-V3 4-Strategy (S1+S2+S3+S4)
APPLY_MODE: CLEAN_ROOM_CONCEPT_INJECTION
Allowed Sources: T1 (Structure-Trusted), T2 (Stub-Suspicion, re-derived)
Forbidden Sources: T3 (Runtime Core), T4 (License Boundary)
Procedure: Extract → Restate → Implement (Python from K-V3 vocabulary)
Operator Zone: T3/T4 analysis only, no replication code
7-Layer Routing: Observation / Interpretation / Decision / Execution / Learning
No Routing: Evolution, Constitution (K-V3 native only)
Audit: Per-PR audit block + 5 verdict gates
Status: DRAFT — awaiting operator sign-off
Prepared by: Implementer
Authority: Operator (운영자)
Date: 2026-05-12
```
