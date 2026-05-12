# CR-050: Injection Audit Block & Receipt Schema (D3)

Date: 2026-05-12
Canonical Core: **K-V3 4-Strategy (S1+S2+S3+S4)**
Parent: **CR-050** (External Artifact Trust Map + Clean-Room Injection Policy)
Child Artifact Declaration: per `docs/operations/evidence_namespace_policy.md` §3 (relation = Child of CR-050)
Sibling on main: `docs/operations/evidence/cr050_constitution_amendment_plan.md` (D1)
Authority: Operator (운영자)
Status: DRAFT — awaiting operator sign-off

---

## Plan-Only Clarifier

This document defines the **audit and receipt schema only**.
It does **not** create a parser, gate module, call site, CI check, runtime hook, or enforcement authority.

No `app/`, `strategies/`, `workers/`, `tests/`, or CI configuration is touched by this document.
No existing CR-050 parent document, no D1 document, and no `docs/system_final_constitution.md` is modified.

---

## 1. Status, Authority, Parent Relation

| Attribute | Value |
|-----------|-------|
| Document class | Schema specification (docs-only) |
| Authority | Operator (운영자) |
| Parent CR | CR-050 |
| Parent docs (read-only references) | `cr050_external_artifact_trust_map.md`, `cr050_clean_room_injection_policy.md` |
| Sibling on main | `cr050_constitution_amendment_plan.md` (D1) |
| Namespace relation | Child of CR-050 |
| Namespace pre-flight | `cr050 | relation=Child | inventory_checked=YES` |
| Lifecycle status | DRAFT pending sign-off |
| Modification rule | Successive amendments require their own per-PR approval |

---

## 2. Problem Statement

CR-050 establishes the trust map (T0–T4) and the clean-room injection procedure (Extract → Restate → Implement). It also defines a per-PR audit block (§7 of `cr050_clean_room_injection_policy.md`) and five verdict gates. **None of these are defined at field-level schema precision.**

Without a precise schema:

- A shadow-only gate skeleton (Bundle 3.1) cannot parse PR bodies deterministically.
- A dogfood audit cannot verify the author's own audit block.
- A future enforcement gate cannot reject malformed input without ambiguity.
- Cross-PR audit log queries cannot be normalized.

This document closes the schema gap. It is consumed by — but does not create — every downstream CR-050 wiring step.

---

## 3. CR-050 Audit Block Schema

Every PR that injects an external-artifact concept into K-V3 must include the audit block in its PR body. The block is parsed as YAML-style key-value pairs. Field order is illustrative; parsers must be key-based, not position-based.

| Field | Type | Required | Allowed Values / Format | Source |
|-------|------|----------|-------------------------|--------|
| `concepts_injected` | list[string] | yes | Restatement IDs, one per concept (no Uprich identifiers) | clean-room policy §4 Step B |
| `source_tier_each` | list[enum] | yes | one of `{T1, T2}` per concept; length must equal `concepts_injected` | trust map §2 |
| `forbidden_inputs` | enum (literal) | yes | exact string `"NONE"` (any other value → FAIL) | clean-room policy §3 |
| `operator_zone_reliance` | enum | yes | `YES` \| `NO` | clean-room policy §5 |
| `routing_layer` | enum | yes | one of `{Observation, Interpretation, Decision, Execution, Learning}` per concept | clean-room policy §6 |
| `independence_test` | enum (literal) | yes | exact string `"PASS"` (any other value → FAIL) | clean-room policy §4 Step C |
| `tier_doc_ref` | string | yes | `cr050_external_artifact_trust_map.md @ <commit-sha-or-section>` | trust map (this is the anchor) |
| `clean_room_doc_ref` | string | yes | `cr050_clean_room_injection_policy.md @ <commit-sha-or-section>` | clean-room policy |
| `amendment_plan_ref` | string | yes | `cr050_constitution_amendment_plan.md @ <commit-sha-or-section>` | D1 |

### 3.1 Parser format expectation (read-only)

```yaml
CR-050 CLEAN-ROOM AUDIT
concepts_injected:        [<restatement_id_1>, <restatement_id_2>]
source_tier_each:         [T1, T2]
forbidden_inputs:         NONE
operator_zone_reliance:   NO
routing_layer:            [Decision, Interpretation]
independence_test:        PASS
tier_doc_ref:             cr050_external_artifact_trust_map.md @ <sha>
clean_room_doc_ref:       cr050_clean_room_injection_policy.md @ <sha>
amendment_plan_ref:       cr050_constitution_amendment_plan.md @ <sha>
```

