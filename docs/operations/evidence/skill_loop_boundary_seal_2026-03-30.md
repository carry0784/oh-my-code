# K-Dexter Skill Loop -- Operation Boundary Seal

> **Status**: SEALED
> **Date**: 2026-03-30
> **Sealed By**: K-Dexter Governance Process
> **Prerequisite**: skill_loop_seal_receipt_2026-03-30.md (SEALED)

---

## 1. Purpose

This document seals the **operational boundary** between the K-Dexter Skill Loop system and the Trading Execution system. The boundary defines what the Skill Loop is allowed to do, what it is prohibited from doing, and how it interfaces with the live trading infrastructure.

---

## 2. Architecture Boundary

```
+----------------------------------------------+
|           SKILL LOOP DOMAIN                  |
|                                              |
|  Fix Loop    Learning Loop    Evolution Loop |
|  (reactive)   (memory)        (proactive)   |
|                                              |
|  evaluate_results.py                         |
|  autofix_loop.py                             |
|  evolution_loop.py                           |
|  governance_check.py                         |
|  validate_system.py                          |
|  run_tests.py                                |
|  inject_failure.py                           |
+----------------------------------------------+
         |  READ-ONLY  |  PROPOSAL-ONLY  |
         v             v                 v
+----------------------------------------------+
|         TRADING EXECUTION DOMAIN             |
|                                              |
|  OrderService     ExchangeFactory            |
|  PositionService  AgentOrchestrator          |
|  SignalValidator   RiskManager               |
|  Celery Workers   Market Feed                |
+----------------------------------------------+
```

### Crossing Rules

