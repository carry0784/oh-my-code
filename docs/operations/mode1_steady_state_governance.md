# CR-024: Mode 1 Steady-State Governance Pack

Date: 2026-05-14
Status: **ACTIVE**
Author: B (Implementer)
CR-ID: CR-024
Category: L1 (operational governance, no code change)
Supersedes: Warm-Start Activation Gate (CR-020) experimental status

---

## 1. Purpose

Upgrade Mode 1 Sustained Operation from experimental activation to
formal steady-state operational status. This pack fixes the baseline,
defines the operational cadence, and establishes the governance
framework for ongoing Mode 1 operation.

**Mode 1 is no longer experimental. It is the production-grade
observation-only operational mode for K-Dexter.**

---

## 2. Steady-State Declaration

| Parameter | Value | Authority |
|-----------|-------|-----------|
| Operational mode | Mode 1 (observation-only) | CR-020, CR-021 |
| Exchange target | Binance Testnet | CR-020 §8.1 |
| BINANCE_TESTNET | true (mandatory) | post_pilot_change_control.md L3 |
| Workers | Celery worker + beat | CR-021 verification |
| Sustained run | 7-day PASS (CR-023) | mode1_sustained_review_2026-05-14.md |
| Status | **STEADY-STATE** | This document |

### Upgrade Basis

| Evidence | Result | Date |
|----------|--------|------|
| Mode 1 Activation (CR-021) | VERIFIED | 2026-05-08 |
| 7-Day Sustained Run (CR-023) | 7/7 PASS | 2026-05-14 |
| Safety invariants | 7/7 intact x 7 days | 2026-05-08~14 |
| Test baseline | 832/0/0 stable | 2026-05-14 |
| Incidents | 0 | 2026-05-08~14 |

---

## 3. Steady-State Baseline

### 3.1 Board State (Normal under Mode 1)

| Field | Steady-State Value | Notes |
|-------|-------------------|-------|
| seal_chain_complete | True | Cold-start seal |
| pressure | LOW | No proposals = no pressure |
| posture | MONITOR | Default |
| risk | LOW | No active positions |
| orphan_count | 0 | No proposals to orphan |
| cleanup_candidates | 0 | No proposals to clean |
| blocked_count | 0 | No proposals to block |
| retry_pending | 0 | No proposals to retry |
| latency.has_measurements | False | No proposals flowing |
| trend.trend_available | False | No snapshots accumulating |

**Cold-start is the normal operational state under Mode 1.**
The observation layer reads pipeline ledgers (ActionLedger, ExecutionLedger,
SubmitLedger). Mode 1 activates exchange reads but does not generate
pipeline proposals. Cold-start resolves automatically when Mode 2
activates signal/order flow. No code change is needed or permitted.

### 3.2 Safety Invariants (Constant)

| Layer | Invariant | Required Value |
|-------|-----------|---------------|
| Observation | read_only | True |
| Observation | simulation_only | True |
| Observation | no_action_executed | True |
| Observation | no_prediction | True |
| Decision | action_allowed | False |
| Decision | suggestion_only | True |
| Decision | read_only | True |

**7/7 invariants must hold at every check. Any violation triggers
immediate Mode 1 suspension and incident response.**

### 3.3 Test Baseline

| Suite | Count | Required |
|-------|-------|----------|
| Observation tests | 520 | 0 failures |
| Governance tests | 312 | 0 failures |
| **Total** | **832** | **0 failures, 0 warnings** |

Execution rule (RA-001): Two separate pytest invocations mandatory.

### 3.4 Worker Status

| Component | Expected State |
|-----------|---------------|
| Celery worker | UP (responds to ping) |
| Celery beat | UP (8 tasks scheduled) |
| Beat tasks | sync_positions, check_orders, expire_signals |
| Exchange connection | Binance Testnet |

---

## 4. Operational Cadence Matrix

### 4.1 Daily (Light Check)

| # | Check | Method | Pass Criteria |
|---|-------|--------|---------------|
| 1 | Worker alive | `celery inspect ping` | pong response |
| 2 | Board read | `build_four_tier_board()` | Cold-start or consistent |
| 3 | Safety invariants | Board safety fields | 7/7 intact |

**Effort**: ~5 minutes
**Operator**: B (or designated operator)
**Log**: Append to sustained_operation_log.md (batch format for normal days)

### 4.2 Weekly (Governance Check)

| # | Check | Method | Pass Criteria |
|---|-------|--------|---------------|
| 1 | Daily checks (all 7) | Log review | 7/7 days OK |
| 2 | Test baseline | 2x pytest invocation | 832/0/0 |
| 3 | Red line spot check | 10-point grep | 10/10 intact |
| 4 | FP-001 status | Red line 1 grep | Stable (known) |
| 5 | Worker uptime | 7-day log | No restarts needed |

**Effort**: ~30 minutes
**Operator**: B (or designated operator)
**Log**: Weekly section in sustained_operation_log.md

### 4.3 Bi-Weekly (Drift + Calibration Review)

