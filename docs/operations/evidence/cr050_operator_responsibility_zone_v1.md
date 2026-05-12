# CR-050: Operator Responsibility Zone v1 (D2)

Date: 2026-05-12
Canonical Core: **K-V3 4-Strategy (S1+S2+S3+S4)**
Parent: **CR-050** (External Artifact Trust Map + Clean-Room Injection Policy)
Child Artifact Declaration: per `docs/operations/evidence_namespace_policy.md` §3 (relation = Child of CR-050)
Sibling on main: D1 (`cr050_constitution_amendment_plan.md`), D3 (`cr050_injection_audit_receipt_spec.md`), D6 (`cr050_shadow_gate_activation_policy.md`)
Authority: Operator (운영자)
Status: DRAFT — awaiting operator sign-off

---

## Plan-Only Clarifier

This document defines **operator-zone responsibility boundaries only**.
It does **not** authorize bypass, circumvention, replication, runtime patching, decompiled-source reuse, code wiring, or enforcement authority.

This is a **boundary-sealing** document, not a permission-expanding one. Listing an activity here as "operator-zone allowed" means **it is restricted to the operator's environment with no AI assistance for circumvention** — it does not become permissible inside K-V3 automation.

No `app/`, `strategies/`, `workers/`, `tests/`, or CI configuration is touched by this document.
No existing CR-050 parent doc, no D1, no D3, no D6, and no `docs/system_final_constitution.md` is modified.

---

## 1. Status, Authority, Parent Relation

| Attribute | Value |
|-----------|-------|
| Document class | Operator-zone scope specification (docs-only) |
| Authority | Operator (운영자) |
| Parent CR | CR-050 |
| Parent docs (read-only references) | `cr050_external_artifact_trust_map.md`, `cr050_clean_room_injection_policy.md` |
| Sibling docs on main | D1 (`cr050_constitution_amendment_plan.md`), D3 (`cr050_injection_audit_receipt_spec.md`), D6 (`cr050_shadow_gate_activation_policy.md`) |
| Namespace relation | Child of CR-050 |
| Namespace pre-flight | `cr050 | relation=Child | inventory_checked=YES` |
| Lifecycle status | DRAFT pending sign-off |
| Authority scope | Operator personal environment only — does **not** grant AI / K-V3 automation any new permission |

---

## 2. Problem Statement

The CR-050 trust map (`cr050_external_artifact_trust_map.md` §6) and the clean-room injection policy (`cr050_clean_room_injection_policy.md` §5) reference an **operator responsibility zone** carve-out for T3 (runtime / protection) and T4 (license / security) artifact analysis. The carve-out is named but **not formally scoped**.

Without a formal scope:

- A T3 / T4 analysis observation could be ambiguously presented as either "operator-zone outcome" or "K-V3 admissible input".
- An AI assistant could be asked to perform circumvention work under the implicit cover of "the operator is doing the analysis anyway".
- Result-flow rules between operator zone and K-V3 vocabulary lack precise admissibility criteria.
- An audit reader cannot tell whether a particular K-V3 file element was clean-room restated or smuggled from operator-zone analysis.

This document closes those gaps. It is a **boundary** document: it tells the operator and any AI assistant exactly which T3 / T4 activities are operator-zone allowed (with strict result-flow restrictions), and which are forbidden everywhere.

---

## 3. Operator-Zone Activities

For each activity the matrix specifies: what the operator may do, what the operator may not do, what AI assistance is provided / withheld, and what (if anything) may flow back into K-V3.

### 3.1 License / Trial logic analysis (T4)

| Field | Value |
|-------|-------|
| Allowed in operator zone | Reading the artifact's license / trial flow in the operator's own environment for legal-compliance assessment |
| Forbidden everywhere | Generating bypass code; suggesting bypass code; copying license-check bodies into K-V3; building a "compatible" license-skip module in K-V3 |
| AI assistance provided | None for bypass; conceptual restatement assistance only (e.g., "this looks like a per-machine trial timer", in plain English) |
| AI assistance withheld | Code generation that replicates, defeats, or circumvents license / trial logic |
| K-V3 impact | None directly. Operator may, **after restatement**, inform K-V3 telemetry policy in natural language only (cross-ref D6 §11) |

### 3.2 DynamicMethod / Marshal runtime analysis (T3)

