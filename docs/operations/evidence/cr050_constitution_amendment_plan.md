# CR-050: Constitution Amendment Plan

Date: 2026-05-12
Canonical Core: **K-V3 4-Strategy (S1+S2+S3+S4)**
Parent: **CR-050** (External Artifact Trust Map + Clean-Room Injection Policy)
Child Artifact Declaration: per `docs/operations/evidence_namespace_policy.md` §3 (relation = Child of CR-050)
Authority: Operator (운영자)
Status: DRAFT — awaiting operator sign-off

---

## Plan-Only Clarifier

This document is an **amendment plan, not an amendment**.
It does **not** modify the active constitution at `docs/system_final_constitution.md`.
It does **not** authorize CR-050 runtime wiring, gate skeleton creation, dogfood activation, or live enforcement.

The active constitution remains unchanged until a separate amendment process is run end-to-end.

---

## 1. Problem Statement

CR-050 introduced two governance documents on main (`cr050_external_artifact_trust_map.md`, `cr050_clean_room_injection_policy.md`) that define how external artifact concepts (Uprich Future Bot v1.5.4) may enter K-V3. The policies impose two structural rules that the **active constitution does not yet anchor**:

1. External artifact concepts are admissible **only** at trust tiers T1 / T2, and **only** through the Extract → Restate → Implement procedure.
2. The K-V3 7-layer architecture must accept artifact-derived concepts at five layers (Observation / Interpretation / Decision / Execution / Learning), and must **reject** them at two layers (Evolution / Constitution).

Without constitutional anchors, the CR-050 policies are ungrounded:

- A future CR-050 wiring PR (shadow / dogfood / enforcement) could be challenged as exceeding policy authority.
- The Evolution and Constitution layers have no constitutional clause that explicitly **forbids** external concept ingestion.
- The trust tier verdict matrix (T3/T4 SEALED) cannot be enforced without a constitutional rule it derives from.

This document **plans** the constitutional clauses that would close those gaps. Drafting and ratifying the actual amendment is **out of scope** here.

---

## 2. Proposed Amendment Concepts (Plan Only)

The following two clauses are proposed for the eventual amendment. Names (`C12`, `C13`) are placeholders; final clause numbering is decided when the amendment is drafted.

### 2.1 Proposed C12 — External Artifact Concept Non-Injection

**Intent (plan-language only):**

- External artifact concepts shall not enter K-V3 code, schemas, evidence, or runtime state except through the procedure declared in `cr050_clean_room_injection_policy.md` §4 (Extract → Restate → Implement).
- Trust tiers T3 and T4 are SEALED at all times. No K-V3 module may import, reference, or operationally consume T3/T4 elements.
- Default tier for any unclassified artifact element is T3 (deny-by-default).

**Why constitutional, not policy-only:**

A policy alone may be revised by routine PR. A constitutional clause requires the amendment procedure, which raises the bar for any future relaxation of T3/T4 SEALED status.

**What this clause does NOT do:**

- Does not authorize creation of `app/services/cr050_audit_gate.py` or any other gate module.
- Does not authorize hooking into `GovernanceGate.pre_check` or `strategies/ppf/constitution.py`.
- Does not approve any PR that copies decompiled bodies, even with a TODO comment.

### 2.2 Proposed C13 — Seven-Layer Routing Restriction

**Intent (plan-language only):**

- Artifact-derived concepts (T1, T2) may only be routed to: **Observation, Interpretation, Decision, Execution, Learning**.
- The **Evolution** and **Constitution** layers shall not receive any input derived from an external artifact, at any tier, under any condition.
- Routing decisions are recorded in the per-PR audit block (see future D3 — `cr050_injection_audit_receipt_spec.md`).

**Why constitutional:**

The 7-layer architecture is the structural backbone of K-V3. A routing exception introduced via policy-only patch could erode the boundary; a constitutional clause forces such an exception through amendment review.

---

## 3. Seven-Layer Mapping (Authority Reference)

