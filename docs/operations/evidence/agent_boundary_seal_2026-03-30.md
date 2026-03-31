# K-Dexter Agent Orchestrator -- Boundary Seal

> **Status**: SEALED
> **Date**: 2026-03-30
> **Prerequisite**: skill_loop_boundary_seal_2026-03-30.md (SEALED)
> **Sealed By**: K-Dexter Governance Process

---

## 1. Purpose

This document seals the **operational boundary** for the Agent Orchestrator layer. It defines what agents can do, what they are prohibited from doing, and how their actions are controlled by the transplanted Skill Loop operational model.

---

## 2. Architecture

```
Client Request
    |
    v
AgentOrchestrator.execute()
    |
    v
[1] GovernanceGate.pre_check()       <-- 10-check gate (existing)
    |
    v
[2] SignalValidator / RiskManager     <-- LLM agent execution
    |
    v
[3] ActionLedger.propose_and_guard()  <-- 4-check Apply Guard (NEW)
    |                                     RISK_APPROVED
    |                                     GOVERNANCE_CLEAR
    |                                     SIZE_BOUND
    |                                     COST_BUDGET
    |
    v  (blocked? -> return failure + evidence)
    |
[4] Execution commitment              <-- "Step 3: Would execute order here"
    |
    v
[5] ActionLedger.record_receipt()     <-- Approval receipt (NEW)
    |
    v
[6] GovernanceGate.post_record()      <-- Evidence linkage (existing)
```

---

## 3. Boundary Prohibitions

### AB-01: ActionLedger is Append-Only

The ActionLedger stores proposals and receipts in an **append-only** buffer. No deletion, no mutation of past proposals is permitted.

- No `delete()`, `remove()`, or `clear_proposals()` methods exist
- Buffer flush writes to `data/agent_action_history.json` (append, not overwrite)
- Maximum 500 entries retained in flush file

**Enforcement**: `test_agent_action_ledger.py` AXIS 4 (append-only test)

### AB-02: Apply Guard Cannot Be Bypassed

In the `execute()` flow, every execution commitment must pass through `ActionLedger.propose_and_guard()` with all 4 checks passing.

- No `--force` equivalent in the real-time execution path
- Unlike Skill Loop `--force`, agent Apply Guard has **no override**
- If any guard check fails, execution is blocked with full evidence

**Enforcement**: `test_agent_action_ledger.py` AXIS 2 (5 guard tests)

### AB-03: Every Guarded Proposal Must Have a Receipt

After execution succeeds, `record_receipt()` must be called to create an `ActionReceipt` linking:
- `proposal_id` -> `pre_evidence_id` -> `post_evidence_id`

A GUARDED proposal without a receipt indicates an execution anomaly.

**Enforcement**: `test_agent_action_ledger.py` AXIS 3 (receipt trail tests)

### AB-04: ActionLedger Has No Exchange Access

The `action_ledger.py` module is prohibited from importing:
- `exchanges/` (any exchange module)
- `app.services.order_service` (or any order execution service)
- Any module capable of submitting orders or connecting to exchanges

**Enforcement**: `test_agent_action_ledger.py` AXIS 4 (import boundary tests)

### AB-05: GovernanceGate.pre_check() Remains Mandatory

The existing GovernanceGate 3-phase flow is unchanged. The ActionLedger Apply Guard is **additive** -- it does not replace the GovernanceGate pre_check.

Execution must pass BOTH:
1. GovernanceGate.pre_check() (10 checks)
2. ActionLedger.propose_and_guard() (4 checks)

**Enforcement**: `test_agent_governance.py` AXIS 2 (bypass prevention)

### AB-06: Agents Cannot Auto-Execute Without Guard

No agent (SignalValidator, RiskManager, or future agents) may commit to execution without passing through the ActionLedger Apply Guard. Direct calls to exchange or order APIs from agent code are prohibited.

**Enforcement**: ForbiddenLedger FA-AGENT-001~004, AB-04 import restriction

---

## 4. Apply Guard Checks