### 3.2 Hard schema rules

- Missing required field → audit block status = `MALFORMED`.
- `forbidden_inputs` ≠ `"NONE"` → forbidden-input gate = FAIL regardless of other fields.
- `routing_layer` containing `"Evolution"` or `"Constitution"` → seven-layer gate = FAIL.
- `len(source_tier_each)` ≠ `len(concepts_injected)` → MALFORMED.
- Any `source_tier_each[i]` ∈ `{T0, T3, T4}` → tier gate = FAIL (T0 is native, T3/T4 are SEALED).

---

## 4. Gate Verdict Model

Exactly five gates. Each gate produces one of `{PASS, FAIL, UNKNOWN}`. Blocking behavior depends on the deployment phase.

### 4.1 Gate definitions

| # | Gate | Audit Field(s) | PASS | FAIL | UNKNOWN |
|---|------|----------------|------|------|---------|
| 1 | `tier_classification_gate` | `source_tier_each`, `tier_doc_ref` | every entry ∈ `{T1, T2}` and `tier_doc_ref` resolves | any entry ∈ `{T0, T3, T4}` or `tier_doc_ref` does not resolve | field present but cannot be evaluated (e.g., parser cannot fetch the ref) |
| 2 | `forbidden_input_scan_gate` | `forbidden_inputs` | exact value `"NONE"` | any other value | field missing |
| 3 | `vocabulary_independence_gate` | (PR body + diff scan, not a single field) | zero Uprich identifiers in PR body / diff (matched against a known-identifier list maintained outside this doc) | one or more Uprich identifiers found | scan path unavailable |
| 4 | `artifact_independence_gate` | `independence_test` | exact value `"PASS"` | any other value | field missing |
| 5 | `seven_layer_routing_gate` | `routing_layer` | every entry ∈ `{Observation, Interpretation, Decision, Execution, Learning}` | any entry ∈ `{Evolution, Constitution}` or unknown layer | field missing |

### 4.2 Blocking behavior by phase

| Phase | tier_classification | forbidden_input | vocabulary_independence | artifact_independence | seven_layer_routing | Overall blocking |
|-------|---------------------|------------------|---------------------------|------------------------|----------------------|-------------------|
| **shadow** (Bundle 3.1, future) | record only | record only | record only | record only | record only | **none** (informational) |
| **dogfood** (Bundle 3.2, future) | advisory | advisory | advisory | advisory | advisory | **none** (label only) |
| **enforcement** (Bundle 3.3, future, BLOCKED today) | blocking | blocking | blocking | blocking | blocking | any FAIL → merge blocked; any UNKNOWN → merge blocked |

**Critical**: the enforcement column documents the intended behavior. Enforcement is **not authorized** by this document and remains `BLOCK` until the constitutional amendment is ratified and a separate per-PR approval is granted.

### 4.3 Hard rule

A single FAIL gate is sufficient to bar transition to dogfood from shadow, and to bar transition to enforcement from dogfood. There is no partial pass. UNKNOWN is not equivalent to PASS.

---

## 5. Receipt Schema

Every audit evaluation (shadow, dogfood, or — when authorized — enforcement) produces one receipt. Receipts are persisted via the existing `kdexter.audit.evidence_store.EvidenceStore` boundary, **not** by a new store invented here.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `receipt_id` | string (uuid) | yes | Unique per evaluation; suggested prefix `cr050-receipt-` |
| `pr_number` | int | yes | GitHub PR number being evaluated |
| `head_sha` | string | yes | PR head commit SHA at evaluation time |
| `parent_cr` | string (literal) | yes | `"CR-050"` |
| `audit_block_present` | bool | yes | true if the PR body contains a recognized `CR-050 CLEAN-ROOM AUDIT` block |
| `audit_block_parse_status` | enum | yes | `OK` \| `MALFORMED` \| `MISSING` |
| `gate_verdicts` | object | yes | map of 5 gate names → `{PASS, FAIL, UNKNOWN}` |
| `overall_state` | enum | yes | one of the state terms in §6 |
| `created_at` | string (iso-8601 utc) | yes | timestamp of evaluation |
| `actor` | string | yes | static identifier of the evaluator; for shadow phase suggested `"cr050_shadow_audit"` |
| `evidence_bundle_id` | string | yes | EvidenceStore bundle id produced for this receipt (audit chain anchor) |
| `source_doc_refs` | object | yes | `{tier_doc_ref, clean_room_doc_ref, amendment_plan_ref}` as captured from the audit block |
| `rollback_note` | string | yes | plain-text statement of how the receipt is invalidated if needed (see §8 mapping) |

