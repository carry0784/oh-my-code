# Governance Layer Final Seal

**Card**: C-45 (Governance Layer Seal)
**Type**: Institutional Seal
**Date**: 2026-03-25
**Baseline at seal**: 1631 passed, 0 failed

---

## 1. Purpose

The governance layer defines and enforces the **constitutional rules, gates, and state machines** that control all system behavior.

- Governance is the supreme authority layer.
- All other layers are subordinate to governance decisions.
- Governance gates must be passed before any significant system action.
- Governance cannot be overridden by operational convenience.

---

## 2. System Scope

### Modules

| Module | Path | Role |
|--------|------|------|
| B1 Constitution | `src/kdexter/governance/b1_constitution.py` | Core constitutional rules |
| B2 Orchestration | `src/kdexter/governance/b2_orchestration.py` | Orchestration governance |
| Doctrine | `src/kdexter/governance/doctrine.py` | Doctrinal rules |
| Gate Evaluator | `src/kdexter/gates/gate_evaluator.py` | Gate evaluation engine |
| Gate Registry | `src/kdexter/gates/gate_registry.py` | Gate registration |
| Gate Criteria | `src/kdexter/gates/criteria.py` | Gate criteria definitions |
| Gate Hooks | `src/kdexter/gates/gate_hooks.py` | Gate lifecycle hooks |
| Governance Gate Agent | `app/agents/governance_gate.py` | LLM-assisted gate evaluation |
| Trust State | `src/kdexter/state_machine/trust_state.py` | Trust level state machine |
| Work State | `src/kdexter/state_machine/work_state.py` | Work mode state machine |
| Security State | `src/kdexter/state_machine/security_state.py` | Security level state machine |

### Explicit Non-Scope

- Order execution (subordinate layer)
- Notification delivery (subordinate layer)
- Retry management (subordinate layer)
- Dashboard rendering (observation layer)

---

## 3. Constitutional Hierarchy

```
Governance (supreme)
  |
  +-- Engine (executes under governance)
  |     |
  |     +-- Execution (trades under engine+governance approval)
  |
  +-- Notification (observes, never overrides)
  |
  +-- Retry (bounded, subordinate to all above)
  |
  +-- Dashboard (read-only observation)
```

No lower layer may override, bypass, or influence governance decisions.

---

## 4. Allowed Responsibilities

1. Define constitutional rules that bind all system behavior
2. Evaluate gates before significant actions
3. Manage trust, work, and security state transitions
4. Enforce doctrinal constraints
5. Provide governance state to observation layers (read-only)
6. Block or approve system actions based on constitutional evaluation

---

## 5. Forbidden Responsibilities

1. Governance must not execute trades directly
2. Governance must not deliver notifications directly
3. Governance must not own retry logic
4. Governance must not be bypassed by any layer
5. Governance decisions must not be silently overridden
6. Governance state must not be mutated by observation layers

---

## 6. Gate Constitution

- Every significant system action must pass through a governance gate.
- Gate evaluation is deterministic and auditable.
- Gate denial is final unless explicitly overridden by a higher governance rule.
- Gate state is exposed to readiness probes and dashboard.
- Gate bypass is constitutionally invalid.

---

## 7. State Machine Constitution

The three state machines form the governance foundation:

| State Machine | Controls | Transitions |
|--------------|----------|-------------|
| Trust State | System trust level | Governed by trust decay engine |
| Work State | Operational mode | Governed by loop monitor and governance |
| Security State | Security posture | Governed by security evaluations |

State transitions are:

- Deterministic
- Auditable
- Governed by engine-layer rules
- Read-only to observation layers
- Never influenced by notification outcomes

---

## 8. Invariants

1. Governance is supreme; no layer overrides it
2. Gates are mandatory; bypass is invalid
3. State machines are owned by engine layer
4. State is consumed read-only by dashboard/notification
5. Governance modules are Card B sealed
6. Constitutional rules are permanent unless amended by constitutional card
7. Governance decisions are fail-closed (deny on error)

---

## 9. Amendment Rule

Governance is the most constitutionally protected layer. Amendment requires:

1. Explicit constitutional card with full justification
2. Card B regression verification
3. Impact analysis on all subordinate layers
4. Sealed contract preservation proof
5. Unanimous GO from review process

No governance change may be made as a side effect of a feature card.

---

*Sealed by Card C-45.*
