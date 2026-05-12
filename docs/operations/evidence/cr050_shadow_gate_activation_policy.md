# CR-050: Shadow Gate Activation Policy (D6)

Date: 2026-05-12
Canonical Core: **K-V3 4-Strategy (S1+S2+S3+S4)**
Parent: **CR-050** (External Artifact Trust Map + Clean-Room Injection Policy)
Child Artifact Declaration: per `docs/operations/evidence_namespace_policy.md` §3 (relation = Child of CR-050)
Sibling on main: D1 (`cr050_constitution_amendment_plan.md`), D3 (`cr050_injection_audit_receipt_spec.md`)
Authority: Operator (운영자)
Status: DRAFT — awaiting operator sign-off

---

## Plan-Only Clarifier

This document defines **activation boundaries only**.
It does **not** create or authorize code, parser logic, gate modules, CI checks, runtime hooks, call sites, or enforcement authority.

No `app/`, `strategies/`, `workers/`, `tests/`, or CI configuration is touched by this document.
No existing CR-050 parent doc, no D1, no D3, and no `docs/system_final_constitution.md` is modified.

This is an **activation policy**, not an **activation approval**. The presence of phase names and transition criteria here does not authorize transitioning into any phase — each transition requires its own per-PR operator approval.

---

## 1. Status, Authority, Parent Relation

| Attribute | Value |
|-----------|-------|
| Document class | Activation policy specification (docs-only) |
| Authority | Operator (운영자) |
| Parent CR | CR-050 |
| Parent docs (read-only references) | `cr050_external_artifact_trust_map.md`, `cr050_clean_room_injection_policy.md` |
| Sibling docs on main | D1 (`cr050_constitution_amendment_plan.md`), D3 (`cr050_injection_audit_receipt_spec.md`) |
| Namespace relation | Child of CR-050 |
| Namespace pre-flight | `cr050 | relation=Child | inventory_checked=YES` |
| Lifecycle status | DRAFT pending sign-off |
| Default activation state | `CR050_SHADOW_DISABLED` |

---

## 2. Problem Statement

D1 establishes the constitutional amendment plan. D3 establishes the audit block and receipt schema. Neither defines **when, how, and under what conditions** the CR-050 audit logic may transition from pure-documentation into shadow-only, dogfood, or enforcement modes.

Without an activation policy:

- A Bundle 3.1 shadow skeleton PR has no documented entry criteria.
- A dogfood transition has no documented prerequisite checklist.
- An enforcement transition has no documented rollback authority.
- Kill-switch semantics are undefined; a misbehaving gate could not be safely disabled.

This document fills that gap. It is consumed by — but does not create — every downstream CR-050 activation transition.

---

## 3. Activation Phases

Exactly five phases are defined. Phase names are stable identifiers; transitions are unidirectional in the steady state, with explicit downgrade paths defined in §7.

| Phase | Name | Plain-English summary |
|-------|------|------------------------|
| 0 | `PHASE_0_DOCS_ONLY` | All CR-050 artifacts are markdown only. No code, no parser, no gate, no CI hook. |
| 1 | `PHASE_1_SHADOW_SKELETON` | A non-call-site Python module exists, `_CR050_AUDIT_ENABLED = False`. No external caller. Records nothing yet. |
| 2 | `PHASE_2_DOGFOOD_AUDIT` | The module evaluates its own PRs' audit blocks (and prior CR-050 PR bodies) and writes receipts to `EvidenceStore`. Verdicts are **advisory** — they do not block merges. |
| 3 | `PHASE_3_ENFORCEMENT_CANDIDATE` | The module evaluates all qualifying PRs. Verdicts are **labeled** (PASS / FAIL) but still **non-blocking**. A trial period gathers signal before enforcement. |
| 4 | `PHASE_4_LIVE_ENFORCEMENT` | The module's FAIL verdict blocks merge of qualifying PRs. Requires a ratified constitutional amendment (per D1) and a separate per-transition operator approval. |

### 3.1 Current state

```text
Active phase     = PHASE_0_DOCS_ONLY
Default state    = CR050_SHADOW_DISABLED
Transition to 1  = HOLD (requires D1 + D3 + D6 all merged + separate Bundle 3.1 approval)
Transition to 2  = HOLD (requires D2 + D4 + D5 all merged + separate approval)
Transition to 3  = HOLD (requires §4 PHASE_3 prerequisites + separate approval)
Transition to 4  = BLOCK (requires actual constitutional amendment ratification per D1)
```