### 5.1 Receipt immutability

Receipts are append-only. Corrections create new receipts referencing the prior `receipt_id` via a `supersedes` field that may be added in a future amendment to this schema (out of scope here).

---

## 6. State Terms

The following state terms are defined for use across shadow / dogfood / enforcement phases. No code emits these today; they are vocabulary for downstream work.

| State | Set When | Allowed Phase(s) |
|-------|----------|------------------|
| `CR050_AUDIT_NOT_REQUIRED` | PR does not inject any external-artifact concept | shadow / dogfood / enforcement |
| `CR050_AUDIT_BLOCK_PRESENT` | Audit block parsed without schema violation | shadow / dogfood / enforcement |
| `CR050_AUDIT_BLOCK_MALFORMED` | Audit block present but schema-invalid | shadow / dogfood / enforcement |
| `CR050_VERDICT_PASS_SHADOW` | All 5 gates PASS, phase = shadow | shadow only |
| `CR050_VERDICT_FAIL_SHADOW` | One or more gates FAIL or UNKNOWN, phase = shadow | shadow only |
| `CR050_VERDICT_PASS_DOGFOOD` | All 5 gates PASS, phase = dogfood | dogfood only |
| `CR050_VERDICT_FAIL_DOGFOOD` | One or more gates FAIL or UNKNOWN, phase = dogfood | dogfood only |
| `CR050_VERDICT_PASS_ENFORCE` | All 5 gates PASS, phase = enforcement | enforcement only (BLOCKED today) |
| `CR050_VERDICT_FAIL_ENFORCE` | One or more gates FAIL or UNKNOWN, phase = enforcement | enforcement only (BLOCKED today) |

### 6.1 State transitions (descriptive, not enforced)

```text
PR opened
  └── audit block detection
        ├── absent + no injection → CR050_AUDIT_NOT_REQUIRED
        ├── absent + injection suspected → MALFORMED treatment
        ├── present + valid → CR050_AUDIT_BLOCK_PRESENT
        └── present + invalid → CR050_AUDIT_BLOCK_MALFORMED
                ↓
        gate evaluation by phase
                ├── shadow → CR050_VERDICT_PASS_SHADOW / FAIL_SHADOW
                ├── dogfood → CR050_VERDICT_PASS_DOGFOOD / FAIL_DOGFOOD
                └── enforcement → CR050_VERDICT_PASS_ENFORCE / FAIL_ENFORCE
                                  (BLOCKED today)
```

---

## 7. Seven-Layer Routing Map

The `routing_layer` audit field accepts only:

| Layer | Status in CR-050 |
|-------|------------------|
| Observation | **allowed** |
| Interpretation | **allowed** |
| Decision | **allowed** |
| Execution | **allowed** |
| Learning | **allowed** |
| Evolution | **forbidden** |
| Constitution | **forbidden** |

The Evolution / Constitution forbidden rule is the same one proposed for constitutional anchoring as **C13** in D1. Until ratification, this document treats it as a **policy-level rule enforced by the seven_layer_routing_gate**.

---

## 8. Forbidden Actions (Bound to This Document)

This document **does not authorize** any of the following:

- Creation of `app/services/cr050_audit_gate.py` or any sibling shadow / dogfood / enforcement module.
- Implementation of an audit block parser (no Python code is sanctioned here).
- Addition of a CI check that consumes this schema.
- Hooking into `app/agents/governance_gate.py`, `app/agents/orchestrator.py`, or `app/main.py`.
- Modification of `strategies/ppf/constitution.py` (C1–C11 invariants).
- Modification of `docs/system_final_constitution.md`.
- Modification of the existing CR-050 parent docs (`cr050_external_artifact_trust_map.md`, `cr050_clean_room_injection_policy.md`).
- Modification of the D1 document (`cr050_constitution_amendment_plan.md`).
- Commit of the Uprich artifact binary, decompiled source, or any reformat thereof.
- Generation of T3 (runtime / protection) or T4 (license / security) replication code.
- Auto-start of D6, Bundle 3.1, Bundle 2 Batch 7, or branch hygiene.
- Interference with PR #107~#110 workstreams.

