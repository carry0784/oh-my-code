# K-Dexter Execution Boundary Seal

> **Status**: SEALED
> **Date**: 2026-03-30
> **Prerequisite**: agent_boundary_seal_2026-03-30.md (SEALED)
> **Sealed By**: K-Dexter Governance Process

---

## 1. Purpose

This document seals the **execution boundary** -- the final control gate between agent approval and actual order submission. The ExecutionLedger ensures that `execution_ready` is a derived property that can only become `True` through a complete, auditable guard-receipt chain.

---

## 2. Architecture

```
GovernanceGate.pre_check()              [10-check gate]
    |
    v
Agent ActionLedger.propose_and_guard()  [4-check gate]
    |
    v
Agent ActionLedger.record_receipt()     [agent RECEIPTED]
    |
    v
ExecutionLedger.propose_and_guard()     [5-check gate] <-- THIS BOUNDARY
    |  AGENT_RECEIPTED
    |  GOVERNANCE_CLEAR
    |  COST_WITHIN_BUDGET
    |  LOCKDOWN_CHECK
    |  SIZE_FINAL_CHECK
    |
    v  (blocked? -> return failure, execution_ready=False)
    |
ExecutionLedger.record_receipt()        [EXEC_RECEIPTED, execution_ready=True]
    |
    v
(future) OrderService                   [NOT connected -- EB-04 prohibits]
```

---

## 3. Boundary Prohibitions

### EB-01: ExecutionLedger is Append-Only

The ExecutionLedger stores proposals and receipts in an **append-only** buffer. No deletion, no mutation of past proposals is permitted.

- No `delete()`, `remove()`, or `clear_proposals()` methods exist
- Buffer flush writes to `data/execution_action_history.json` (append, not overwrite)
- Maximum 500 entries retained in flush file

**Enforcement**: `test_execution_ledger.py` AXIS 5 (append-only test)

### EB-02: Execution Guard Cannot Be Bypassed

Every execution commitment must pass through `ExecutionLedger.propose_and_guard()` with all 5 checks passing. There is no `--force` equivalent.

- No `force_apply`, `force_guard`, or `bypass_guard` methods exist
- If any guard check fails, `execution_ready` remains `False`
- A blocked execution proposal is terminal -- cannot be retried

**Enforcement**: `test_execution_ledger.py` AXIS 2 (8 guard tests)

### EB-03: execution_ready Is a Derived Property

`execution_ready` is **never directly assigned**. It is a `@property` that returns `True` only when `status == "EXEC_RECEIPTED"`.

```python
@property
def execution_ready(self) -> bool:
    return self.status == "EXEC_RECEIPTED"
```

This means:
- Cannot be set to `True` without passing all 5 guard checks
- Cannot be set to `True` without a valid receipt
- Cannot be set to `True` if any state machine violation occurs

**Enforcement**: `test_execution_ledger.py` AXIS 1 (lifecycle tests), AXIS 3 (receipt tests)

### EB-04: ExecutionLedger Has No Exchange Access

The `execution_ledger.py` module is prohibited from importing:
- `exchanges/` (any exchange module)
- `app.services.order_service` (or any order execution service)
- Any module capable of submitting orders or connecting to exchanges

**Enforcement**: `test_execution_ledger.py` AXIS 5 (import boundary tests)

### EB-05: Agent Receipt Required Before Execution Guard

The first of 5 guard checks (`AGENT_RECEIPTED`) verifies that the upstream agent proposal has reached `RECEIPTED` status. This enforces the full chain:

```
GovernanceGate -> Agent Guard -> Agent Receipt -> Execution Guard -> Execution Receipt
```

No step can be skipped.

**Enforcement**: `test_execution_ledger.py` AXIS 2 (agent_not_receipted_blocks), AXIS 6 (lineage tests)

### EB-06: Receipt Requires EXEC_GUARDED + guard_passed

Receipt is fail-closed. `record_receipt()` raises `ExecStateTransitionError` if:
- `guard_passed` is `False`
- Status is not `EXEC_GUARDED` (e.g., `EXEC_PROPOSED` or `EXEC_BLOCKED`)

**Enforcement**: `test_execution_ledger.py` AXIS 3 (receipt fail-closed tests)

### EB-07: State Machine Is Sealed

The state machine has 5 states with explicitly defined transitions. All undefined transitions raise `ExecStateTransitionError`.

| From | To (allowed) |
|------|-------------|
| EXEC_PROPOSED | EXEC_GUARDED, EXEC_BLOCKED |
| EXEC_GUARDED | EXEC_RECEIPTED, EXEC_FAILED |
| EXEC_BLOCKED | (terminal) |
| EXEC_RECEIPTED | (terminal) |
| EXEC_FAILED | (terminal) |

**Enforcement**: `test_execution_ledger.py` AXIS 4 (6 state machine tests)

---

## 4. Execution Guard Checks (5)