| K-V3 Layer | Accepts External Concepts? | Allowed Source Tiers | Constitutional Anchor |
|------------|----------------------------|----------------------|-----------------------|
| Observation | Yes (through future approved slots) | T1 | proposed C13 |
| Interpretation | Yes | T1, T2 (re-derived) | proposed C13 |
| Decision | Yes | T1, T2 (re-derived) | proposed C13 |
| Execution | Yes | T1 (shape only) | proposed C13 |
| Learning | Yes | T2 (failure-mode templates) | proposed C13 |
| **Evolution** | **No (constitutional bar)** | — | proposed C13 |
| **Constitution** | **No (constitutional bar)** | — | proposed C13 |

The seven-layer mapping in `cr050_clean_room_injection_policy.md` §6 already states this rule as a policy. The amendment plan elevates the **Evolution / Constitution rejection** to constitutional status.

---

## 4. State Terms (Plan-Defined, Not Implemented)

The following states are defined here in **natural language only**. They are not implemented in code by this document.

| State | Meaning | Set by | Cleared by |
|-------|---------|--------|------------|
| `CR050_AMENDMENT_PLANNED` | This document is on main; amendment is planned but not drafted. | Merge of this PR | Drafting the actual amendment text in a successor doc |
| `CR050_AMENDMENT_NOT_APPLIED` | The active constitution has not been modified. | Default (until ratification) | Ratification commit on `docs/system_final_constitution.md` |
| `CR050_WIRING_BLOCKED_PENDING_AMENDMENT` | No CR-050 wiring (shadow / dogfood / enforcement) may proceed because the amendment is not yet applied. | Default | Successful ratification + Bundle 3.1 separate approval |

The three states are descriptive markers, not enforced flags. They exist so that downstream evidence documents can reference a stable vocabulary.

---

## 5. Audit / Receipt Requirements

When the eventual amendment PR is drafted (out of scope here), it must record an audit block with the following fields:

| Field | Type | Source | Required |
|-------|------|--------|----------|
| `amendment_plan_id` | string | this document's stable identifier (`cr050_constitution_amendment_plan`) | yes |
| `parent_doc_ref` | string | path + commit SHA of CR-050 parent (`cr050_external_artifact_trust_map.md @ <sha>`) | yes |
| `proposed_clause_ids` | list[string] | e.g. `["C12", "C13"]` (placeholder names retained until amendment) | yes |
| `operator_decision` | enum | `PLANNED` \| `DRAFTING` \| `RATIFIED` \| `WITHDRAWN` | yes |
| `created_at` | iso-8601 utc | timestamp of decision change | yes |
| `rollback_note` | string | how the plan is unwound if withdrawn before ratification | yes |

For this PR (the plan itself), the receipt values are:

```
amendment_plan_id   = cr050_constitution_amendment_plan
parent_doc_ref      = docs/operations/evidence/cr050_external_artifact_trust_map.md @ d2ba463
proposed_clause_ids = [C12, C13]
operator_decision   = PLANNED
created_at          = 2026-05-12T00:00:00Z
rollback_note       = Withdraw by deleting this file in a follow-up docs-only PR; no
                      runtime state is created by this document, so withdrawal is
                      reversible without code rollback.
```

---

## 6. Forbidden Actions (Bound to This Document)

This document **does not authorize** any of the following, now or by implication of merge:

- Creation of `app/services/cr050_audit_gate.py` or any sibling shadow / dogfood / enforcement module.
- Hooking into `app/agents/governance_gate.py` (`GovernanceGate.pre_check`, `post_record`).
- Modification of `app/agents/orchestrator.py` (Step 5.75 integration path).
- Modification of `app/main.py` (governance gate DI).
- Modification of `strategies/ppf/constitution.py` (C1–C11 invariants).
- Modification of `docs/system_final_constitution.md` (the active constitution).
- Modification of `docs/operations/evidence/cr050_external_artifact_trust_map.md`.
- Modification of `docs/operations/evidence/cr050_clean_room_injection_policy.md`.
- Activation of live enforcement at any layer.
- Commit of the Uprich artifact binary, decompiled source, or any reformat thereof.
- Generation of T3 (runtime / protection) or T4 (license / security) replication code.
- Interference with PR #107~#110 workstreams.
- Auto-start of Bundle 2 Batch 7 or any other batch.
- Branch hygiene operations.

