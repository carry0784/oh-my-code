# K-Dexter Order Executor Design Document

> **Status**: ACTIVE
> **Date**: 2026-03-30
> **Type**: Execution Layer Design (NOT a seal document)
> **Prerequisite**: 4-Tier Seal Chain COMPLETE

---

## 1. Purpose

The OrderExecutor sits **outside the 4-tier seal chain**. It is the only module that performs actual side-effects (exchange API calls). The seal chain handles approval; the OrderExecutor handles execution.

```
[Seal Chain - Approval]                    [Execution Layer]
GovernanceGate → ActionLedger              OrderExecutor
  → ExecutionLedger → SubmitLedger    →      → Exchange API
                   submit_ready=True         → OrderResult (OX-*)
```

---

## 2. Safety Mechanisms

| # | Mechanism | Description |
|---|-----------|------------|
| OE-01 | submit_ready check | submit_ready=False → ExecutionDeniedError |
| OE-02 | Idempotency | Same submit_proposal_id → cached result, no duplicate order |
| OE-03 | dry_run default True | Real execution requires explicit dry_run=False |
| OE-04 | Exchange allowlist | Exchange must be in SUPPORTED_EXCHANGES_ALL |
| OE-05 | Timeout | Exchange call wrapped in asyncio.wait_for() |
| OE-06 | Ledger write ban | Never writes to SubmitLedger, ExecutionLedger, or ActionLedger |
| OE-07 | History append-only | No delete, no mutation of past results |

---

## 3. OrderResult Status Values

| Status | Meaning |
|--------|---------|
| FILLED | Order fully executed |
| PARTIAL | Order partially filled |
| REJECTED | Exchange rejected the order |
| TIMEOUT | Exchange API call timed out |
| ERROR | Unexpected error (network, validation, etc.) |

---

## 4. Lineage (4-tier)

```
AP-* (Agent)  →  EP-* (Execution)  →  SP-* (Submit)  →  OX-* (Order)
```

Every OrderResult contains all three upstream IDs for full audit trail.

---

## 5. Test Guardians

| Axis | Tests | What It Guards |
|------|-------|----------------|
| AXIS 1: Execute Flow | 6 | dry_run, recording, lineage |
| AXIS 2: Safety Checks | 5 | submit_ready, allowlist, idempotency |
| AXIS 3: Error Handling | 4 | timeout, exceptions, error recording |
| AXIS 4: Boundary | 4 | no ledger write, append-only |
| AXIS 5: Audit Trail | 4 | history, lookup, lineage trace |
| **Total** | **23** | |

---

## 6. Relationship to 4-Tier Seal Chain

| Seal Chain (Approval) | OrderExecutor (Execution) |
|----------------------|--------------------------|
| State machine enforced | No state machine (not needed) |
| Guard checks (4→5→6) | Safety checks (submit_ready, allowlist) |
| Receipt required | OrderResult recorded |
| Append-only ledger | Append-only history |
| No exchange access | Exchange access (sole handler) |
| fail-closed transitions | fail-closed submit_ready check |

**Key principle**: The seal chain decides. The executor acts. They never mix.

---

> Document created: 2026-03-30
> This is NOT a seal document. OrderExecutor has safety mechanisms, not boundary prohibitions.
