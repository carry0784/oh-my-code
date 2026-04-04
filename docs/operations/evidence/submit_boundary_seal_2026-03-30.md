# K-Dexter Submit Boundary Seal

> **Status**: SEALED
> **Date**: 2026-03-30
> **Prerequisite**: execution_boundary_seal_2026-03-30.md (SEALED)
> **Sealed By**: K-Dexter Governance Process

---

## 1. Purpose

This document seals the **submit boundary** -- the final control gate between `execution_ready=True` and actual order submission to an exchange. The SubmitLedger ensures that `submit_ready` is a derived property that can only become `True` through a complete, auditable 6-check guard-receipt chain.

**Critical design principle**: SubmitLedger records approval only. It never submits orders. The actual API call is performed by an external caller that reads `submit_ready=True`.

---

## 2. Architecture (4-Tier Seal Chain)

```
[1] GovernanceGate.pre_check()              10-check gate
     |
[2] Agent ActionLedger.propose_and_guard()   4-check gate  → agent RECEIPTED
     |
[3] ExecutionLedger.propose_and_guard()      5-check gate  → execution_ready=True
     |
[4] SubmitLedger.propose_and_guard()         6-check gate  → submit_ready=True  <-- THIS
     |
[X] External Caller (OrderService)           Reads submit_ready, submits order
```

---

## 3. Boundary Prohibitions

### SB-01: SubmitLedger is Append-Only

No `delete()`, `remove()`, or `clear_proposals()` methods exist.

**Enforcement**: `test_submit_ledger.py` AXIS 5

### SB-02: Submit Guard Cannot Be Bypassed

No `force_apply`, `force_guard`, or `bypass_guard` methods exist.

**Enforcement**: `test_submit_ledger.py` AXIS 2

### SB-03: submit_ready Is a Derived Property

```python
@property
def submit_ready(self) -> bool:
    return self.status == "SUBMIT_RECEIPTED"
```

Cannot be set to `True` without passing all 6 guard checks + valid receipt.

**Enforcement**: `test_submit_ledger.py` AXIS 1, AXIS 3

### SB-04: SubmitLedger Has No Exchange Access

`submit_ledger.py` is prohibited from importing `exchanges/` or `order_service`.

**Enforcement**: `test_submit_ledger.py` AXIS 5

### SB-05: Execution Receipt Required Before Submit Guard

The first check (`EXEC_RECEIPTED`) verifies the upstream execution proposal has reached `EXEC_RECEIPTED`. This enforces the full 4-tier chain.

**Enforcement**: `test_submit_ledger.py` AXIS 2, AXIS 6

### SB-06: Receipt Requires SUBMIT_GUARDED + guard_passed

`record_receipt()` raises `SubmitStateTransitionError` if `guard_passed` is `False` or status is not `SUBMIT_GUARDED`.

**Enforcement**: `test_submit_ledger.py` AXIS 3

### SB-07: State Machine Is Sealed

| From | To (allowed) |
|------|-------------|
| SUBMIT_PROPOSED | SUBMIT_GUARDED, SUBMIT_BLOCKED |
| SUBMIT_GUARDED | SUBMIT_RECEIPTED, SUBMIT_FAILED |
| SUBMIT_BLOCKED | (terminal) |
| SUBMIT_RECEIPTED | (terminal) |
| SUBMIT_FAILED | (terminal) |

**Enforcement**: `test_submit_ledger.py` AXIS 4

### SB-08: Exchange Whitelist Check (SSOT Reference)

Guard check 5 (`EXCHANGE_ALLOWED`) verifies the exchange is in `SUPPORTED_EXCHANGES_ALL` from `app.core.config`. Unsupported exchanges are blocked with explicit error message.

**Enforcement**: `test_submit_ledger.py` AXIS 2 (exchange_not_allowed, exchange_none)

---

## 4. Submit Guard Checks (6)

| # | Check | What It Verifies | Failure Action |
|---|-------|-----------------|---------------|
| 1 | EXEC_RECEIPTED | execution_proposal status == EXEC_RECEIPTED | SUBMIT_BLOCKED |
| 2 | GOVERNANCE_FINAL | pre_evidence_id exists | SUBMIT_BLOCKED |
| 3 | COST_FINAL | CostController budget not exhausted | SUBMIT_BLOCKED |
| 4 | LOCKDOWN_FINAL | SecurityState not LOCKDOWN/QUARANTINE | SUBMIT_BLOCKED |
| 5 | EXCHANGE_ALLOWED | exchange in SUPPORTED_EXCHANGES_ALL | SUBMIT_BLOCKED |
| 6 | SIZE_SUBMIT_CHECK | position_size <= max_position_usd | SUBMIT_BLOCKED |

---

## 5. Proposal Lifecycle