| # | Check | What It Verifies | Failure Action |
|---|-------|-----------------|---------------|
| 1 | RISK_APPROVED | risk_result["approved"] == True | BLOCKED |
| 2 | GOVERNANCE_CLEAR | pre_evidence_id exists (pre_check passed) | BLOCKED |
| 3 | SIZE_BOUND | position_size <= max_position_usd | BLOCKED |
| 4 | COST_BUDGET | CostController budget not exhausted | BLOCKED |

---

## 5. Proposal Lifecycle

```
PROPOSED --> GUARDED --> RECEIPTED  (success path)
         \-> BLOCKED              (guard check failure)
         \-> GUARDED --> FAILED   (execution exception after guard)
```

| Status | Meaning | Next Allowed |
|--------|---------|-------------|
| PROPOSED | Created, not yet guarded | GUARDED or BLOCKED |
| GUARDED | All 4 guard checks passed | RECEIPTED or FAILED |
| RECEIPTED | Execution succeeded, receipt recorded | Terminal |
| BLOCKED | Guard check failed | Terminal |
| FAILED | Execution failed after guard | Terminal |

---

## 6. Test Guardians

| Test Suite | Count | What It Guards |
|-----------|-------|----------------|
| `test_agent_action_ledger.py` AXIS 1 | 4 | Proposal board lifecycle |
| `test_agent_action_ledger.py` AXIS 2 | 6 | Apply Guard 4-check gate |
| `test_agent_action_ledger.py` AXIS 3 | 3 | Receipt trail + evidence linking |
| `test_agent_action_ledger.py` AXIS 4 | 3 | Boundary (imports, append-only) |
| `test_agent_governance.py` | 29 | GovernanceGate (unchanged) |
| **Total** | **45** | **Agent layer boundaries** |

---

## 7. Prohibited Changes

1. Adding `delete`, `remove`, or `clear` methods to ActionLedger
2. Adding `--force` bypass to the real-time Apply Guard
3. Importing `exchanges/` or `order_service` in `action_ledger.py`
4. Removing `propose_and_guard()` call from `orchestrator.py` execute flow
5. Removing `record_receipt()` call after successful execution
6. Weakening any of the 4 guard checks
7. Removing GovernanceGate.pre_check() in favor of ActionLedger-only checking

---

## 8. Relationship to Skill Loop Seal

| Skill Loop Control | Agent Adaptation | Key Difference |
|-------------------|-----------------|----------------|
| Evolution Proposal Board | ActionLedger Proposal Board | Milliseconds vs days |
| Evolution Apply Guard (4 checks + force) | Agent Apply Guard (4 checks, NO force) | No force override |
| Change Approval Receipt | ActionReceipt (automatic) | Automatic vs manual template |
| Boundary Seal (P-01~P-06) | Agent Boundary (AB-01~AB-06) | Same philosophy, different scope |
| Proposal Cooldown | N/A (real-time, no cooldown needed) | Different timescale |

---

## Seal Declaration

This document certifies that the Agent Orchestrator layer has been:

1. **Controlled** -- ActionLedger Apply Guard with 4 checks, no force override
2. **Tracked** -- Proposal board with 5-state lifecycle
3. **Receipted** -- Every guarded execution has an evidence-linked receipt
4. **Bounded** -- AB-01~AB-06 prohibitions with test enforcement
5. **Compatible** -- Existing GovernanceGate 3-phase flow preserved

**Any modification to sealed components requires governance approval and full revalidation.**

## Prohibition (1-line summary)

> **Agent guardless execution, Apply Guard bypass, ActionLedger mutation, exchange imports in action_ledger, and receipt-less execution are permanently prohibited.**

---

## 9. Successor Seal

The Execution boundary (ExecutionLedger) extends this seal with additional controls:

- **Document**: `execution_boundary_seal_2026-03-30.md` (SEALED)
- **Guards**: 5-check Execution Guard (adds AGENT_RECEIPTED, LOCKDOWN_CHECK)
- **Key property**: `execution_ready` is derived (@property), never directly assigned
- **Tests**: 32 additional tests across 6 axes
- **Lineage**: Agent proposal_id -> Execution proposal_id (full audit trail)

---

> Sealed: 2026-03-30
> Prerequisite Seal: skill_loop_boundary_seal_2026-03-30.md
> Successor Seal: execution_boundary_seal_2026-03-30.md
> Next review: Upon first agent boundary-crossing change request