Any future PR that performs the above must obtain its own operator approval and cite its own evidence chain.

---

## 7. Next Dependencies (Sequencing)

This document is the **first** of the Bundle 3.0 docs-only series. The minimum precedent set for Bundle 3.1 (shadow skeleton, call site 0) is:

| Order | Doc | Purpose | Status |
|-------|-----|---------|--------|
| **1** | **this doc — cr050_constitution_amendment_plan.md** | Anchor C12/C13 plan | **this PR** |
| 2 | `cr050_injection_audit_receipt_spec.md` (D3) | audit block + receipt JSON-schema | future PR-β |
| 3 | `cr050_shadow_gate_activation_policy.md` (D6) | shadow → dogfood → enforcement transition + kill switch + rollback | future PR-γ |

After all three are on main, Bundle 3.1 (shadow-only skeleton, `_CR050_AUDIT_ENABLED=False`, zero call sites) may be **separately proposed** for operator approval. No code is authored before then.

Bundle 3.2 (dogfood) and Bundle 3.3 (enforcement) require additional docs (D2, D4, D5) and, for 3.3, the actual constitutional amendment ratification, which is out of scope of this plan.

---

## 8. Final State Verdict

```text
GO     : D1 docs-only PR (this PR) for operator review
HOLD   : D3, D6 (require separate per-PR approval)
HOLD   : Bundle 3.1 shadow skeleton (pending D1 + D3 + D6 merge)
HOLD   : Bundle 3.2 dogfood (pending D2 + D4 + D5)
BLOCK  : Bundle 3.3 live enforcement (pending actual constitutional amendment ratification)
BLOCK  : Code wiring of any kind (no skeleton, no gate, no call site, no flag flip)
BLOCK  : Modification of active constitution (`docs/system_final_constitution.md`)
BLOCK  : Modification of existing CR-050 docs (trust map, clean-room policy)
```

---

## 9. Cross-References

**Parent / sibling CR-050 docs:**

- `docs/operations/evidence/cr050_external_artifact_trust_map.md` — tier definitions (T0–T4) that this amendment plan grounds constitutionally
- `docs/operations/evidence/cr050_clean_room_injection_policy.md` — Extract → Restate → Implement procedure that this plan elevates

**Governance authority (read-only references):**

- `docs/system_final_constitution.md` — the active constitution (unmodified by this plan)
- `strategies/ppf/constitution.py` — C1–C11 invariant pattern (proposed C12/C13 extend the same family, conceptually)
- `docs/operations/change_gate_policy.md` — L0~L4 change-risk grading (this PR is L0 docs-only)
- `docs/operations/evidence_namespace_policy.md` — namespace pre-flight (relation = Child of CR-050)
- `docs/operations/ci_advisory_triage_policy.md` — B-2 docs-only advisory triage applies if tier-2 mypy reports residual debt

**Pattern source:**

- `docs/operations/evidence/cr046_three_tier_judgment.md` — header / section / signature convention

---

## Signature

```
CR-050 Constitution Amendment Plan
Canonical Core: K-V3 4-Strategy (S1+S2+S3+S4)
Parent CR: CR-050
Document Class: amendment plan (NOT amendment)
Constitution Modification: NONE
Runtime Wiring Authorization: NONE
Proposed Clauses (placeholders): C12 (non-injection), C13 (7-layer routing restriction)
States Defined (plan-only): CR050_AMENDMENT_PLANNED, CR050_AMENDMENT_NOT_APPLIED, CR050_WIRING_BLOCKED_PENDING_AMENDMENT
Operator Decision: PLANNED
Namespace Relation: Child of CR-050 (per evidence_namespace_policy.md §3)
Status: DRAFT — awaiting operator sign-off
Prepared by: Implementer
Authority: Operator (운영자)
Date: 2026-05-12
```