### 8.1 Rollback note

Because this document creates no runtime state and no code, withdrawal is reversible by a follow-up docs-only PR that removes or marks the file `WITHDRAWN`. No code rollback is required.

---

## 9. Next Dependency

| Doc | Purpose | Status |
|-----|---------|--------|
| D1 — `cr050_constitution_amendment_plan.md` | Constitutional anchor plan (C12/C13) | ✅ merged on main (`0406d31`, PR #120) |
| **D3 — this document** | Audit block + receipt schema | **this PR** |
| D6 — `cr050_shadow_gate_activation_policy.md` | Shadow → dogfood → enforcement transition + kill switch + rollback | HOLD (separate per-PR approval) |
| Bundle 3.1 — shadow skeleton (`_CR050_AUDIT_ENABLED = False`, zero call sites) | First code artifact; consumes D3 schema | HOLD (pending D1 + D3 + D6 merge) |
| Bundle 3.2 — dogfood | Self-evaluating audit blocks | HOLD (pending D2 + D4 + D5) |
| Bundle 3.3 — live enforcement | merge-blocking on FAIL | BLOCK (pending actual constitutional amendment ratification) |

D3 is mandatory before Bundle 3.1 because the skeleton parser has no schema to parse without it.

---

## 10. Final State Verdict

```text
GO     : D3 docs-only PR (this PR) for operator review
HOLD   : D6 (separate per-PR approval)
HOLD   : Bundle 3.1 shadow skeleton (pending D1 + D3 + D6 merge)
HOLD   : Bundle 3.2 dogfood (pending D2 + D4 + D5)
BLOCK  : Bundle 3.3 live enforcement (pending actual constitutional amendment ratification)
BLOCK  : Code wiring of any kind (no skeleton, no gate, no call site, no parser)
BLOCK  : Modification of active constitution (`docs/system_final_constitution.md`)
BLOCK  : Modification of existing CR-050 parent docs and D1
```

---

## 11. Cross-References

**Parent / sibling CR-050 docs:**

- `docs/operations/evidence/cr050_external_artifact_trust_map.md` — tier definitions consumed by `tier_classification_gate`
- `docs/operations/evidence/cr050_clean_room_injection_policy.md` — audit block and verdict gates that this schema makes precise
- `docs/operations/evidence/cr050_constitution_amendment_plan.md` (D1) — proposed C12 / C13 referenced by the seven-layer routing gate

**Governance authority (read-only references):**

- `docs/system_final_constitution.md` — active constitution (unmodified by this schema)
- `docs/operations/change_gate_policy.md` — L0~L4 risk grading (this PR is L0 docs-only)
- `docs/operations/evidence_namespace_policy.md` — namespace pre-flight (relation = Child of CR-050)
- `docs/operations/ci_advisory_triage_policy.md` — B-2 docs-only advisory triage applies if tier-2 mypy reports residual debt

**Audit infrastructure (read-only references):**

- `kdexter.audit.evidence_store.EvidenceStore` (existing boundary; no modification by this doc)
- `app/agents/governance_gate.py` (existing singleton; no modification by this doc)

**Pattern source:**

- `docs/operations/evidence/cr046_three_tier_judgment.md` — header / section / signature convention

---

## Signature

```
CR-050 Injection Audit Block & Receipt Schema (D3)
Canonical Core: K-V3 4-Strategy (S1+S2+S3+S4)
Parent CR: CR-050
Document Class: schema specification (docs-only)
Active Constitution Modification: NONE
Existing CR-050 Doc Modification: NONE
D1 Modification: NONE
Runtime Wiring Authorization: NONE
Parser Implementation Authorization: NONE
CI Check Authorization: NONE
Enforcement Authorization: NONE
Audit Block Fields: 9 required
Gate Verdicts: 5 (tier / forbidden / vocabulary / artifact-independence / seven-layer)
Receipt Fields: 13 required
States Defined: 9 (CR050_AUDIT_NOT_REQUIRED through CR050_VERDICT_FAIL_ENFORCE)
Allowed Routing Layers: Observation, Interpretation, Decision, Execution, Learning
Forbidden Routing Layers: Evolution, Constitution
Namespace Relation: Child of CR-050 (per evidence_namespace_policy.md §3)
Status: DRAFT — awaiting operator sign-off
Prepared by: Implementer
Authority: Operator (운영자)
Date: 2026-05-12
```