| Field | Value |
|-------|-------|
| Allowed in operator zone | Reading the artifact's runtime patching pattern (`DynamicMethod`, `Marshal.Copy`, JIT hook installation) for understanding **what protection mechanism exists**, in the operator's own environment |
| Forbidden everywhere | Porting the runtime patching to Python via `ctypes` / `numba` / equivalent; copying the IL / native-pointer logic; generating "the same effect" through different code; integrating any such pattern into K-V3 |
| AI assistance provided | Conceptual restatement to Python idioms **for distinct purposes only** (e.g., "K-V3 uses explicit decorators for the same role"); never replication |
| AI assistance withheld | Code generation that replicates, replaces, or extends T3 patterns; assistance in defeating anti-debug / anti-tamper mechanisms |
| K-V3 impact | None directly. Operator may, **after restatement**, propose a Python-idiom equivalent **for a distinct purpose** through the standard CR / clean-room procedure |

### 3.3 Boundary verification and tier triage

| Field | Value |
|-------|-------|
| Allowed in operator zone | Inspecting an artifact element's structural fingerprint (header tokens, namespace shape, attribute names) to decide whether it is T1, T2, T3, or T4 |
| Forbidden everywhere | Skipping tier classification; classifying into T0 (K-V3 native); reclassifying T3 / T4 as T1 / T2 to permit injection |
| AI assistance provided | Read-only triage assistance: "this token shape suggests T2 obfuscation" |
| AI assistance withheld | Decisions that loosen tier classification; suggestions that "this looks safe enough for T1" without operator confirmation |
| K-V3 impact | A tier table entry only, recorded in `cr050_external_artifact_trust_map.md` (deny-by-default applies for unclassified — see trust map §2 reading rule) |

### 3.4 Legal review of artifact license / EULA

| Field | Value |
|-------|-------|
| Allowed in operator zone | Operator (or operator-engaged counsel) reviewing the artifact's license, EULA, and terms in the operator environment |
| Forbidden everywhere | Generating legal advice; substituting AI summary for legal counsel; recording legal opinions in K-V3 docs as if authoritative |
| AI assistance provided | None |
| AI assistance withheld | All AI assistance for legal review; AI sign-off on license compliance |
| K-V3 impact | None. The operator may **separately** record a legal sign-off in a future `cr050_legal_review_v1.md` (out of scope here); that doc's authority is the operator (not AI) |

---

## 4. Result-Flow Rules

The single most important rule of this document:

> **Operator-zone results may flow back into K-V3 only as natural-language risk notes. They may never enter K-V3 as code, code-equivalent IL / bytecode / pseudocode, identifier copies, transcribed bodies, or transcribed control flow.**

### 4.1 What may flow back

| Form | Example |
|------|---------|
| Natural-language risk note | "The artifact's protection layer reacts to debugger attach; assume runtime introspection of K-V3 by the artifact is opportunistic — this informs our deployment-isolation policy." |
| Tier-table entry update | "Element X reclassified from unknown to T3 after operator inspection." |
| Restated K-V3 vocabulary concept | "Clean-room concept: a per-symbol cooldown after a stop-out, expressed in K-V3 schema fields." |
| Telemetry-boundary policy update (operator-authored) | A future `cr050_telegram_notification_policy_v1.md` (forthcoming) referencing the operator's findings in natural language only |

### 4.2 What may NOT flow back

| Form | Why forbidden |
|------|---------------|
| Decompiled C# / IL bodies pasted as comments or strings | Trust map §5 + clean-room policy §3 |
| `Marshal.Copy` / `DynamicMethod` patterns transliterated to Python | T3 SEALED no-cross |
| License-check or trial-expiry logic ported to Python | T4 SEALED operator zone (the license logic itself never enters K-V3) |
| TPM-circumvention code, anti-debug-removal code, integrity-check skip code | Forbidden everywhere, all phases, all tiers |
| Obfuscated identifier names appearing in K-V3 source / comments | Trust map §5 + clean-room policy §3 |
| Replication of operator-zone observations as "K-V3 has the same thing" | Independence test (clean-room §4 Step C) is breached |

### 4.3 Restatement requirement

Before any operator-zone observation enters K-V3 — even as a natural-language risk note — it must pass clean-room policy §4 Step B (Restate):

1. Rewrite in K-V3 vocabulary (English / Python identifiers).
2. Strip every artifact identifier; the text must contain zero Uprich names.
3. The restatement must be reviewable as a standalone document with no reference back to the artifact.

A K-V3 PR that injects an operator-zone-derived risk note must include the standard CR-050 audit block (per D3) with `operator_zone_reliance: YES`.

---

## 5. Forbidden Actions (Bound to This Document)

This document **does not authorize** any of the following, regardless of who performs them:

- Generation of bypass, circumvention, replication, or runtime-patching code by any AI assistant.
- Commit of the Uprich artifact binary, decompiled source, IL listings, or any reformat thereof.
- Generation of T3 (runtime / protection) or T4 (license / security) replication code.
- Modification of `docs/system_final_constitution.md`.
- Modification of the existing CR-050 parent docs (`cr050_external_artifact_trust_map.md`, `cr050_clean_room_injection_policy.md`).
- Modification of D1 (`cr050_constitution_amendment_plan.md`), D3 (`cr050_injection_audit_receipt_spec.md`), or D6 (`cr050_shadow_gate_activation_policy.md`).
- Creation of `app/services/cr050_audit_gate.py` or any other code module by this document.
- Addition of a parser, CI check, runtime hook, gate module, or call site by this document.
- Activation of any phase, kill-switch state, or enforcement transition.
- Reclassification of any T3 / T4 element as T1 / T2 for the purpose of injection.
- Auto-start of D4, D5, Bundle 3.1, Bundle 2 Batch 7, or branch hygiene.
- Interference with PR #107~#110 workstreams.

### 5.1 Carve-out non-expansion

Naming an activity in §3 as "operator-zone allowed" **does not expand** what is permissible inside K-V3 automation. Each row of §3 explicitly carries a "Forbidden everywhere" column for that reason.

---

## 6. State Terms

The following state terms are defined for use across the operator-zone lifecycle. **No code emits them today**; they are vocabulary for downstream activity logs and receipts.

| State | Meaning | Set when |
|-------|---------|----------|
| `CR050_OPERATOR_ZONE_INACTIVE` | No operator-zone activity in progress for the relevant artifact element | Default |
| `CR050_OPERATOR_ZONE_ACTIVE_T3_ANALYSIS` | Operator is currently analyzing a T3 element (runtime / protection) in the operator environment | Operator declares activity start |
| `CR050_OPERATOR_ZONE_ACTIVE_T4_ANALYSIS` | Operator is currently analyzing a T4 element (license / security) in the operator environment | Operator declares activity start |
| `CR050_OPERATOR_ZONE_RESULT_PENDING_RESTATEMENT` | An observation is captured but not yet restated per §4.3 | After analysis ends, before injection |
| `CR050_OPERATOR_ZONE_RESULT_INJECTED_AS_RISK_NOTE` | An observation has been restated and injected into K-V3 as a natural-language risk note via a CR-050 audit-block-bearing PR | When the injection PR merges |

State transitions are descriptive markers, not enforced flags. Downstream evidence documents may reference these states in audit logs.

---

## 7. Operator-Zone Activity Receipt Schema

When an operator-zone activity is conducted with intent to potentially inform K-V3, the operator records a receipt. Receipts are persisted via the existing `kdexter.audit.evidence_store.EvidenceStore` boundary (no new store invented here).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `receipt_id` | string (uuid) | yes | Suggested prefix `cr050-operator-zone-` |
| `tier` | enum | yes | `T3` \| `T4` (this document scopes T3 / T4 only) |
| `activity` | enum | yes | `LICENSE_TRIAL_ANALYSIS` \| `RUNTIME_PATCH_ANALYSIS` \| `BOUNDARY_VERIFICATION` \| `LEGAL_REVIEW` |
| `operator_decision` | enum | yes | `ANALYSIS_ONLY` \| `INJECT_AS_RISK_NOTE` \| `WITHDRAW` |
| `result_class` | enum | yes | `NATURAL_LANGUAGE_RISK_NOTE` \| `NONE` |
| `injected_into_kv3` | bool | yes | `true` only if a CR-050 audit-block-bearing PR carries the restated risk note |
| `injection_pr_ref` | string \| null | yes | PR number / SHA if `injected_into_kv3 == true`; else `null` |
| `created_at` | string (iso-8601 utc) | yes | Timestamp of receipt creation |
| `rollback_note` | string | yes | Plain-text statement of how the receipt is invalidated if needed (e.g., "withdraw by issuing a superseding receipt with `operator_decision = WITHDRAW`") |

### 7.1 Append-only

Receipts are append-only. A withdrawal creates a new receipt referencing the prior `receipt_id`; the original receipt is not edited.

### 7.2 No K-V3 enforcement of receipt presence by this document

The receipt schema is defined here; no code or CI check that **enforces** receipt creation is authorized by this document. Enforcement, if and when desired, is a separate per-PR operator approval.

---

## 8. Seven-Layer Mapping

Operator-zone results that are injected back into K-V3 (per §4) are subject to D3's `seven_layer_routing_gate`:

- **Allowed routing layers**: Observation, Interpretation, Decision, Execution, Learning.
- **Forbidden routing layers**: Evolution, Constitution.

D2 does not relax the seven-layer rule. Operator-zone observations destined for Evolution / Constitution layers are **rejected at the routing gate**, regardless of operator-zone provenance.