---

## 4. Phase Permissions

For each phase the following matrix governs what is allowed and forbidden. **The matrix is descriptive; entering a phase requires a separate per-PR operator approval that cites this matrix.**

### 4.1 `PHASE_0_DOCS_ONLY` (current)

| Field | Value |
|-------|-------|
| Allowed actions | New markdown CR-050 child artifacts; docs-only PRs |
| Forbidden actions | Any Python code, any CI check, any parser, any call site, any gate module |
| Required prior documents | None beyond parent CR-050 docs and ongoing CR-050 children |
| Required receipts | None (docs PRs use namespace pre-flight only) |
| Rollback authority | Operator (delete or supersede the doc via follow-up PR) |
| Merge blocking | Not allowed (advisory CI failures handled by B-2 docs-only auto-triage) |

### 4.2 `PHASE_1_SHADOW_SKELETON`

| Field | Value |
|-------|-------|
| Allowed actions | Single new Python module (e.g. `app/services/cr050_audit_gate.py`) with `_CR050_AUDIT_ENABLED = False`, zero call sites, zero CI hooks |
| Forbidden actions | Calling the module from any existing code path; emitting receipts; reading PR bodies; modifying `GovernanceGate` / orchestrator / `app/main.py` / `strategies/ppf/constitution.py`; adding CI checks |
| Required prior documents | D1 + D3 + D6 all merged on main |
| Required receipts | One activation receipt (§8) recording phase 0 → 1 transition |
| Rollback authority | Operator (delete the module in a follow-up PR; no runtime impact because call sites = 0) |
| Merge blocking | Not allowed (gate is disabled and not wired) |

### 4.3 `PHASE_2_DOGFOOD_AUDIT`

| Field | Value |
|-------|-------|
| Allowed actions | Enable parser logic to read PR bodies (read-only HTTP); evaluate own and prior CR-050 PRs; write receipts to existing `EvidenceStore`; emit logs |
| Forbidden actions | Blocking merges; modifying `GovernanceGate.pre_check` to enforce; modifying the active constitution; activating runtime hooks beyond receipt write |
| Required prior documents | D1 + D3 + D6 merged **plus** D2 (operator zone), D4 (parameter slots), D5 (risk control slots) merged |
| Required receipts | Activation receipt for phase 1 → 2 + at least one self-evaluation receipt before approval |
| Rollback authority | Operator may downgrade to phase 1 via PR that flips `_CR050_AUDIT_ENABLED = False` and stops new receipt writes |
| Merge blocking | Not allowed (verdicts are advisory) |

### 4.4 `PHASE_3_ENFORCEMENT_CANDIDATE`

| Field | Value |
|-------|-------|
| Allowed actions | Label PRs with verdict (PASS / FAIL); attach CI advisory check; gather statistics over a trial window |
| Forbidden actions | Blocking merges; touching `system_final_constitution.md`; expanding scope beyond CR-050 audit evaluation |
| Required prior documents | All preceding (D1+D2+D3+D4+D5+D6 merged) + a separate **phase 3 readiness evidence doc** authored as a CR-050 grandchild |
| Required receipts | Activation receipt for phase 2 → 3 + a minimum number of phase-2 receipts (count to be set when the phase 3 readiness doc is authored; not bound here) |
| Rollback authority | Operator may downgrade to phase 2 with a single docs-only or single-config PR |
| Merge blocking | Not allowed (only labeling) |

### 4.5 `PHASE_4_LIVE_ENFORCEMENT`

| Field | Value |
|-------|-------|
| Allowed actions | Block merges of qualifying PRs that produce FAIL verdicts |
| Forbidden actions | Bypassing the gate; silently disabling it; widening scope beyond CR-050 |
| Required prior documents | All of the above **plus a ratified constitutional amendment** (per D1 C12 / C13 or equivalent — actual constitutional change, not the plan) |
| Required receipts | Activation receipt for phase 3 → 4 with explicit constitutional ratification reference + operator approval receipt + a CI-status receipt |
| Rollback authority | Operator + constitutional review (see §7.5) |
| Merge blocking | Allowed (this is the only phase that blocks) |

---

## 5. Required Preconditions

### 5.1 Document prerequisites (cumulative)

