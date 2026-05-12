# CR-050: Parameter Slots Policy (D4)

Date: 2026-05-12
Canonical Core: **K-V3 4-Strategy (S1+S2+S3+S4)**
Parent: **CR-050** (External Artifact Trust Map + Clean-Room Injection Policy)
Child Artifact Declaration: per `docs/operations/evidence_namespace_policy.md` §3 (relation = Child of CR-050)
Sibling on main: D1 (`cr050_constitution_amendment_plan.md`), D3 (`cr050_injection_audit_receipt_spec.md`), D6 (`cr050_shadow_gate_activation_policy.md`), D2 (`cr050_operator_responsibility_zone_v1.md`)
Authority: Operator (운영자)
Status: DRAFT — awaiting operator sign-off

---

## Plan-Only Clarifier

This document defines **parameter-slot admissibility only**.
It does **not** authorize live parameter injection, strategy implementation, parser logic, gate modules, runtime hooks, call sites, or enforcement authority.

No `app/`, `strategies/`, `workers/`, `tests/`, or CI configuration is touched by this document.
No existing CR-050 parent doc, no D1, no D3, no D6, no D2, and no `docs/system_final_constitution.md` is modified.

This document defines **what may legally arrive** at a future K-V3 parameter slot. Whether any specific slot is implemented — and how — is a separate per-PR operator decision.

---

## 1. Status, Authority, Parent Relation

| Attribute | Value |
|-----------|-------|
| Document class | Parameter-slot admissibility specification (docs-only) |
| Authority | Operator (운영자) |
| Parent CR | CR-050 |
| Parent docs (read-only references) | `cr050_external_artifact_trust_map.md`, `cr050_clean_room_injection_policy.md` |
| Sibling docs on main | D1, D3, D6, D2 |
| Namespace relation | Child of CR-050 |
| Namespace pre-flight | `cr050 | relation=Child | inventory_checked=YES` |
| Lifecycle status | DRAFT pending sign-off |
| Modification rule | Successive amendments require their own per-PR approval |

---

## 2. Problem Statement

The CR-050 trust map (`cr050_external_artifact_trust_map.md`) and the clean-room injection policy (`cr050_clean_room_injection_policy.md`) permit **clean-room restated concepts** under strict tiering. The policies do not yet specify, at field-level precision, **what counts as a valid parameter slot derived from such a concept**.

Without a parameter-slot policy:

- A future PR could inject a vague external concept ("preset = aggressive") as a configuration value with no schema check.
- The boundary between an admissible parameter (T1 slot shape) and an inadmissible implementation body (T2 obfuscated logic) is implicit.
- D3's audit block (per `cr050_injection_audit_receipt_spec.md`) refers to `concepts_injected` and `routing_layer` but does not define what a slot must look like field-by-field.
- A shadow skeleton or dogfood evaluator has no schema to compare incoming proposals against.

This document closes that gap. It is a **boundary** document: it tells PR authors and reviewers what a parameter slot must contain, what it may not contain, and which K-V3 layer may receive it.

---

## 3. Allowed Source Tiers

| Tier | Admissibility for parameter slot | Conditions |
|------|----------------------------------|------------|
| **T0** (K-V3 native) | N/A | T0 parameters do not derive from external artifacts; no CR-050 audit required |
| **T1** (structure-trusted) | **Admissible** | After clean-room restatement (per clean-room policy §4 Step B); no Uprich identifier may appear in the slot definition |
| **T2** (stub suspicion) | **Admissible only as abstract restatement** | Behavior must be re-derived from K-V3 canonical understanding; never transcribed; no decompiled body permitted |
| **T3** (runtime / protection core) | **FORBIDDEN** | T3 elements may not become parameter slots under any condition |
| **T4** (license / security boundary) | **FORBIDDEN** | T4 elements may not become parameter slots under any condition |

### 3.1 Operator-zone interaction (cross-ref D2)

Operator-zone observations of T3 / T4 material per `cr050_operator_responsibility_zone_v1.md` (D2) **may not become parameter slots**. They may only become natural-language risk notes per D2 §4. Any attempt to inject operator-zone material as a parameter slot is **rejected** (see §10).