D3 remains authoritative on routing decisions; D2 governs the **upstream admissibility** of the observation itself.

---

## 9. Next Dependency

| Doc / Bundle | Purpose | Status |
|--------------|---------|--------|
| D1 — `cr050_constitution_amendment_plan.md` | Constitutional anchor plan | ✅ merged (`0406d31`, PR #120) |
| D3 — `cr050_injection_audit_receipt_spec.md` | Audit block + receipt schema | ✅ merged (`64c5a4e`, PR #121) |
| D6 — `cr050_shadow_gate_activation_policy.md` | Activation phases + kill switch + rollback | ✅ merged (`280cbb0`, PR #122) |
| **D2 — this document** | Operator-zone scope + result-flow rules | **this PR** |
| D4 — `cr050_parameter_slots_policy.md` | T1 slot K-V3 mapping | HOLD (separate per-PR approval) |
| D5 — `cr050_risk_control_slots_policy.md` | T1/T2 → Decision/Execution restrictions | HOLD (separate per-PR approval) |
| Bundle 3.1 — shadow skeleton | First code artifact; eligible for separate per-PR approval after D6 merge | HOLD |
| Bundle 3.2 — dogfood | Self-evaluation | HOLD (pending D2 + D4 + D5 + Bundle 3.1) |
| Bundle 3.3 — live enforcement | Merge-blocking | BLOCK (pending actual constitutional amendment ratification) |

D2 closes one of the three remaining Bundle 3.2 prerequisite docs (D2 + D4 + D5). It does **not** unlock Bundle 3.2 by itself.

---

## 10. Final State Verdict

```text
GO     : D2 docs-only PR (this PR) for operator review
HOLD   : D4 (separate per-PR approval)
HOLD   : D5 (separate per-PR approval)
HOLD   : Bundle 3.1 shadow skeleton (eligible for separate approval; not auto-started)
HOLD   : Bundle 3.2 dogfood (pending D2 + D4 + D5 + Bundle 3.1)
BLOCK  : Bundle 3.3 live enforcement (pending actual constitutional amendment ratification)
BLOCK  : Code wiring of any kind by this PR
BLOCK  : Modification of active constitution by this PR
BLOCK  : Modification of CR-050 parent docs, D1, D3, or D6 by this PR
BLOCK  : AI generation of bypass / circumvention / replication / patching code at any time
```

---

## 11. Cross-References

**Parent / sibling CR-050 docs:**

- `docs/operations/evidence/cr050_external_artifact_trust_map.md` — tier definitions (T0–T4), §6 operator-responsibility zone reference
- `docs/operations/evidence/cr050_clean_room_injection_policy.md` — Extract → Restate → Implement procedure, §5 operator-zone reference
- `docs/operations/evidence/cr050_constitution_amendment_plan.md` (D1) — proposed C12 / C13 plan
- `docs/operations/evidence/cr050_injection_audit_receipt_spec.md` (D3) — audit block / receipt schema (operator_zone_reliance field)
- `docs/operations/evidence/cr050_shadow_gate_activation_policy.md` (D6) — activation phases (operator-zone activity is independent of phase, but injection back to K-V3 must observe phase rules)

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
CR-050 Operator Responsibility Zone v1 (D2)
Canonical Core: K-V3 4-Strategy (S1+S2+S3+S4)
Parent CR: CR-050
Document Class: operator-zone scope specification (docs-only)
Active Constitution Modification: NONE
Existing CR-050 Doc Modification: NONE
D1 Modification: NONE
D3 Modification: NONE
D6 Modification: NONE
Runtime Wiring Authorization: NONE
Parser / CI Check / Gate Module / Call Site Authorization: NONE
Phase Transition Authorization: NONE
Bypass / Circumvention / Replication / Patching Code: FORBIDDEN at all times
Activities Scoped: 4 (License/Trial T4, Runtime/Marshal T3, Boundary Verification, Legal Review)
Result-Flow: natural-language risk notes only, after restatement
Receipt Fields: 9 required
States Defined: 5 (CR050_OPERATOR_ZONE_INACTIVE through CR050_OPERATOR_ZONE_RESULT_INJECTED_AS_RISK_NOTE)
Allowed Routing Layers: Observation, Interpretation, Decision, Execution, Learning (per D3)
Forbidden Routing Layers: Evolution, Constitution (per D3)
Namespace Relation: Child of CR-050 (per evidence_namespace_policy.md §3)
Status: DRAFT — awaiting operator sign-off
Prepared by: Implementer
Authority: Operator (운영자)
Date: 2026-05-12
```