| # | Check | What It Verifies | Failure Action |
|---|-------|-----------------|---------------|
| 1 | AGENT_RECEIPTED | Agent proposal status == RECEIPTED | EXEC_BLOCKED |
| 2 | GOVERNANCE_CLEAR | pre_evidence_id exists (pre_check passed) | EXEC_BLOCKED |
| 3 | COST_WITHIN_BUDGET | CostController budget not exhausted | EXEC_BLOCKED |
| 4 | LOCKDOWN_CHECK | SecurityState not LOCKDOWN/QUARANTINE | EXEC_BLOCKED |
| 5 | SIZE_FINAL_CHECK | position_size <= max_position_usd | EXEC_BLOCKED |

---

## 5. Proposal Lifecycle

```
EXEC_PROPOSED --> EXEC_GUARDED --> EXEC_RECEIPTED  (success, execution_ready=True)
              \-> EXEC_BLOCKED                     (guard failure, execution_ready=False)
              \-> EXEC_GUARDED --> EXEC_FAILED     (exception, execution_ready=False)
```

---

## 6. Lineage Chain

Full audit trail from signal to execution readiness:

```
GovernanceGate.pre_check()
  -> pre_evidence_id
    -> ActionLedger.propose_and_guard()
      -> agent_proposal_id (AP-*)
        -> ActionLedger.record_receipt()
          -> receipt_id (AR-*)
            -> ExecutionLedger.propose_and_guard()
              -> execution_proposal_id (EP-*)
                -> ExecutionLedger.record_receipt()
                  -> execution_receipt_id (ER-*)
                    -> execution_ready = True
```

`get_full_lineage(execution_proposal_id)` traces this chain.

**Enforcement**: `test_execution_ledger.py` AXIS 6 (lineage tests)

---

## 7. Test Guardians

| Test Suite | Count | What It Guards |
|-----------|-------|----------------|
| `test_execution_ledger.py` AXIS 1 | 6 | Execution Board lifecycle |
| `test_execution_ledger.py` AXIS 2 | 8 | Execution Guard 5-check gate |
| `test_execution_ledger.py` AXIS 3 | 4 | Receipt fail-closed |
| `test_execution_ledger.py` AXIS 4 | 6 | State Machine sealed |
| `test_execution_ledger.py` AXIS 5 | 3 | Boundary (imports, append-only) |
| `test_execution_ledger.py` AXIS 6 | 5 | Lineage + duplicate suppression |
| **Total** | **32** | **Execution boundary** |

Cumulative control test counts:

| Layer | Tests | Seal |
|-------|-------|------|
| GovernanceGate | 29 | test_agent_governance.py |
| Agent ActionLedger | 31 | test_agent_action_ledger.py |
| Execution Ledger | 32 | test_execution_ledger.py |
| 4-State Regression | 14 | test_4state_regression.py |
| Governance Monitor | 11 | test_governance_monitor.py |
| **Total** | **117** | **All boundaries sealed** |

---

## 8. Prohibited Changes

1. Adding `delete`, `remove`, or `clear` methods to ExecutionLedger
2. Adding force/bypass to the Execution Guard
3. Making `execution_ready` a mutable attribute instead of derived property
4. Importing `exchanges/` or `order_service` in `execution_ledger.py`
5. Removing `AGENT_RECEIPTED` check (breaks lineage chain)
6. Removing `record_receipt()` requirement for EXEC_RECEIPTED
7. Weakening any of the 5 guard checks
8. Allowing state regression in the state machine

---

## 9. Relationship to Agent Boundary Seal

| Agent Control | Execution Adaptation | Key Difference |
|--------------|---------------------|----------------|
| ActionLedger (4 checks) | ExecutionLedger (5 checks) | +AGENT_RECEIPTED, +LOCKDOWN |
| ActionProposal states | ExecutionProposal states (EXEC_ prefix) | Same pattern, different namespace |
| guard_passed (assigned) | execution_ready (derived @property) | Stronger guarantee |
| Receipt -> RECEIPTED | Receipt -> EXEC_RECEIPTED | Same fail-closed |
| AB-01~AB-06 | EB-01~EB-07 | +EB-03 (derived), +EB-05 (chain), +EB-07 (sealed) |

---

## Seal Declaration

This document certifies that the Execution boundary has been:

1. **Controlled** -- 5-check Execution Guard with no force override
2. **Derived** -- `execution_ready` is a property, never directly assigned
3. **Chained** -- Agent RECEIPTED required before Execution Guard entry
4. **Receipted** -- Every guarded execution has an evidence-linked receipt
5. **Bounded** -- EB-01~EB-07 prohibitions with test enforcement
6. **Tested** -- 32 tests across 6 axes, 117 total control tests

**Any modification to sealed components requires governance approval and full revalidation.**

## Prohibition (1-line summary)

> **Execution without guard, direct execution_ready assignment, exchange imports in execution_ledger, receipt-less EXEC_RECEIPTED, and agent-receipt-skipping execution are permanently prohibited.**

---

> Sealed: 2026-03-30
> Prerequisite Seal: agent_boundary_seal_2026-03-30.md
> Successor Seal: submit_boundary_seal_2026-03-30.md
> Next review: Upon first execution boundary-crossing change request