| Phase | Documents that must be merged on main first |
|-------|---------------------------------------------|
| 0 → 1 | Parent CR-050 docs + D1 + D3 + D6 |
| 1 → 2 | Phase 0 → 1 set + D2 + D4 + D5 |
| 2 → 3 | Phase 1 → 2 set + a phase 3 readiness evidence doc (CR-050 grandchild, future) |
| 3 → 4 | Phase 2 → 3 set + ratified constitutional amendment commit on `docs/system_final_constitution.md` |

### 5.2 Locked state at this PR

- ✓ Parent CR-050 docs: live on main
- ✓ D1: merged on main (`0406d31`, PR #120)
- ✓ D3: merged on main (`64c5a4e`, PR #121)
- ⏳ D6: this PR (pending merge)
- ⏳ D2 / D4 / D5: not started
- ⏳ Phase 3 readiness doc: not started
- ⏳ Constitutional amendment ratification: BLOCK

Therefore at the moment of this document's authorship, the only transition that becomes **eligible for separate per-PR approval** after this PR merges is **phase 0 → 1** (and that approval has **not** been granted by this document).

---

## 6. Kill Switch Policy

Kill switches are operator-controlled markers. The current document defines the **states** and the **default**, not a code mechanism for flipping them.

| State | Meaning | Default? |
|-------|---------|----------|
| `CR050_SHADOW_DISABLED` | Module either does not exist (phase 0) or exists with `_CR050_AUDIT_ENABLED = False` and zero call sites (phase 1 entered, gate disabled) | **YES** (initial state) |
| `CR050_SHADOW_ENABLED_RECORD_ONLY` | Module is wired to read PR bodies and write receipts; verdicts informational only | no |
| `CR050_DOGFOOD_ENABLED_ADVISORY` | Module evaluates own and prior CR-050 PRs; verdicts visible but advisory | no |
| `CR050_ENFORCEMENT_CANDIDATE` | Module evaluates all qualifying PRs; verdicts labeled but non-blocking | no |
| `CR050_ENFORCEMENT_ENABLED` | Module's FAIL verdict blocks merge | no |

### 6.1 Hard rules

- The default state at every fresh install / fresh deploy is `CR050_SHADOW_DISABLED`.
- A state change is **only** valid when accompanied by an activation receipt (§8) and a per-PR operator approval.
- A kill switch downgrade (e.g., `CR050_ENFORCEMENT_ENABLED` → `CR050_DOGFOOD_ENABLED_ADVISORY`) does **not** require constitutional review; an upgrade does (for transitions into `CR050_ENFORCEMENT_ENABLED`).
- A `CR050_SHADOW_DISABLED` state may be entered from **any** higher state without delay; it is the safe fallback.

---

## 7. Rollback Policy

Rollback is defined per phase. Live-enforcement rollback has the strictest requirements.

### 7.1 Docs-only rollback (phase 0)

- Method: follow-up docs-only PR that deletes or marks the file `WITHDRAWN`.
- Authority: operator.
- Receipt: a withdrawal note in the follow-up PR body suffices.
- Runtime impact: none.

### 7.2 Shadow skeleton rollback (phase 1)

- Method: single PR that deletes the module file.
- Authority: operator.
- Receipt: activation receipt with `phase_to = PHASE_0_DOCS_ONLY` and `operator_decision = ROLLBACK`.
- Runtime impact: none (call sites = 0).

### 7.3 Dogfood rollback (phase 2)

- Method: single PR that flips `_CR050_AUDIT_ENABLED = False`, removes call sites if any were added during phase 2, and stops new receipt writes. Existing receipts remain (append-only).
- Authority: operator.
- Receipt: activation receipt with `phase_to = PHASE_1_SHADOW_SKELETON` or `PHASE_0_DOCS_ONLY`.
- Runtime impact: gate stops emitting new receipts; CI advisory status returns to baseline.

### 7.4 Enforcement-candidate rollback (phase 3)

- Method: single PR that removes the CI advisory check and downgrades the state to `CR050_DOGFOOD_ENABLED_ADVISORY` or `CR050_SHADOW_ENABLED_RECORD_ONLY`.
- Authority: operator.
- Receipt: activation receipt with `phase_to = PHASE_2_DOGFOOD_AUDIT` and `risk_assessment` documenting the trial-window observations.
- Runtime impact: labels disappear; receipts persist; merge behavior unchanged (already non-blocking).

### 7.5 Live enforcement emergency rollback (phase 4)

Live enforcement rollback **must** require **all** of the following:

| Requirement | Justification |
|-------------|---------------|
| Operator approval (explicit, time-stamped) | Live blocking affects every qualifying PR; operator is the final authority |
| Rollback receipt with `phase_to`, `operator_decision = EMERGENCY_ROLLBACK`, `risk_assessment` | Audit chain integrity |
| Constitutional review note (operator-authored) confirming the rollback does not violate the ratified amendment | A live enforcement gate is anchored to a ratified clause; rollback must reconcile |
| Separate PR (not a config flip) that removes the blocking behavior and re-labels state to `CR050_DOGFOOD_ENABLED_ADVISORY` or lower | Single-commit traceability |

A live enforcement gate may be **suspended** (not removed) under emergency by an operator-issued kill-switch receipt that moves state to `CR050_SHADOW_DISABLED`; full rollback still requires the four items above. Suspension is documented as a separate receipt.

---

## 8. Activation Receipt Schema

Every phase transition (forward or backward) produces one activation receipt. Receipts are persisted via the existing `kdexter.audit.evidence_store.EvidenceStore` boundary (no new store invented here).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `receipt_id` | string (uuid) | yes | Suggested prefix `cr050-activation-` |
| `phase_from` | enum | yes | one of the five phase names |
| `phase_to` | enum | yes | one of the five phase names |
| `operator_decision` | enum | yes | `PROCEED` \| `ROLLBACK` \| `EMERGENCY_ROLLBACK` \| `SUSPEND` |
| `prerequisite_docs` | list[string] | yes | list of CR-050 doc refs verified prior to transition |
| `ci_status` | object | yes | summary of last CI run (lint / build / tier-1 / test / advisory) |
| `evidence_refs` | list[string] | yes | EvidenceStore bundle ids consulted (e.g., prior phase receipts) |
| `risk_assessment` | string | yes | operator-authored note on observed risk and mitigations |
| `rollback_plan` | string | yes | how this transition would be undone (cross-ref to §7) |
| `created_at` | string (iso-8601 utc) | yes | timestamp |
| `actor` | string | yes | static identifier (e.g., `cr050_activation_operator`) |

### 8.1 Append-only

Receipts are append-only. A rollback creates a new receipt; the original transition receipt is not edited.

---

## 9. State Terms

| State | Meaning |
|-------|---------|
| `CR050_GATE_NOT_INSTALLED` | Phase 0; no Python module exists |
| `CR050_GATE_SHADOW_DISABLED` | Phase 1; module exists but disabled and unwired |
| `CR050_GATE_SHADOW_RECORD_ONLY` | Phase 1 → 2 entry; module reads and records, does not advise |
| `CR050_GATE_DOGFOOD_ADVISORY` | Phase 2; verdicts visible, non-blocking |
| `CR050_GATE_ENFORCEMENT_CANDIDATE` | Phase 3; verdicts labeled, non-blocking |
| `CR050_GATE_ENFORCEMENT_ACTIVE` | Phase 4; verdicts block qualifying PRs |
| `CR050_GATE_ROLLBACK_REQUIRED` | Anomaly observed; rollback receipt pending |
| `CR050_GATE_ROLLBACK_COMPLETE` | Rollback receipt persisted; state downgraded |

These states are vocabulary for downstream work. **No code emits them today.**

---

## 10. Explicit Non-Authorizations

This document **does not authorize** any of the following, now or by implication of merge:

- Creation of `app/services/cr050_audit_gate.py` or any sibling shadow / dogfood / enforcement module.
- Implementation of an audit block parser.
- Addition of a CI check, runtime hook, or call site.
- Hooking into `app/agents/governance_gate.py`, `app/agents/orchestrator.py`, `app/main.py`, or `strategies/ppf/constitution.py`.
- Modification of `docs/system_final_constitution.md`.
- Modification of the existing CR-050 parent docs (`cr050_external_artifact_trust_map.md`, `cr050_clean_room_injection_policy.md`).
- Modification of the D1 (`cr050_constitution_amendment_plan.md`) or D3 (`cr050_injection_audit_receipt_spec.md`) documents.
- Activation of any phase, state, or kill switch.
- Commit of the Uprich artifact binary, decompiled source, or any reformat thereof.
- Generation of T3 / T4 replication code.
- Auto-start of Bundle 3.1, D2, D4, D5, Bundle 2 Batch 7, or branch hygiene.
- Interference with PR #107~#110 workstreams.

---

## 11. Seven-Layer Mapping

- **Observation / Interpretation / Decision / Execution / Learning** may only receive CR-050-derived inputs through a future approved phase (≥ 2), subject to D3's `seven_layer_routing_gate`.
- **Evolution** and **Constitution** remain protected from external-artifact concepts. D6 does not relax this rule and references D1's proposed C13 as the anchor.
- D6 defines **activation boundaries** (when the gate may operate) — not **routing decisions** (which D3 governs).

---

## 12. Next Dependency

| Doc / Bundle | Purpose | Status |
|--------------|---------|--------|
| D1 — `cr050_constitution_amendment_plan.md` | Constitutional anchor plan | ✅ merged (`0406d31`, PR #120) |
| D3 — `cr050_injection_audit_receipt_spec.md` | Audit block + receipt schema | ✅ merged (`64c5a4e`, PR #121) |
| **D6 — this document** | Activation phases + kill switch + rollback | **this PR** |
| D2 — `cr050_operator_responsibility_zone_v1.md` | T3/T4 operator-zone formal scope | HOLD (separate per-PR approval) |
| D4 — `cr050_parameter_slots_policy.md` | T1 slot K-V3 mapping | HOLD |
| D5 — `cr050_risk_control_slots_policy.md` | T1/T2 → Decision/Execution restrictions | HOLD |
| Bundle 3.1 — shadow skeleton | First code artifact; `_CR050_AUDIT_ENABLED=False`, call sites = 0 | HOLD (eligible for separate approval after this PR merges) |
| Bundle 3.2 — dogfood | Self-evaluation | HOLD (pending D2 + D4 + D5) |
| Bundle 3.3 — live enforcement | Merge-blocking | BLOCK (pending actual constitutional amendment ratification) |

After this PR merges, **Bundle 3.1 (shadow skeleton) becomes eligible for a separate per-PR operator approval**. It is **not** auto-started by this merge.

---

## 13. Final State Verdict

```text
GO     : D6 docs-only PR (this PR) for operator review
HOLD   : Bundle 3.1 shadow skeleton (eligible for separate approval only after this PR merges)
HOLD   : D2, D4, D5 (separate per-PR approval each)
HOLD   : Bundle 3.2 dogfood (pending D2 + D4 + D5)
HOLD   : Phase 3 readiness evidence doc (future grandchild)
BLOCK  : Bundle 3.3 live enforcement (pending actual constitutional amendment ratification)
BLOCK  : Code wiring of any kind by this PR
BLOCK  : Modification of active constitution by this PR
BLOCK  : Modification of CR-050 parent docs, D1, or D3 by this PR
```

---

## 14. Cross-References

**Parent / sibling CR-050 docs:**

- `docs/operations/evidence/cr050_external_artifact_trust_map.md` — tier definitions (T0–T4)
- `docs/operations/evidence/cr050_clean_room_injection_policy.md` — Extract → Restate → Implement procedure + 5 verdict gates
- `docs/operations/evidence/cr050_constitution_amendment_plan.md` (D1) — proposed C12 / C13 plan
- `docs/operations/evidence/cr050_injection_audit_receipt_spec.md` (D3) — audit block schema + receipt fields + verdict model

**Governance authority (read-only references):**

- `docs/system_final_constitution.md` — active constitution (unmodified by this policy)
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
CR-050 Shadow Gate Activation Policy (D6)
Canonical Core: K-V3 4-Strategy (S1+S2+S3+S4)
Parent CR: CR-050
Document Class: activation policy specification (docs-only)
Active Constitution Modification: NONE
Existing CR-050 Doc Modification: NONE
D1 Modification: NONE
D3 Modification: NONE
Runtime Wiring Authorization: NONE
Parser / CI Check / Gate Module / Call Site Authorization: NONE
Phase Transition Authorization: NONE (each transition needs its own per-PR approval)
Phases Defined: 5 (PHASE_0_DOCS_ONLY through PHASE_4_LIVE_ENFORCEMENT)
Kill Switch States: 5 (default: CR050_SHADOW_DISABLED)
Activation Receipt Fields: 11
Gate States Defined: 8 (CR050_GATE_NOT_INSTALLED through CR050_GATE_ROLLBACK_COMPLETE)
Live Enforcement Rollback: requires operator approval + receipt + constitutional review + separate PR
Namespace Relation: Child of CR-050 (per evidence_namespace_policy.md §3)
Status: DRAFT — awaiting operator sign-off
Prepared by: Implementer
Authority: Operator (운영자)
Date: 2026-05-12
```