| Direction | Allowed | Method |
|-----------|---------|--------|
| Skill Loop -> Trading | READ test/validation results | File read only (data/*.json) |
| Skill Loop -> Trading | PROPOSE changes | Evolution proposal (human approval required) |
| Skill Loop -> Trading | NEVER execute orders | **PROHIBITED** |
| Skill Loop -> Trading | NEVER modify exchange config | **PROHIBITED** |
| Trading -> Skill Loop | Trigger evaluation | `evaluate_results.py` via CLI or scheduler |
| Trading -> Skill Loop | Report failures | `test_results.json`, `validation_results.json` |

---

## 3. Sealed Prohibitions

### P-01: Skill Loop Cannot Execute Orders

The Skill Loop (Fix Loop, Learning Loop, Evolution Loop) is **permanently prohibited** from:
- Calling `OrderService.create_order()` or any order submission method
- Calling `ExchangeFactory.create()` to obtain exchange clients
- Importing or referencing `exchanges/` module for execution purposes
- Sending signals to `SignalValidatorAgent` or `AgentOrchestrator`

**Enforcement**: `governance_check.py` GC-04 (live execution path detection)

### P-02: Evolution Loop is Proposal-Only

The Evolution Loop (`evolution_loop.py`) can only:
- ANALYZE failure patterns and grade history
- DIAGNOSE root causes
- PROPOSE improvements (written to `evolution_history.json`)

It **cannot**:
- Auto-apply any proposal
- Modify source code files
- Execute approved proposals without human intervention
- Bypass the PROPOSED -> APPROVED -> (human applies) workflow

**Enforcement**: Max 1 proposal per run, `validate_proposal()` governance check, no file write capability

### P-03: GovernanceGate.pre_check() Bypass Forbidden

Every agent execution MUST pass through `GovernanceGate.pre_check()` before LLM invocation. Bypass is prohibited via:
- GC-01: GovernanceGate singleton enforcement
- GC-02: pre_check() call verification
- 10-check validation (FORBIDDEN, MANDATORY, COMPLIANCE, PATTERN, BUDGET)
- Regression tests: `test_agent_governance.py` AXIS 2 (8 bypass tests)

**Enforcement**: `GovernanceGate` singleton pattern, `test_agent_governance.py` guards

### P-04: CostController Required for All LLM Calls

No agent may invoke LLM without `CostController` budget verification:
- `BUDGET_CHECK` must be `passed` (not `deferred` or `failed`)
- Budget exceeded -> agent execution blocked
- Token usage tracked per call via `last_usage` extraction

**Enforcement**: `GovernanceGate` BUDGET_CHECK, `test_agent_governance.py` AXIS 5 (4 tests)

### P-05: FailurePatternMemory is Learning-Only

`FailurePatternMemory` stores failure patterns, recurrence data, and fix strategies for **learning and diagnosis purposes only**. It has:
- NO execution authority
- NO ability to trigger fixes
- NO ability to modify production code
- READ access to failure data, WRITE access only to pattern storage (`failure_patterns.json`)

The AutoFix Loop reads pattern data for decision-making, but `FailurePatternMemory` itself never initiates actions.

**Enforcement**: `PATTERN_CHECK` in GovernanceGate, pattern escalation rules (WARN at 3+, BAN at 5+)

### P-06: AutoFix Scope Restrictions

The AutoFix Loop (`autofix_loop.py`) is constrained by:
- Maximum 3 iterations per loop run
- Maximum 3 files modified per fix attempt
- BLOCK state -> immediate exit (exit code 2), no fix attempted
- F-GOVERNANCE type -> always DENY (no autofix allowed)
- Protected files require governance approval before modification

**Enforcement**: `AUTOFIX_POLICY` table, `_get_autofix_decision()`, loop iteration counter

---

## 4. Interface Contracts

### 4.1 Data Flow (Skill Loop reads these)

| File | Producer | Consumer | Format |
|------|----------|----------|--------|
| `data/test_results.json` | `run_tests.py` / pytest | `evaluate_results.py` | {status, passed, failed, errors, failures[]} |
| `data/validation_results.json` | `validate_system.py` | `evaluate_results.py` | {overall, passed, failed, checks[]} |
| `data/governance_check_result.json` | `governance_check.py` | `evaluate_results.py` | {judgment, violations[], warnings[]} |
| `data/failure_patterns.json` | `autofix_loop.py` | `evaluate_results.py`, `evolution_loop.py` | [{test_id, type, recurrence, count, ...}] |

### 4.2 Data Flow (Skill Loop writes these)

| File | Producer | Consumer | Purpose |
|------|----------|----------|---------|
| `data/evaluation_report.json` | `evaluate_results.py` | Dashboard, G-MON | Grade + risk score |
| `data/grade_history.json` | `evaluate_results.py` | Dashboard, Evolution Loop | Time-series grades |
| `data/autofix_loop_report.json` | `autofix_loop.py` | Dashboard | Fix attempt results |
| `data/evolution_history.json` | `evolution_loop.py` | Dashboard, CLI | Proposals + approvals |

### 4.3 Dashboard Integration (READ-ONLY from Skill Loop data)

| Endpoint | Source Files | Card |
|----------|-------------|------|
| `GET /dashboard/api/evaluation-status` | evaluation_report.json, grade_history.json, autofix_loop_report.json, failure_patterns.json, evolution_history.json | self_healing_card + evolution_card |

---

## 5. Governance Check Coverage

| Rule | Protection | Boundary Relevance |
|------|-----------|-------------------|
| GC-01 | GovernanceGate singleton | P-03: bypass prevention |
| GC-02 | pre_check mandatory | P-03: bypass prevention |
| GC-03 | Protected file modification | P-06: autofix scope |
| GC-04 | Live execution path detection | P-01: order execution ban |
| GC-05 | Forbidden content patterns | P-01, P-02: injection prevention |
| GC-06 | Constitution consistency | Structural integrity |
| GC-07 | Risk score manipulation ban | Seal integrity |
| GC-08 | Grade history integrity | Seal integrity |

---

## 6. Test Guardians

| Test Suite | Count | What It Guards |
|-----------|-------|----------------|
| `test_agent_governance.py` AXIS 1 | 2 | Contract preservation |
| `test_agent_governance.py` AXIS 2 | 8 | Bypass prevention (P-03) |
| `test_agent_governance.py` AXIS 3 | 3 | Record consistency |
| `test_agent_governance.py` AXIS 4 | 5 | Singleton safety (P-03) |
| `test_agent_governance.py` AXIS 5 | 4 | Budget control (P-04) |
| `test_agent_governance.py` AXIS 6 | 7 | Pattern memory (P-05) |
| `test_4state_regression.py` | 14 | 4-state grading + policy (P-06) |
| `test_governance_monitor.py` | 11 | G-MON reporting |
| **Total** | **54** | **All boundaries** |

---

## 7. Prohibited Changes (Boundary-Specific)

1. Adding import of `exchanges/` or `OrderService` to any Skill Loop script
2. Adding `auto_apply=True` or equivalent to Evolution Loop
3. Removing `GovernanceGate.pre_check()` from any agent execution path
4. Removing `CostController` dependency from `GovernanceGate`
5. Granting `FailurePatternMemory` write access to non-pattern files
6. Removing iteration/file limits from AutoFix Loop
7. Adding direct database write capability to Skill Loop scripts
8. Bypassing human approval for Evolution proposals

---

## 8. Revalidation Triggers

Any of the following changes require boundary revalidation:

- Modification to `GovernanceGate` constructor or `pre_check()`
- Modification to `autofix_loop.py` policy table or loop constraints
- Modification to `evolution_loop.py` proposal workflow
- Addition of new imports to Skill Loop scripts
- Modification to `governance_check.py` GC-04 (live path detection)
- Any change that crosses the Skill Loop / Trading boundary

**Revalidation method**:
1. `pytest tests/test_agent_governance.py tests/test_4state_regression.py -v` (all PASS)
2. `python scripts/inject_failure.py --mode scenario-all` (4/4 ALL PASS)
3. Manual review of changed imports and call paths

---

## 9. Operational Controls (Post-Seal Additions)

### 9.1 Apply Guard

Every `evolution_loop.py apply` execution is gated by 4 automatic checks:

| Guard | Check | Failure Action |
|-------|-------|---------------|
| RECEIPT | Change approval receipt exists referencing proposal_id | apply blocked |
| TESTS | evaluation_report.json grade is GREEN or YELLOW | apply blocked |
| GOVERNANCE | governance_check_result.json judgment is not BLOCK | apply blocked |
| COMMIT | --commit hash provided | apply blocked |

- `--force` override: allowed but records `apply_forced: true` in history
- Every forced apply requires Section 7 (Force Override Record) in the receipt

### 9.2 Proposal Cooldown

| Parameter | Value |
|-----------|-------|
| `PROPOSAL_COOLDOWN_HOURS` | 24 |
| Scope | Per category (same category cannot be re-proposed within window) |
| Future | Category-specific cooldowns when operational data accumulates |

### 9.3 Evolution Board State Transitions

```
PROPOSED --> APPROVED --> APPLIED
         \-> REJECTED
         \-> BLOCKED
```

| Command | Transition | Constraint |
|---------|-----------|------------|
| `approve <id>` | PROPOSED -> APPROVED | Operator only |
| `reject <id>` | PROPOSED/APPROVED -> REJECTED | Operator only |
| `apply <id>` | APPROVED -> APPLIED | Apply Guard must pass |
| `block <id>` | PROPOSED/APPROVED -> BLOCKED | Reason required |

### 9.4 CLI Operations

| Command | Purpose |
|---------|---------|
| `run` | Execute one evolution cycle |
| `list` | Show all proposals |
| `board` | Show proposals grouped by status |
| `approve <id>` | Approve a proposal |
| `reject <id>` | Reject a proposal |
| `apply <id> --commit <hash>` | Apply with guard checks |
| `block <id> --reason "..."` | Block a proposal |

---

## Seal Declaration

This document certifies that the operational boundary between the K-Dexter Skill Loop and the Trading Execution system has been:

1. **Defined** -- 6 prohibitions (P-01 through P-06) with enforcement mechanisms
2. **Guarded** -- 54 tests across 8 test suites protect all boundaries
3. **Enforced** -- GC-01 through GC-08 governance rules machine-enforce boundaries
4. **Documented** -- Interface contracts, data flows, and crossing rules specified
5. **Controlled** -- Apply Guard, Proposal Cooldown, and Board state transitions operational

**Any modification that crosses the sealed boundary requires governance approval, human review, and full revalidation.**

## Prohibition (1-line summary)

> **Skill Loop order execution, Evolution auto-apply, GovernanceGate bypass, CostController-less LLM calls, FailurePatternMemory execution authority, AutoFix unbounded operation, and guardless apply are permanently prohibited.**

---

> Sealed: 2026-03-30T08:30:00Z
> Updated: 2026-03-30T09:00:00Z (Section 9 added: operational controls)
> Prerequisite Seal: skill_loop_seal_receipt_2026-03-30.md
> Next review: Upon first boundary-crossing change request