```
SUBMIT_PROPOSED --> SUBMIT_GUARDED --> SUBMIT_RECEIPTED  (submit_ready=True)
                \-> SUBMIT_BLOCKED                       (submit_ready=False)
                \-> SUBMIT_GUARDED --> SUBMIT_FAILED     (submit_ready=False)
```

---

## 6. Lineage Chain (4-Tier)

```
GovernanceGate.pre_check()
  -> pre_evidence_id
    -> ActionLedger (AP-*) -> receipt (AR-*)
      -> ExecutionLedger (EP-*) -> receipt (ER-*)
        -> SubmitLedger (SP-*) -> receipt (SR-*)
          -> submit_ready = True
            -> External Caller submits order
```

`get_full_lineage(submit_proposal_id)` returns:
```json
{
  "submit_proposal_id": "SP-...",
  "execution_proposal_id": "EP-...",
  "agent_proposal_id": "AP-...",
  "status": "SUBMIT_RECEIPTED",
  "submit_ready": true,
  "receipt_id": "SR-..."
}
```

---

## 7. Test Guardians

| Test Suite | Count | What It Guards |
|-----------|-------|----------------|
| `test_submit_ledger.py` AXIS 1 | 6 | Submit Board lifecycle |
| `test_submit_ledger.py` AXIS 2 | 10 | Submit Guard 6-check gate |
| `test_submit_ledger.py` AXIS 3 | 4 | Receipt fail-closed |
| `test_submit_ledger.py` AXIS 4 | 6 | State Machine sealed |
| `test_submit_ledger.py` AXIS 5 | 3 | Boundary (imports, append-only) |
| `test_submit_ledger.py` AXIS 6 | 5 | Lineage 3-tier chain |
| **Total** | **34** | **Submit boundary** |

Cumulative 4-tier control test counts:

| Layer | Tests | Seal |
|-------|-------|------|
| GovernanceGate | 29 | test_agent_governance.py |
| Agent ActionLedger | 31 | test_agent_action_ledger.py |
| Execution Ledger | 32 | test_execution_ledger.py |
| Submit Ledger | 34 | test_submit_ledger.py |
| Market Feed + SSOT | 22 | test_market_feed.py |
| 4-State Regression | 14 | test_4state_regression.py |
| Governance Monitor | 11 | test_governance_monitor.py |
| **Total** | **173** | **All boundaries sealed** |

---

## 8. Prohibited Changes

1. Adding delete/remove/clear to SubmitLedger
2. Adding force/bypass to Submit Guard
3. Making submit_ready a mutable attribute
4. Importing exchanges/ or order_service in submit_ledger.py
5. Removing EXEC_RECEIPTED check
6. Removing EXCHANGE_ALLOWED check
7. Removing record_receipt() requirement
8. Allowing state regression
9. Hardcoding exchange names instead of SSOT reference

---

## 9. Four-Tier Seal Chain Complete

```
Skill Loop Seal                    [SEALED - operational baseline]
  -> Agent Boundary Seal           [SEALED - 4-check, AB-01~AB-06]
    -> Execution Boundary Seal     [SEALED - 5-check, EB-01~EB-07]
      -> Submit Boundary Seal      [SEALED - 6-check, SB-01~SB-08]  <-- THIS
```

This completes the full control chain from signal to submit-ready:

> **Signal -> Governance -> Agent Guard -> Agent Receipt -> Execution Guard -> Execution Receipt -> Submit Guard -> Submit Receipt -> submit_ready=True -> External Caller**

Every step is:
- State-machine enforced (fail-closed)
- Receipt-gated (no advancement without receipt)
- Append-only (no mutation)
- Exchange-isolated (no side effects)
- Test-proven (173 control tests)

---

## Seal Declaration

This document certifies that the Submit boundary has been:

1. **Controlled** -- 6-check Submit Guard with no force override
2. **Derived** -- `submit_ready` is a property, never directly assigned
3. **Chained** -- Execution RECEIPTED required before Submit Guard entry
4. **Whitelisted** -- Exchange must be in SUPPORTED_EXCHANGES_ALL
5. **Receipted** -- Every guarded submit has an evidence-linked receipt
6. **Bounded** -- SB-01~SB-08 prohibitions with test enforcement
7. **Tested** -- 34 tests across 6 axes, 173 total control tests

## Prohibition (1-line summary)

> **Submit without guard, direct submit_ready assignment, exchange imports in submit_ledger, receipt-less SUBMIT_RECEIPTED, execution-receipt-skipping submit, and unsupported exchange submit are permanently prohibited.**

---

> Sealed: 2026-03-30
> Prerequisite Seal: execution_boundary_seal_2026-03-30.md
> Next review: Upon first submit boundary-crossing change request