---

## 4. Parameter Slot Categories

Exactly five slot categories are defined. Each maps to one of the five admissible K-V3 layers (per clean-room policy §6 and D3's seven-layer routing gate).

| Category | Target K-V3 layer | Plain-English summary |
|----------|--------------------|------------------------|
| `observation_parameter_slot` | Observation | Data-field shapes (e.g., a price-history window length, a balance read frequency) |
| `interpretation_parameter_slot` | Interpretation | Categorical or threshold structures used by interpreters (e.g., "preset = aggressive / neutral / conservative") |
| `decision_threshold_slot` | Decision | Numeric thresholds used by decision gates (e.g., "block entry if funding rate > X") |
| `execution_limit_slot` | Execution | Order-shape limits (e.g., max leverage, max position size, allowed order types) |
| `learning_metadata_slot` | Learning | Tags / labels attached to learning cases (e.g., "trailing-entry timeout pattern") |

### 4.1 Categories not defined here

There are **no** parameter slot categories for the **Evolution** or **Constitution** layers. Both layers remain protected from external-artifact concepts (see §8 and D6).

---

## 5. Forbidden Parameter Inputs

The following inputs are **forbidden** as parameter slot content, regardless of intent or framing:

| # | Input | Why forbidden |
|---|-------|---------------|
| 1 | Binary artifact content | Trust map §5 + clean-room policy §3 |
| 2 | Decompiled C# / IL bodies | Clean-room policy §3, D2 §4.2 |
| 3 | License-bypass logic | Forbidden everywhere (D2 §3.1, clean-room §3) |
| 4 | TPM / circumvention logic | T3 SEALED no-cross |
| 5 | Runtime patching logic | T3 SEALED no-cross |
| 6 | Vendor-specific implementation bodies | Independence test (clean-room §4 Step C) is breached |
| 7 | Operator-zone restricted details | D2 §4.2 (only natural-language risk notes may flow back) |
| 8 | Evolution-layer concepts | D6 §11 + proposed C13 in D1 |
| 9 | Constitution-layer concepts | D6 §11 + proposed C13 in D1 |

**Default rule**: if an input does not clearly match an allowed slot category in §4 with admissible source tier in §3, it is **forbidden**.

---

## 6. Slot Schema

Each parameter slot proposed under CR-050 must populate the following fields. Field order is illustrative; parsers (when later authorized) must be key-based.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slot_id` | string | yes | Stable identifier (suggested prefix `cr050-slot-`) |
| `slot_name` | string | yes | Human-readable K-V3 vocabulary name (no Uprich identifiers) |
| `source_tier` | enum | yes | `T1` \| `T2` (T0 / T3 / T4 are not valid for this schema) |
| `clean_room_summary` | string | yes | One-line K-V3-vocabulary description of the concept (no artifact identifiers) |
| `allowed_layer` | enum | yes | One of the 5 categories in §4 |
| `forbidden_material_check` | enum | yes | `PASS` \| `FAIL` (must be `PASS` to be admissible; cross-ref §5) |
| `independence_test` | enum | yes | `PASS` \| `FAIL` (per clean-room §4 Step C; must be `PASS`) |
| `operator_zone_reliance` | enum | yes | `YES` \| `NO`; if `YES`, the slot must additionally satisfy D2 §4 (natural-language risk note basis only) |
| `audit_receipt_ref` | string | yes | Reference to a D3-compliant CR-050 audit block in the introducing PR (e.g., `cr050-receipt-<uuid>`) |
| `rollback_note` | string | yes | Plain-text statement of how the slot is withdrawn if needed |

### 6.1 Schema rules

- Missing required field → slot proposal is `MALFORMED`.
- `source_tier` ∈ `{T0, T3, T4}` → automatic rejection (§10).
- `allowed_layer` ∈ `{Evolution, Constitution}` (or any value not in §4) → automatic rejection.
- `forbidden_material_check` ≠ `PASS` → automatic rejection.
- `independence_test` ≠ `PASS` → automatic rejection.
- `operator_zone_reliance == YES` and the slot proposal contains material beyond a restated risk note → automatic rejection.

---

## 7. Acceptance Rules

A parameter slot may be **accepted** (subject to phase, per D6) if and only if **all** of the following hold:

1. `source_tier ∈ {T1, T2}`.
2. `forbidden_material_check == PASS`.
3. `independence_test == PASS`.
4. The introducing PR contains a D3-compliant CR-050 audit block, and `audit_receipt_ref` resolves to it.
5. If `operator_zone_reliance == YES`, the slot's `clean_room_summary` is consistent with D2 §4 result-flow rules (natural-language risk note only).
6. `allowed_layer` ∈ `{Observation, Interpretation, Decision, Execution, Learning}`.
7. The slot does not contain any item from §5 (forbidden inputs).
8. The slot does not depend on T3 / T4 elements, even by reference.

### 7.1 Phase-aware acceptance

Acceptance under §7 yields one of the per-phase verdict states defined in §11. The phase governing the verdict is set by D6:

- **PHASE_0_DOCS_ONLY**: only docs-only slot proposals (descriptive entries in this or a successor doc) are admissible. No code slot is admissible.
- **PHASE_1_SHADOW_SKELETON**: code slots may be defined statically (e.g., schema constants) but `_CR050_AUDIT_ENABLED = False`; no live admission yet.
- **PHASE_2_DOGFOOD_AUDIT**: live admission is evaluated and recorded; verdicts are advisory.
- **PHASE_3 / PHASE_4**: not authorized by this document.

---

## 8. Rejection Rules

A parameter slot **must be rejected** if **any** of the following hold:

1. `source_tier ∈ {T0, T3, T4}`.
2. The slot contains implementation details from the artifact (any of §5 items 1, 2, 6).
3. The slot depends on bypass / circumvention / patching logic (any of §5 items 3, 4, 5).
4. `allowed_layer ∈ {Evolution, Constitution}` or any value not in §4.
5. The slot lacks a clean-room restatement (`clean_room_summary` empty or contains artifact identifiers).
6. The slot lacks an `audit_receipt_ref` resolving to a D3-compliant audit block.
7. `operator_zone_reliance == YES` and the slot proposes material beyond a restated risk note.
8. Any of the §6.1 schema rules trigger.

A single failing rule is sufficient to reject. There is no partial accept.

---

## 9. Seven-Layer Mapping

| K-V3 Layer | Slot category accepted | Anchor |
|------------|------------------------|--------|
| Observation | `observation_parameter_slot` | clean-room §6 + D3 routing gate |
| Interpretation | `interpretation_parameter_slot` | clean-room §6 + D3 routing gate |
| Decision | `decision_threshold_slot` | clean-room §6 + D3 routing gate |
| Execution | `execution_limit_slot` | clean-room §6 + D3 routing gate |
| Learning | `learning_metadata_slot` | clean-room §6 + D3 routing gate |
| **Evolution** | **none** | **forbidden by D6 §11 + proposed C13 in D1** |
| **Constitution** | **none** | **forbidden by D6 §11 + proposed C13 in D1** |

D3's `seven_layer_routing_gate` remains the runtime authority for routing checks. D4 governs the upstream **slot definition** itself.

---

## 10. State Terms

The following state terms are defined for use in slot lifecycle audit logs. **No code emits them today**; they are vocabulary for downstream activity logs and receipts.

| State | Meaning | Allowed phase(s) |
|-------|---------|-------------------|
| `CR050_PARAMETER_SLOT_NOT_REQUIRED` | PR does not introduce any external-artifact-derived parameter slot | all phases |
| `CR050_PARAMETER_SLOT_PROPOSED` | A slot proposal has been written and is awaiting evaluation | all phases |
| `CR050_PARAMETER_SLOT_ACCEPTED_SHADOW` | All §7 acceptance rules satisfied, phase = shadow (record only) | shadow only |
| `CR050_PARAMETER_SLOT_REJECTED_SHADOW` | One or more §8 rejection rules triggered, phase = shadow | shadow only |
| `CR050_PARAMETER_SLOT_ACCEPTED_DOGFOOD` | All §7 acceptance rules satisfied, phase = dogfood (advisory) | dogfood only |
| `CR050_PARAMETER_SLOT_REJECTED_DOGFOOD` | One or more §8 rejection rules triggered, phase = dogfood | dogfood only |
| `CR050_PARAMETER_SLOT_BLOCKED` | Slot rejected and operator-marked as never-revisit (e.g., T3/T4 derivation attempt) | all phases |

State transitions are descriptive markers, not enforced flags.

---

## 11. Receipt Schema

When a parameter slot proposal is evaluated (in any phase), a receipt is recorded. Receipts are persisted via the existing `kdexter.audit.evidence_store.EvidenceStore` boundary (no new store invented here).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `receipt_id` | string (uuid) | yes | Suggested prefix `cr050-slot-receipt-` |
| `slot_id` | string | yes | Reference to the proposed slot's `slot_id` (per §6) |
| `source_tier` | enum | yes | `T1` \| `T2` (T0/T3/T4 receipts are not valid; the slot would have been rejected before reaching this stage) |
| `allowed_layer` | enum | yes | One of the 5 categories in §4 |
| `gate_verdict` | enum | yes | `ACCEPTED` \| `REJECTED` \| `MALFORMED` |
| `audit_receipt_ref` | string | yes | Reference to the D3 CR-050 audit block in the introducing PR |
| `operator_decision` | enum | yes | `PROPOSE` \| `ACCEPT` \| `REJECT` \| `BLOCK` |
| `created_at` | string (iso-8601 utc) | yes | Timestamp |
| `rollback_note` | string | yes | Plain-text statement of how the slot is withdrawn if needed (cross-ref §6) |

### 11.1 Append-only

Receipts are append-only. A withdrawal creates a new receipt referencing the prior `receipt_id`; the original receipt is not edited.

### 11.2 No K-V3 enforcement of receipt presence by this document

The receipt schema is defined here; no code or CI check that **enforces** receipt creation is authorized by this document. Enforcement, if and when desired, is a separate per-PR operator approval.

---

## 12. Forbidden Actions (Bound to This Document)

This document **does not authorize** any of the following:

- Creation of `app/services/cr050_audit_gate.py` or any sibling shadow / dogfood / enforcement module.
- Implementation of a parameter slot parser or validator.
- Addition of a CI check, runtime hook, gate module, or call site.
- Hooking into `app/agents/governance_gate.py`, `app/agents/orchestrator.py`, `app/main.py`, or `strategies/ppf/constitution.py`.
- Introduction of any actual K-V3 strategy parameter under CR-050 by this PR.
- Modification of `docs/system_final_constitution.md`.
- Modification of the existing CR-050 parent docs.
- Modification of D1, D2, D3, or D6.
- Activation of any phase or kill-switch state.
- Generation of bypass / circumvention / replication / runtime-patching code by any AI assistant.
- Commit of the Uprich artifact binary, decompiled source, or any reformat thereof.
- Auto-start of D5, Bundle 3.1, Bundle 2 Batch 7, or branch hygiene.
- Interference with PR #107~#110 workstreams.

---

## 13. Next Dependency

| Doc / Bundle | Purpose | Status |
|--------------|---------|--------|
| D1 — `cr050_constitution_amendment_plan.md` | Constitutional anchor plan | ✅ merged (`0406d31`, PR #120) |
| D3 — `cr050_injection_audit_receipt_spec.md` | Audit block + receipt schema | ✅ merged (`64c5a4e`, PR #121) |
| D6 — `cr050_shadow_gate_activation_policy.md` | Activation phases + kill switch + rollback | ✅ merged (`280cbb0`, PR #122) |
| D2 — `cr050_operator_responsibility_zone_v1.md` | Operator-zone scope + result-flow | ✅ merged (`b1830fc`, PR #123) |
| **D4 — this document** | Parameter-slot admissibility | **this PR** |
| D5 — `cr050_risk_control_slots_policy.md` | Risk / control slot restrictions | HOLD (separate per-PR approval) |
| Bundle 3.1 — shadow skeleton | First code artifact | HOLD (eligible for separate approval; not auto-started) |
| Bundle 3.2 — dogfood | Self-evaluation | HOLD (pending D5 + Bundle 3.1) |
| Bundle 3.3 — live enforcement | Merge-blocking | BLOCK (pending actual constitutional amendment ratification) |

D4 closes the second of the three Bundle 3.2 prerequisite docs (D2 ✅, D4 this PR, D5 outstanding). It does **not** unlock Bundle 3.2 by itself.

---

## 14. Final State Verdict

```text
GO     : D4 docs-only PR (this PR) for operator review
HOLD   : D5 (separate per-PR approval)
HOLD   : Bundle 3.1 shadow skeleton
HOLD   : Bundle 3.2 dogfood
BLOCK  : Bundle 3.3 live enforcement
BLOCK  : Code wiring of any kind by this PR
BLOCK  : Modification of active constitution by this PR
BLOCK  : Modification of CR-050 parent docs, D1, D2, D3, or D6 by this PR
```

---

## 15. Cross-References

**Parent / sibling CR-050 docs:**

- `docs/operations/evidence/cr050_external_artifact_trust_map.md` — tier definitions (T0–T4)
- `docs/operations/evidence/cr050_clean_room_injection_policy.md` — Extract → Restate → Implement procedure + 5 verdict gates + 7-layer routing
- `docs/operations/evidence/cr050_constitution_amendment_plan.md` (D1) — proposed C12 / C13 plan
- `docs/operations/evidence/cr050_injection_audit_receipt_spec.md` (D3) — audit block + receipt fields + verdict model (referenced by `audit_receipt_ref` field)
- `docs/operations/evidence/cr050_shadow_gate_activation_policy.md` (D6) — activation phases (slot acceptance is phase-aware, see §7.1)
- `docs/operations/evidence/cr050_operator_responsibility_zone_v1.md` (D2) — operator-zone result-flow rule (referenced by `operator_zone_reliance` field)

**Governance authority (read-only references):**

- `docs/system_final_constitution.md` — active constitution (unmodified by this policy)
- `docs/operations/change_gate_policy.md` — L0~L4 risk grading (this PR is L0 docs-only)
- `docs/operations/evidence_namespace_policy.md` — namespace pre-flight (relation = Child of CR-050)
- `docs/operations/ci_advisory_triage_policy.md` — B-2 docs-only advisory triage applies if tier-2 mypy reports residual debt

**Audit infrastructure (read-only references):**

- `kdexter.audit.evidence_store.EvidenceStore` (existing boundary; no modification by this doc)

**Pattern source:**

- `docs/operations/evidence/cr046_three_tier_judgment.md` — header / section / signature convention

---

## Signature

```
CR-050 Parameter Slots Policy (D4)
Canonical Core: K-V3 4-Strategy (S1+S2+S3+S4)
Parent CR: CR-050
Document Class: parameter-slot admissibility specification (docs-only)
Active Constitution Modification: NONE
Existing CR-050 Doc Modification: NONE
D1 / D2 / D3 / D6 Modification: NONE
Runtime Wiring Authorization: NONE
Parser / CI Check / Gate Module / Call Site Authorization: NONE
Phase Transition Authorization: NONE
Strategy Parameter Implementation Authorization: NONE
Allowed Source Tiers: T1, T2 (T0/T3/T4 not admissible for slots)
Slot Categories: 5 (observation / interpretation / decision_threshold / execution_limit / learning_metadata)
Forbidden Inputs: 9 categories
Slot Schema Fields: 10 required
States Defined: 7 (CR050_PARAMETER_SLOT_NOT_REQUIRED through CR050_PARAMETER_SLOT_BLOCKED)
Receipt Fields: 9 required
Allowed Routing Layers: Observation, Interpretation, Decision, Execution, Learning
Forbidden Routing Layers: Evolution, Constitution
Namespace Relation: Child of CR-050 (per evidence_namespace_policy.md §3)
Status: DRAFT — awaiting operator sign-off
Prepared by: Implementer
Authority: Operator (운영자)
Date: 2026-05-12
```
