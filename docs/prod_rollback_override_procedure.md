# D-05: Production Rollback & Override Procedure

**Card**: D-05
**Type**: Documentation (no code change)
**Date**: 2026-03-25

---

## 1. Purpose

This document defines the mandatory rollback, emergency brake, and override procedures for production operation. No production system may operate without this procedure being documented, reviewed, and accessible.

---

## 2. Immediate Stop Conditions

The following conditions require **immediate production stop** without waiting for approval:

| # | Condition | Severity |
|---|-----------|:--------:|
| 1 | Governance gate broken or disabled | **CRITICAL** |
| 2 | Persistence layer broken (evidence DB or receipt store) | **CRITICAL** |
| 3 | All health endpoints failing | **CRITICAL** |
| 4 | Configuration mismatch detected (wrong env loaded) | **CRITICAL** |
| 5 | Illegal execution path detected (C-40 test would fail) | **CRITICAL** |
| 6 | Audit failure on sealed contract | **HIGH** |
| 7 | Unplanned testnet flag change | **HIGH** |
| 8 | Unauthorized code deployment detected | **HIGH** |
| 9 | Database connection permanently lost | **HIGH** |
| 10 | Security breach suspected | **CRITICAL** |

**Any operator may invoke immediate stop. No approval required for safety actions.**

---

## 3. Rollback Sequence

When a stop condition is triggered, execute in order:

### Step 1: Stop Application

```bash
# Stop FastAPI server (SIGTERM or Ctrl+C)
# Stop Celery workers
celery -A workers.celery_app control shutdown
```

### Step 2: Preserve Evidence

```bash
# Copy current state before any changes
cp data/prod_evidence.db data/prod_evidence_$(date +%Y%m%d_%H%M%S).db.bak
cp data/prod_receipts.jsonl data/prod_receipts_$(date +%Y%m%d_%H%M%S).jsonl.bak
cp logs/prod.log logs/prod_$(date +%Y%m%d_%H%M%S).log.bak
```

**Never delete evidence files during rollback.**

### Step 3: Revert Config/Environment

```bash
# If config was the issue, revert to last known good config
# If code was the issue, revert to last known good commit
git log --oneline -5  # identify rollback target
# Do NOT force-push or destructively modify without card
```

### Step 4: Verify Safe State

```bash
# Run audit
pytest tests/test_a01_constitution_audit.py -q

# Run boundary lock
pytest tests/test_c40_execution_boundary_lock.py -q

# Run full regression
pytest -q
```

### Step 5: Document Incident

Create an incident receipt containing:
- Timestamp of detection
- Stop condition triggered
- Operator who stopped
- Evidence preserved (file list)
- Config state at time of incident
- Recovery actions taken
- Post-recovery audit results

---

## 4. Emergency Override Law Usage

Reference: L-03 (`law_emergency_override.md`)

### 4.1 When Override Is Allowed

Only when:
- System is unsafe and standard card process cannot address in time
- A condition from Section 2 is active
- Minimum change needed to restore safety

### 4.2 Who May Invoke

- Any authorized operator for Tier 1 (operator lock)
- Any authorized operator for Tier 2 (config override)
- Authorized operator with post-audit commitment for Tier 3 (code override)

### 4.3 Required Evidence

Every override must record:

| Evidence | Required |
|----------|:--------:|
| Timestamp | Yes |
| Operator identity | Yes |
| Emergency condition | Yes |
| Override tier (1/2/3) | Yes |
| Exact changes made | Yes |
| Rollback plan | Yes |
| Post-override audit card number | Yes |

### 4.4 Post-Override Audit

Within 24 hours of any emergency override:

1. Create A-series audit card
2. Run full audit (A-01 + C-40)
3. Run full regression
4. Verify all invariants restored
5. Document whether constitutional gap exists
6. If gap found, create amendment card

---

## 5. Responsibility Matrix

| Action | Operator | Reviewer | Approver |
|--------|:--------:|:--------:|:--------:|
| Detect stop condition | **Primary** | — | — |
| Execute immediate stop | **Primary** | — | — |
| Preserve evidence | **Primary** | — | — |
| Revert environment | **Primary** | Verify | — |
| Verify safe state | **Primary** | **Review** | — |
| Document incident | **Primary** | **Review** | — |
| Invoke emergency override | **Primary** | — | Post-audit |
| Approve restart after incident | — | **Primary** | **Required** |
| Create post-incident card | **Primary** | **Review** | Approve |

---

## 6. Forbidden Actions

1. **Silent rollback**: Every rollback must be documented
2. **Undocumented override**: Every override must produce evidence (Section 4.3)
3. **Config mutation without receipt**: No config change during incident without recording
4. **Production continue under broken governance**: Governance must be restored before restart
5. **Evidence deletion**: Never delete evidence files during or after incident
6. **Skip post-override audit**: 24-hour audit card requirement is mandatory
7. **Blame-driven response**: Focus on system safety, not attribution
8. **Restart without verification**: All pre-start checks (D-03 Section 2.1) must pass before restart

---

## 7. Activation Dependency

Production activation is forbidden without:
- This rollback procedure being documented
- This procedure being reviewed and accessible
- Operator awareness of immediate stop conditions
- Evidence preservation capability verified

---

*Documented by Card D-05.*
