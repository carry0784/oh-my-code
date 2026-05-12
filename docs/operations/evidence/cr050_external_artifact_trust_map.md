# CR-048: External Artifact Trust Map

Date: 2026-05-12
Canonical Core: **K-V3 4-Strategy (S1+S2+S3+S4)**
Authority: Operator (운영자)
Status: DRAFT — awaiting operator sign-off

---

## 1. Purpose and Scope

CR-048 governs the adoption of strategy concepts from **Uprich Future Bot v1.5.4** (a battle-tested commercial Binance Futures trading bot) into K-V3. The artifact under review is a **decompiled / obfuscated .NET 6 WPF assembly**, not the original source. Before any K-V3 module references, restates, or implements any element of this artifact, that element must be classified into a **trust tier (T0–T4)** defined in this document.

This document is the **upstream dependency** for every later CR-048 work item. No interpreter, no parameter slot, no risk gate, no paper rollout proceeds without per-element tier classification recorded here or in a successor map.

**In scope:** classification rules, per-tier verdicts, boundary enforcement, operator responsibility carve-outs.

**Out of scope:** the clean-room extraction procedure itself (see `cr048_clean_room_injection_policy.md`), constitutional amendments (see `cr048_constitution_amendment_v1.md`), strategy parameter content (see `cr048_strategy_parameter_slots_v1.md`).

---

## 2. Trust Tier Definitions (T0–T4)

| Tier | Name | Description | Trust |
|------|------|-------------|-------|
| **T0** | K-V3 Native | Code, schemas, and docs authored inside the K-V3 repository | **FULL** |
| **T1** | Structure-Trusted | UI field names, setting identifiers, parameter slot shapes from the artifact — structure observable but behavior unverified | **STRUCTURE ONLY** |
| **T2** | Protected Stub Suspicion | Method bodies that decompile but are obfuscated, control-flow flattened, or known to be runtime-patched | **SUSPECT** |
| **T3** | Runtime / Protection Core | `DynamicMethod`, `Marshal.Copy`, JIT hook installation, IL patching, anti-debug, anti-tamper, integrity verification | **BOUNDARY (no-cross)** |
| **T4** | License / Security Boundary | Trial expiry, subscription validation, machine-binding, `ServerCustomer` reporting, IP/balance transmission, kill-switch keys | **BOUNDARY (operator zone)** |

Trust decreases monotonically from T0 → T4. A single source element receives **the highest applicable tier** (most restrictive wins).

---

## 3. Per-Tier Verdict Matrix (Rev 3 Policy)

| Tier | Concept Extraction | Code Copy | Analysis | Verdict |
|------|---------------------|-----------|----------|---------|
| **T0** | N/A | N/A | N/A | **PASS** |
| **T1** | Allowed (restated in K-V3 vocabulary) | Forbidden | Allowed | **PASS** |
| **T2** | Allowed only as concept hypothesis; behavior re-derived from scratch | Forbidden | Allowed | **CONDITIONAL PASS** |
| **T3** | Prohibited | Prohibited | Boundary only (no operational hooks into K-V3) | **SEALED (no-cross)** |
| **T4** | Prohibited | Prohibited | Operator-zone only (results never auto-flow into K-V3 code) | **SEALED (operator zone)** |

**Reading rule.** Anything not classified is treated as **T3** until proven otherwise (deny-by-default).

---

## 4. Tier-by-Tier Examples from the Uprich Artifact

| Element (representative) | Tier | Rationale |
|--------------------------|------|-----------|
| `LongUsdt`, `ShortLeverage`, `TakeProfit`, `StopLoss` UI/property slot names | **T1** | Pure structural identifiers; behavior is re-implemented in K-V3 |
| `FundingFilterEnabled`, `DepthGapFilterEnabled`, `TrailingEntryEnabled` flags | **T1** | Boolean slot shapes; semantic restated as K-V3 gate concepts |
| `MeanRevertEnabled`, `BreakoutEnabled`, `UprichAgrtEnabled` strategy slots | **T1** | Slot names map to K-V3 S2/S3/S4 — concept only |
| `LongStandard1m/15m/1h/4h` timeframe-threshold pairs | **T1** | Parameter slot shape, value semantics re-derived |
| Decompiled method bodies in `*ViewModel.cs` with linear logic | **T1 / T2** | T1 if trivially declarative; T2 if logic appears flattened or stripped |
| `tDo6wFPt5M1rBm3hKC.*` obfuscated namespace methods | **T2** | Names mangled, bodies decompile but semantics not verifiable |
| `<Module>{...}` cctor with switch-flattened control flow | **T2** | Obfuscator output, behavior cannot be trusted |
| `Marshal.Copy(...)` writes into JIT-generated code addresses | **T3** | Runtime protection core — boundary, not for K-V3 use |
| `DynamicMethod` construction targeting native function pointers | **T3** | Same — runtime patching infrastructure |
| Anti-debug checks (`Debugger.IsAttached` patterns, integrity hashes) | **T3** | Protection runtime; never injected into K-V3 |
| `TrialKeyCheck()`, expiry timer, `MachineId` binding | **T4** | License boundary — operator zone analysis only |
| `ServerCustomer.Validate()`, IP / balance transmission payloads | **T4** | Reporting/telemetry boundary — operator decides retention |
| `Hardcodet.Wpf.TaskbarNotification` system-tray license popups | **T4** | License UX surface — operator zone |

