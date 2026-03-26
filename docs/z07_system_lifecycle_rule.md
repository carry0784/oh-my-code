# Z-07: System Lifecycle Rule

**Card**: Z-07
**Type**: Operational Rule (no code change, final operational card)
**Date**: 2026-03-25
**Phase**: prod (frozen)

---

## System States

| State | Description |
|-------|-------------|
| `dev` | Active development and testing |
| `staging` | Pre-production validation |
| `prod` | Live production operation |
| `frozen` | Production with change freeze active |
| `live` | Actively operating under governance |
| `maintenance` | Planned operational maintenance window |
| `incident` | Active incident response |
| `rollback` | Reverting to previous known-good state |

### Current State

**`prod` + `frozen` + `live`**

---

## Allowed State Transitions

```
prod → maintenance     (planned window, operator action)
maintenance → prod     (window closed, checks pass)

prod → incident        (failure detected, Z-03 triggered)
incident → rollback    (recovery needed, D-05 invoked)
rollback → prod        (restored, audit passed)

incident → prod        (resolved without rollback, audit passed)
```

### Transition Rules

| Transition | Requires |
|-----------|----------|
| prod → maintenance | Operator declaration, log entry |
| maintenance → prod | All daily checks pass (Z-02 Level 1) |
| prod → incident | Failure detection per Z-03 |
| incident → rollback | D-05 procedure initiated |
| rollback → prod | Z-01 inspection pass, audit pass |
| incident → prod | Root cause resolved, audit pass |

---

## Forbidden State Transitions

| Transition | Reason |
|-----------|--------|
| `prod → dev` | Development is finished. System is sealed. |
| `prod → staging` | Staging phase is complete. No regression. |
| `frozen → dev` | Freeze cannot be reverted to development. |
| `sealed → unsealed` | Archive seal is permanent (X-06). |
| `law → bypassed` | Laws cannot be bypassed (L-01). |
| `seal → removed` | Seals cannot be removed without constitutional amendment. |
| `governance → disabled` | Production requires governance (fail-fast). |

---

## State Diagram

```
                    ┌─────────────┐
                    │    prod     │
                    │  (frozen)   │
                    │   (live)    │
                    └──┬──────┬───┘
                       │      │
              planned  │      │  failure
              window   │      │  detected
                       ▼      ▼
              ┌────────────┐ ┌───────────┐
              │maintenance │ │  incident  │
              └─────┬──────┘ └──┬────┬───┘
                    │           │    │
              checks│    resolve│    │rollback
              pass  │           │    │needed
                    ▼           ▼    ▼
              ┌────────────┐ ┌───────────┐
              │    prod    │ │  rollback  │
              └────────────┘ └─────┬─────┘
                                   │
                              audit│pass
                                   ▼
                             ┌───────────┐
                             │   prod    │
                             └───────────┘
```

All paths return to `prod`. No path leads to `dev` or `staging`.

---

## Lifecycle Invariants

1. **K-V3 is a lifecycle-governed system.** State transitions follow defined rules.
2. **Development is finished.** No return to `dev` state.
3. **Staging is finished.** No return to `staging` state.
4. **Production is permanent.** The system operates in `prod` or temporarily in `maintenance`/`incident`/`rollback`.
5. **Freeze is permanent.** Changes require law + card + audit.
6. **Seal is permanent.** Archive seal (X-06) cannot be reversed.
7. **Every transition produces evidence.** No silent state change.
8. **Every return to prod requires audit.** No unchecked resumption.

---

## Final Statement

K-V3 is a **lifecycle-governed system**.

It was built, staged, deployed, frozen, sealed, inspected, and protocol-defined. It now operates within a closed lifecycle where every transition is governed, every state is verifiable, and every deviation is detectable.

**No further lifecycle states will be added. The system operates within these boundaries permanently.**

---

*Defined by Card Z-07. This is the final operational card of the K-V3 system.*
