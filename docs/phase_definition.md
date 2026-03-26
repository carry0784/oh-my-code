# P-01: Dev / Staging / Prod Phase Definition

**Card**: P-01
**Type**: Phase Definition
**Date**: 2026-03-25
**Authority**: Under Phase Law (L-05) and Constitution (C-46)

---

## 1. Current Phase

**Phase: `dev`**

The K-V3 system is in development phase. All constitutional, law, seal, and audit frameworks are active and binding even in this phase.

---

## 2. Phase Registry

| Phase | Status | Entry Criteria | Exit Criteria |
|-------|--------|---------------|---------------|
| `dev` | **ACTIVE** | System exists | Staging readiness achieved |
| `staging` | NOT ENTERED | Dev exit criteria met | Production readiness achieved |
| `prod` | NOT ENTERED | Staging exit criteria met | N/A (operational) |

---

## 3. Dev Phase Definition

### 3.1 Characteristics

- Active feature implementation via C-series cards
- Testnet mode enabled by default
- All changes follow card protocol (L-02)
- Constitution, laws, and seals are active
- Full regression required for every card
- Automated audit (A-01) is available and enforced

### 3.2 Dev Exit Criteria

To transition from `dev` to `staging`, all of the following must be verified:

1. **Regression**: Full test suite clean (current: 1631+)
2. **Constitution**: All seal documents finalized
3. **Laws**: All L-series laws enacted (L-01 through L-05)
4. **Audit**: A-01 full constitution audit passes
5. **Boundary**: C-40 execution boundary lock tests pass
6. **Card B**: All 57 sealed tests pass
7. **Documentation**: Architecture and operational docs complete
8. **Configuration**: Staging environment configuration documented
9. **Dependencies**: All dependencies pinned and verified
10. **Review**: Explicit GO from review process

### 3.3 Dev Phase Permissions

| Action | Permitted |
|--------|:---------:|
| Feature cards (C-series) | Yes |
| Law cards (L-series) | Yes |
| Audit cards (A-series) | Yes |
| Phase cards (P-series) | Yes |
| Engine modification | Constitutional card only |
| Testnet trading | Yes |
| Production trading | No |

---

## 4. Staging Phase Definition

### 4.1 Characteristics

- No new feature cards without staging validation
- Integration testing against sandbox exchanges
- Configuration mirrors production intent
- Performance baseline established
- Operational procedures tested
- Emergency override procedures validated

### 4.2 Staging Entry Checklist

- [ ] All dev exit criteria met
- [ ] Staging environment provisioned
- [ ] Database migrations tested
- [ ] Exchange sandbox connectivity verified
- [ ] Monitoring setup complete
- [ ] Alert routing tested end-to-end
- [ ] Operator procedures documented

### 4.3 Staging Exit Criteria

To transition from `staging` to `prod`:

1. **Integration**: All exchange sandbox tests pass
2. **Performance**: Latency and throughput within acceptable bounds
3. **Resilience**: Failure injection tests pass
4. **Operations**: Runbook complete and validated
5. **Emergency**: Emergency override procedures tested
6. **Monitoring**: All dashboards and alerts functional
7. **Audit**: Full audit in staging environment passes
8. **Review**: Explicit GO from review process

### 4.4 Staging Phase Permissions

| Action | Permitted |
|--------|:---------:|
| Feature cards | With staging validation only |
| Bug fix cards | Yes |
| Configuration changes | Yes |
| Engine modification | Constitutional card only |
| Sandbox trading | Yes |
| Production trading | No |

---

## 5. Prod Phase Definition

### 5.1 Characteristics

- Live operation with real resources
- Elevated change review required
- Emergency override protocol active (L-03)
- Monitoring mandatory at all times
- Audit trail mandatory for all actions
- No experimental changes

### 5.2 Prod Entry Checklist

- [ ] All staging exit criteria met
- [ ] Production credentials configured (not committed to code)
- [ ] Testnet mode explicitly disabled in configuration
- [ ] Monitoring and alerting verified in production
- [ ] On-call procedures established
- [ ] Rollback procedures tested
- [ ] Final audit passed

### 5.3 Prod Phase Permissions

| Action | Permitted |
|--------|:---------:|
| Feature cards | Elevated review required |
| Bug fix cards | Yes, with regression |
| Hot fix | Emergency protocol (L-03) only |
| Engine modification | Constitutional card + elevated review |
| Production trading | Yes |
| Configuration changes | Audited and logged |

### 5.4 Prod Operational Rules

1. Every change must be logged
2. Every deployment must be reversible
3. Monitoring must not be disabled
4. Audit trail must not be interrupted
5. Emergency procedures must be accessible at all times
6. No change during active incident unless part of incident response

---

## 6. Phase Transition Protocol

### 6.1 Forward Transition (dev → staging → prod)

```
1. Verify all exit criteria for current phase
2. Create P-series transition card
3. Run full audit (A-series)
4. Confirm clean regression
5. Execute transition
6. Verify entry criteria for new phase
7. Document transition
```

### 6.2 Backward Transition (prod → staging → dev)

Permitted only under:

1. Emergency override (L-03)
2. Critical production failure
3. Must follow emergency protocol
4. Must create post-rollback audit card
5. Must not skip phases (prod → dev without staging is forbidden)

### 6.3 Phase Skip

**Skipping phases is forbidden.** `dev → prod` without `staging` is constitutionally invalid.

---

## 7. Phase Enforcement

Phase enforcement is currently declarative (this document). Automated enforcement mechanisms (runtime phase checks, deployment guards) may be added by future cards under the authority of this phase definition.

---

*Defined by Card P-01. Phase transitions require explicit P-series cards.*