This list is **non-exhaustive**. Any element not appearing here must be tier-tagged before injection (default T3 per the deny-by-default rule).

---

## 5. Boundary Enforcement Rules

**T3 — Runtime / Protection Core (SEALED no-cross)**

- No K-V3 module imports, references, links, or replicates T3 elements.
- No K-V3 test fixture is constructed from T3 outputs.
- No prompt to any AI assistant requests generation of T3-equivalent code.
- T3 analysis (if performed by operator) stays in the operator workspace; results enter K-V3 only as natural-language risk notes.

**T4 — License / Security Boundary (SEALED operator zone)**

- No K-V3 module replicates trial bypass, license-skip, expiry override, or transmission-suppression logic.
- IP / balance / `MachineId` transmission concepts: K-V3 may have its own telemetry, but it must be **authored independently** in K-V3 vocabulary, with explicit operator opt-in.
- Operator-zone analysis (per §6) does not flow into K-V3 evidence unless explicitly restated as policy.

**Common (T3 + T4)**

- The artifact binary, decompiled source, and obfuscated namespaces are never committed into the K-V3 repository.
- Cross-references in K-V3 docs use **English descriptors of behavior**, never artifact identifiers (e.g., write "trailing-entry cooldown concept" not "the body of `TrailingEntryTimeout`").

---

## 6. Operator Responsibility Zone (Rev 3 §9.2 Carve-Out)

Per the Rev 3 plan, the following analysis activities are reclassified from "prohibited" to **operator responsibility** — meaning the operator may perform them in their own environment, but K-V3 automation does not assist and the results do not auto-flow into K-V3 code:

| Activity | K-V3 AI Assistance | Operator Action |
|----------|--------------------|-----------------|
| License / Trial logic analysis (T4) | **Not provided** | Allowed in operator environment; legal-compliance is operator responsibility |
| `DynamicMethod` / `Marshal` runtime analysis (T3 boundary cases) | **Not provided** | Allowed in operator environment; AI helps only with conceptual restatement to Python idioms |
| Boundary verification (confirming an element is T3/T4, not deeper) | **Read-only triage assistance** | Operator decides final tier |

This carve-out **does not unlock** code-copy, TPM-circumvention code generation, or license-bypass code generation — those remain forbidden under all tiers and all conditions (see `cr048_clean_room_injection_policy.md` §3).

---

## 7. Cross-References

**Companion documents (CR-048 set):**

- `cr048_clean_room_injection_policy.md` — extraction procedure consuming this tier map
- `cr048_constitution_amendment_v1.md` (forthcoming) — C7' / C12 / C13 grounding
- `cr048_operator_responsibility_zone_v1.md` (forthcoming) — fuller carve-out scope
- `cr048_phase_f_parallel_validation_design.md` (forthcoming) — downstream paper validation
- `cr048_risk_control_slots_v1.md` (forthcoming) — T1 slots consumed
- `cr048_strategy_parameter_slots_v1.md` (forthcoming) — T1 slots consumed
- `cr048_telegram_notification_policy_v1.md` (forthcoming) — T4 boundary-aware telemetry

**Pattern source:**

- `cr046_three_tier_judgment.md` — evidence document conventions
- `docs/system_final_constitution.md` — supreme governance authority
- `strategies/ppf/constitution.py` — C1–C11 invariant pattern that this trust map complements

---

## Signature

```
CR-048 External Artifact Trust Map
Canonical Core: K-V3 4-Strategy (S1+S2+S3+S4)
Tiers Defined: T0 (Native), T1 (Structure-Trusted), T2 (Stub Suspicion), T3 (Runtime Core), T4 (License Boundary)
Boundary Tiers: T3 (SEALED no-cross), T4 (SEALED operator zone)
Default Tier (Unclassified): T3 (deny-by-default)
Policy: Rev 3 (Concept Extraction for T1/T2; Boundary for T3/T4)
Operator Zone: T3/T4 analysis allowed in operator environment only
Status: DRAFT — awaiting operator sign-off
Prepared by: Implementer
Authority: Operator (운영자)
Date: 2026-05-12
```