| # | Check | Method | Pass Criteria |
|---|-------|--------|---------------|
| 1 | Category drift review | Registry CR analysis | No downward drift |
| 2 | Classification calibration | 5-sample independent test | >= 4/5 (80%) match |
| 3 | Boundary rule review | post_pilot_change_control.md | Rules current |
| 4 | Outstanding debt | Debt register | Decreasing or stable |

**Effort**: ~1 hour
**Operator**: A + B
**Log**: Separate bi-weekly review document

### 4.4 Monthly (Full Audit)

| # | Check | Method | Pass Criteria |
|---|-------|--------|---------------|
| 1 | All weekly checks | Cumulative | All PASS |
| 2 | Intake registry review | g3_change_intake_registry.md | Complete, no gaps |
| 3 | Change level distribution | L1/L2/L3 tally | Healthy ratios |
| 4 | Constitution review | verify_constitution.py | PASS |
| 5 | Incident count | Event log | 0 or resolved |
| 6 | Baseline stability | 832/0/0 trend | No regression |

**Effort**: ~2 hours
**Operator**: A + B
**Log**: Monthly audit document in evidence/

---

## 5. Calibration Debt Resolution

### 5.1 Outstanding Debt

| Item | Source | Status | Resolution |
|------|--------|--------|------------|
| ~~Classification consistency 3/5 (60%)~~ | CR-022 → CR-025 | **RESOLVED** | 4/5 PASS (2026-05-14), upgraded to 8/8 PASS |

### 5.2 Resolution Plan

At the next bi-weekly drift review, conduct a 5-sample classification
calibration:

1. B prepares 5 new hypothetical change descriptions
2. A and B independently classify each (L1/L2/L3 + Category A/B/C/D)
3. Compare results
4. Target: >= 4/5 (80%) match

**If 4/5+ match**: Upgrade CR-022 criterion #8 from CONDITIONAL PASS
to unconditional PASS. Update phase_h_pilot_closure_2026-05-08.md
scorecard to "8/8 PASS".

**If < 4/5 match**: Extend calibration. Identify systematic mismatch
patterns. Add boundary rules. Schedule another 5-sample re-run.

### 5.3 Boundary Rules (Current)

From CR-022 calibration (2026-05-08):

| Rule | Classification |
|------|---------------|
| Changes touching validation surface (grep patterns, governance checks, red line tools) | Default to Category C |
| Any board field addition/removal | Default to L3 |
| Documentation-only changes | L1 / Category A |
| Test additions (no relaxation) | L1 / Category A or B |

---

## 6. Prohibitions (Steady-State)

### 6.1 Mode 1 Prohibitions (Carried from CR-020)

- Execution path changes: **FORBIDDEN**
- Decision safety changes: **FORBIDDEN**
- Write path expansion: **FORBIDDEN**
- Prediction language: **FORBIDDEN**
- BINANCE_TESTNET=false: **FORBIDDEN** (requires production gate)
- Mode 2 activation: **FORBIDDEN** (requires separate CR + review)
- Cold-start "fix" code changes: **FORBIDDEN** (cold-start is normal)

### 6.2 Gate Status

| Gate | Status | Prerequisite |
|------|--------|-------------|
| Mode 2 (full pipeline) | **ON HOLD** | Steady-state stable + calibration resolved + separate CR |
| Production exchange | **ON HOLD** | Mode 2 verified + separate CR + A approval |

**Neither gate may be opened until steady-state governance is
established AND calibration debt is resolved.**

---

## 7. Escalation Procedures

### 7.1 Safety Invariant Violation

1. **Immediate**: Stop workers (`celery control shutdown`)
2. **Log**: Record invariant violation details
3. **Assess**: Determine if transient or persistent
4. **Report**: Notify A within 1 hour
5. **Resolve**: Fix root cause before restarting workers
6. **Verify**: Full 832/0/0 regression + safety check

### 7.2 Test Baseline Regression

1. **Immediate**: Revert last change (if L2 change caused it)
2. **Log**: Record failing tests
3. **Investigate**: Root cause analysis
4. **Fix**: Restore 832/0/0
5. **Post-mortem**: Document in incident log

### 7.3 Worker Failure

1. **Assess**: Check if planned or unplanned
2. **Restart**: `celery -A workers.celery_app worker --loglevel=info`
3. **Verify**: Safety invariants after restart
4. **Log**: Duration of downtime

---

## 8. Integration with Existing Documents

| Document | Relationship |
|----------|-------------|
| post_pilot_change_control.md | L1/L2/L3 levels govern all changes |
| g3_change_intake_registry.md | All changes registered (CR-024+) |
| g2_governance_sustainment_loop.md | Cadence definitions (refined here) |
| sustained_operation_log.md | Ongoing daily/weekly log |
| warm_start_activation_gate.md | Mode 1 activation authority |
| phase_h_pilot_closure_2026-05-08.md | Pilot baseline reference |

---

## 9. Document Control

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-05-14 | Initial steady-state governance pack |
