# CR-020: Warm-Start Activation Gate Pack

Effective: 2026-05-08
Status: **ACTIVE — Mode 1 Sustained Operation (observation-only)**
Author: B (Implementer)
CR-ID: CR-020
Category: L1 (documentation, no code change)

---

## 1. Purpose

Document the conditions, prerequisites, and verification steps for
transitioning the sealed observation system from cold-start to warm-start.

**This document does NOT activate warm-start.** It defines the gate
criteria that must be met before A authorizes activation.

---

## 2. Current State (Cold-Start)

| Component | Status | Impact on Board |
|-----------|--------|----------------|
| PostgreSQL | Available | Database ready |
| Redis | Available | Broker/cache ready |
| Celery worker | Not running | No background task execution |
| Celery beat | Not running | No snapshot buffer, no trend data |
| Exchange API | Keys not configured | No position sync, no market data |
| Proposal flow | No proposals | All observation fields at zero/default |

### Board Fields in Cold-Start

| Field | Cold-Start Value | Warm-Start Expected |
|-------|-----------------|---------------------|
| seal_chain_complete | True | True (unchanged) |
| pressure | LOW | Varies by proposal volume |
| posture | MONITOR | Varies by pressure |
| risk | LOW | Varies by conditions |
| latency_measured | False | True (when proposals exist) |
| trend_available | False | True (~2h after beat starts) |
| orphan_total | 0 | Reflects actual orphan state |
| stale_total | 0 | Reflects actual staleness |

---

## 3. Warm-Start Prerequisites

### 3.1 Infrastructure Prerequisites

| # | Prerequisite | Verification | Status |
|---|-------------|-------------|--------|
| P1 | PostgreSQL running | `docker-compose ps` shows postgres healthy | To verify |
| P2 | Database migrated | `alembic upgrade head` succeeds | To verify |
| P3 | Redis running | `docker-compose ps` shows redis healthy | To verify |
| P4 | Celery worker running | `celery inspect ping` responds | To verify |
| P5 | Celery beat running | Beat log shows schedule active | To verify |

### 3.2 Exchange Prerequisites

| # | Prerequisite | Verification | Status |
|---|-------------|-------------|--------|
| E1 | BINANCE_TESTNET=true | Check .env | **Required for first activation** |
| E2 | Binance API key configured | BINANCE_API_KEY non-empty | To verify |
| E3 | Binance API secret configured | BINANCE_API_SECRET non-empty | To verify |
| E4 | Exchange connectivity | `ExchangeFactory.create("binance")` succeeds | To verify |

**CRITICAL: First activation MUST use testnet mode (BINANCE_TESTNET=true).**
Production mode (BINANCE_TESTNET=false) requires separate authorization.

### 3.3 Governance Prerequisites

| # | Prerequisite | Verification | Status |
|---|-------------|-------------|--------|
| G1 | Baseline 832/0/0 confirmed | Run both test suites | To verify |
| G2 | 10/10 red lines intact | Weekly spot check | To verify |
| G3 | L1/L2/L3 change control active | post_pilot_change_control.md in effect | DONE |
| G4 | Intake registry current | CR-020 registered | DONE |
| G5 | Safety invariants at expected values | Board read confirms | To verify |

---

## 4. Activation Sequence

When A authorizes warm-start, execute in this order:

### Phase 1: Infrastructure (5 min)

```bash
# Step 1: Start infrastructure
docker-compose up -d

# Step 2: Verify services
docker-compose ps
# Expected: postgres, redis, flower all running

# Step 3: Run migrations
alembic upgrade head
```

### Phase 2: Pre-Activation Baseline (5 min)

```bash
# Step 4: Run full test baseline (split execution per RA-001)
python -m pytest tests/test_four_tier_board.py tests/test_observation_summary.py \
  tests/test_decision_card.py tests/test_observation_summary_schema.py \
  tests/test_decision_schema_typing.py tests/test_stale_contract.py \
  tests/test_threshold_calibration.py tests/test_4state_regression.py \
  tests/test_cleanup_simulation.py tests/test_cleanup_policy.py \
  tests/test_orphan_detection.py tests/test_order_executor.py \
  tests/test_submit_ledger.py tests/test_execution_ledger.py \
  tests/test_agent_action_ledger.py tests/test_operator_decision.py \
  --tb=no -q

python -m pytest tests/test_agent_governance.py tests/test_ops_checks.py \
  tests/test_market_feed.py tests/test_dashboard.py --tb=no -q

# Expected: 832 passed, 0 failed
```

### Phase 3: Board Cold-Start Snapshot (2 min)

```python
# Step 5: Capture cold-start board state for comparison
from app.services.four_tier_board_service import build_four_tier_board
b = build_four_tier_board()
d = b.model_dump()
# Record all 24 fields as pre-activation baseline
```

### Phase 4: Start Workers (2 min)

```bash
# Step 6: Start Celery worker
celery -A workers.celery_app worker --loglevel=info &

# Step 7: Start Celery beat
celery -A workers.celery_app beat --loglevel=info &

# Step 8: Verify beat schedule active
# Check logs for: "beat: Starting..."
```

### Phase 5: Warm-Start Observation (rolling)

```
T+0:     Workers start. sync_all_positions runs first cycle.
T+1m:    Second position sync. Check for proposal creation.
T+5m:    Board read #1. Check latency_measured changes.
T+30m:   Board read #2. Check stale/orphan detection.
T+2h:    Board read #3. Check trend_available transition.
```

### Phase 6: Post-Activation Baseline (after T+2h)

```bash
# Step 9: Run full test baseline again
# Expected: 832 passed, 0 failed (observation is read-only)

# Step 10: Board read — compare all 24 fields to cold-start snapshot
# Record which fields changed and new values
```

---

## 5. Expected Warm-Start Transitions

| Field | Cold-Start | Expected After Warm-Start | When |
|-------|-----------|--------------------------|------|
| latency_measured | False | True (tiers with proposals) | T+5m |
| trend_available | False | True | T+2h |
| stale_total | 0 | >= 0 (depends on proposal age) | T+5m |
| orphan_total | 0 | >= 0 (depends on pipeline state) | T+5m |
| pressure | LOW | Varies | T+5m |
| posture | MONITOR | Varies | T+5m |

### Fields That MUST NOT Change

| Field | Required Value | Violation Response |
|-------|---------------|-------------------|
| read_only | True | **IMMEDIATE SHUTDOWN** |
| simulation_only | True | **IMMEDIATE SHUTDOWN** |
| no_action_executed | True | **IMMEDIATE SHUTDOWN** |
| no_prediction | True | **IMMEDIATE SHUTDOWN** |
| action_allowed | False | **IMMEDIATE SHUTDOWN** |
| suggestion_only | True | **IMMEDIATE SHUTDOWN** |
| seal_chain_complete | True | Investigate (may be transient) |

---

## 6. Rollback Procedure

If any safety invariant changes unexpectedly during warm-start:

```bash
# Step 1: IMMEDIATE — Stop workers
pkill -f "celery.*worker"
pkill -f "celery.*beat"

# Step 2: Verify workers stopped
celery inspect ping  # Should fail (no workers)

# Step 3: Board read — confirm return to cold-start state
# Safety invariants should be at expected values

# Step 4: Run baseline test
# Expected: 832/0/0

# Step 5: Log incident
# Record: what changed, when, what was running

# Step 6: Do NOT restart until A reviews
```

---

## 7. Activation Modes

A chooses one:

### Mode 1: Observation Only (Recommended First)

- Infrastructure running
- Celery beat running (for snapshots/trends)
- Exchange connectivity (for position reads)
- **No order submission**
- **No signal processing**
- Board shows real observations but system takes no actions

### Mode 2: Full Pipeline (Future, requires separate gate)

- All of Mode 1
- Signal validation active
- Risk management active
- Order submission active
- **Requires separate CR and constitutional review (L3/Category D)**

**Recommendation**: Start with Mode 1. Mode 2 is a separate decision.

---

## 8. Gate Decision

A must provide one of:

| Decision | Effect |
|----------|--------|
| **ACTIVATE (Mode 1)** | Execute activation sequence §4, observation-only mode |
| **HOLD** | Maintain cold-start, continue governance cadence |
| **DEFER** | Postpone decision to a specific date |

### Decision Record

```
Date: 2026-05-08
Decision: ACTIVATE (Mode 1)
Rationale: Code-complete for warm-start confirmed (CR-019).
  30-day pilot PASS, all governance gates clear.
  Cold-start is operational state, not code gap.
  Mode 1 (observation-only) is lowest-risk activation path.
Conditions:
  - BINANCE_TESTNET=true mandatory
  - execution/write/prediction paths remain frozen
  - 7 safety invariants monitored, any violation = immediate rollback
  - observation-only scope (no order submission, no signal processing)
Approved by: A (Designer/Inspector)
```

---

## 8.1 Gate Hold Record (2026-05-08)

```
Status: GATE HOLD → CLEARED
Reason for hold: BINANCE_TESTNET=false in .env (production mode)
Resolution: Switched to BINANCE_TESTNET=true
Verified: grep confirms BINANCE_TESTNET=true
Rule added: "read-only activation with production exchange target
  cannot pass Mode 1 gate — testnet is mandatory for first activation"
Cleared by: A (Designer/Inspector)
```

---

## 9. Prohibitions During Warm-Start

Regardless of activation mode:

| Prohibited | Reason |
|------------|--------|
| action_allowed changes | L3 — constitutional |
| Write path activation | L3 — safety boundary |
| Prediction language | L3 — red line 4 |
| New board fields | L3 — sealed at 24 |
| BINANCE_TESTNET=false | Requires separate production gate |
| Order submission | Requires Mode 2 gate (separate CR) |
| Automated signal processing | Requires Mode 2 gate |

---

## 10. Post-Activation Governance

If activated, the following governance cadence applies:

| Check | Frequency | Additional for Warm-Start |
|-------|-----------|--------------------------|
| Board read | Daily | Compare to previous day (field changes expected) |
| Test baseline | Weekly | 832/0/0 must hold |
| Red line spot check | Weekly | Same 10 checks |
| Safety invariant check | Daily (new) | All 7 invariants at expected values |
| Warm-start transition log | First 7 days | Track field transitions from cold to warm |
