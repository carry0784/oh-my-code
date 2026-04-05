# CR-046 Phase 5a Preflight Checklist (SOL Paper Rollout)

**Created**: 2026-04-05
**Source session**: AELP v1 / Plan A / Item A5 (B-5)
**Parent plan**: `autonomous_execution_loop_plan.md` → `continuous_progress_plan_v1.md` §4.5
**Status**: PREFLIGHT DOCUMENTATION — Phase 5a execution is **NOT** started in this PR.
**Purpose**: Enumerate every check, observation point, and abort condition that must be verified **before** initiating SOL/USDT paper trading Phase 5a per `cr046_sol_paper_rollout_plan.md`.

---

## 1. Scope boundary

### 1.1 What this document IS

- A pre-execution gate checklist
- Observation metrics definition
- Abort condition specification
- Rollback trigger matrix
- Reference index linking operational artifacts

### 1.2 What this document is NOT

- **NOT** the Phase 5a execution itself
- **NOT** a modification of `cr046_sol_paper_rollout_plan.md`
- **NOT** a flip of any flag, beat, or paper session start toggle
- **NOT** authorization to start live paper trading

> Activation of Phase 5a still requires **A's explicit scope instruction**. This document exists only to shorten the time between A's GO and the actual start by having all checks pre-documented.

---

## 2. Reference context

| Source | Role |
|---|---|
| `cr046_sol_paper_rollout_plan.md` | Phase 5a approved plan (2026-04-01, A) — SMC+WaveTrend 2/2, 1H, paper/dry_run, 2-week min |
| `cr046_btc_latency_guard_checklist.md` | Parallel BTC guarded paper (2nd priority, latency guard mandatory) |
| `cr046_phase5_deployment_readiness.md` | Overall deployment readiness table |
| `cr046_three_tier_judgment.md` | 3-tier operational path (SOL GO / BTC guarded / ETH excluded) |
| `CLAUDE.md` §CR-046 | SOL 1st / BTC 2nd / ETH excluded |

---

## 3. Pre-execution gate checklist (must all be PASS before start)

### 3.1 Environment integrity

| # | Check | Command / Location | Expected | Block if fail |
|:---:|---|---|---|:---:|
| E1 | Database reachable | `alembic current` | Shows current head revision | 🔴 ABORT |
| E2 | Migrations current | `alembic upgrade head` | `Already at head` | 🔴 ABORT |
| E3 | Celery worker healthy | `celery -A workers.celery_app inspect ping` | `pong` from all workers | 🔴 ABORT |
| E4 | Celery beat schedule loaded | `celery -A workers.celery_app inspect scheduled` | Schedule visible | 🔴 ABORT |
| E5 | Redis broker reachable | `redis-cli ping` | `PONG` | 🔴 ABORT |
| E6 | Exchange API reachable (SOL) | manual ping or health endpoint | 200 OK | 🔴 ABORT |
| E7 | No `.env` secret leak | `git status` | `.env` not staged | 🔴 ABORT |

### 3.2 Strategy configuration

| # | Check | Value | Source | Block if mismatch |
|:---:|---|---|---|:---:|
| S1 | Asset | `SOL/USDT` | `cr046_sol_paper_rollout_plan.md` §1 | 🔴 ABORT |
| S2 | Composition | `SMC (pure-causal, Version B) + WaveTrend` | §1 | 🔴 ABORT |
| S3 | Consensus | `2/2 agreement required` | §1 | 🔴 ABORT |
| S4 | Timeframe | `1H` | §1 | 🔴 ABORT |
| S5 | Mode | `paper / dry_run only` | §1 | 🔴 ABORT |
| S6 | Stop-loss | `2.0%` | §2 | 🔴 ABORT |
| S7 | Take-profit | `4.0%` | §2 | 🔴 ABORT |
| S8 | Max concurrent | `1` | §2 | 🔴 ABORT |
| S9 | Daily loss limit | `5.0%` | §2 | 🔴 ABORT |
| S10 | Weekly trade cap | `15` | §2 | 🔴 ABORT |

### 3.3 Safety interlocks

| # | Check | Expected state | Block if violated |
|:---:|---|---|:---:|
| I1 | `EXECUTION_ENABLED` flag | `False` (paper does not need real write) | 🔴 ABORT |
| I2 | `shadow_write_service.py` | No live execution code path reachable | 🔴 ABORT |
| I3 | testnet env flag | `BINANCE_TESTNET=true` or equivalent | 🔴 ABORT |
| I4 | Real capital accounts | Disconnected / read-only | 🔴 ABORT |
| I5 | `kill_switch` reachable | Manual abort command tested in dry-run | 🔴 ABORT |
| I6 | Paper session DB table exists | `session_store_cr046` table in DB | 🔴 ABORT |

### 3.4 Observability readiness

| # | Check | Expected | Block if fail |
|:---:|---|---|:---:|
| O1 | Signal generation log sink | Writing to `logs/signals.log` or equivalent | 🟡 DEGRADE |
| O2 | Trade execution log sink | Writing to `logs/trades.log` | 🟡 DEGRADE |
| O3 | PnL calculator live | Produces daily/weekly rollup | 🟡 DEGRADE |
| O4 | Alert webhook / channel | Test alert delivered successfully | 🟡 DEGRADE |
| O5 | Grafana / dashboard panel | Visible and scraping | 🟡 DEGRADE |

### 3.5 Governance check

| # | Check | Expected | Block if fail |
|:---:|---|---|:---:|
| G1 | CR-046 Phase 5a scope approval | A explicit instruction exists | 🔴 ABORT |
| G2 | CR-048 RI-2B-2b Track A | `HOLD` status preserved (no accidental unlock) | 🔴 ABORT |
| G3 | `exception_register.md` | No new unresolved exceptions for SOL | 🔴 ABORT |
| G4 | Baseline version | `v2.5` (5456/5456) or later green | 🔴 ABORT |

---

## 4. Observation metrics during Phase 5a

### 4.1 Per-bar (1H)

| Metric | Source | Sampling |
|---|---|---|
| SMC signal value | `app/services/strategies/smc_pure_causal.py` | every bar close |
| WaveTrend signal value | `app/services/strategies/wavetrend.py` | every bar close |
| Agreement (2/2 yes/no) | consensus engine | every bar close |
| Entry decision | strategy runner | every bar close |
| Position state | position service | every bar close |
| Unrealized PnL | performance metrics | every bar close |
| Realized PnL delta | performance metrics | on exit only |

### 4.2 Daily (per `cr046_sol_paper_rollout_plan.md` §4)

| Check | Action if failed |
|---|---|
| Signal generation active | Investigate signal pipeline |
| Trades executed (paper) | Verify execution engine |
| PnL within daily limit | Auto-pause if exceeded |
| No system errors | Fix before next bar |

### 4.3 Weekly review (per §4)

| Metric | Target | Alert |
|---|---|---|
| Rolling Sharpe | > 0.3 | < 0 for 1 week |
| Win rate | > 40% | < 30% |
| Trade count | 3–8 | < 1 or > 15 |
| Max drawdown | < 15% | > 10% |
| Profit factor | > 1.0 | < 0.8 |

---

## 5. Abort / pause matrix

| Condition | Detection | Action | Severity |
|---|---|---|:---:|
| Daily loss > 5.0% | PnL monitor | Auto-pause session until next day 00:00 UTC | 🔴 |
| Daily loss > 4.0% (warning) | PnL monitor | End-of-day forced close, warning alert | 🟡 |
| Weekly drawdown > 15% | Weekly rollup | **Halt Phase 5a** + A notification | 🔴 |
| Win rate < 30% over 1 week | Weekly review | Downgrade to observation, alert A | 🟡 |
| Rolling Sharpe < 0 for 1 week | Weekly review | Downgrade + alert A | 🟡 |
| > 15 trades/week | Anomaly guard | Halt and investigate | 🔴 |
| 0 trades/week + signals exist | Pipeline check | Investigate execution engine | 🟡 |
| Any unhandled exception in runner | Error log | Pause + A notification | 🔴 |
| Exchange API 5xx sustained > 15 min | Health monitor | Pause until recovery | 🟡 |
| `EXECUTION_ENABLED` unexpectedly `True` | Safety interlock | **EMERGENCY HALT** + A notification | 🔴🔴 |
| Real trade observed (non-paper) | Reconciliation | **EMERGENCY HALT** + forensics | 🔴🔴 |

---

## 6. Manual abort procedure (runbook outline)

> Full runbook to be created as `cr046_phase5a_abort_runbook.md` in a separate PR on activation.

1. **Detect**: alert fires or manual observation
2. **Classify**: pause (🟡) vs halt (🔴) vs emergency halt (🔴🔴)
3. **Acknowledge**: operator confirms within 5 min
4. **Execute halt command**: `<halt_script>` (to be specified at activation)
5. **Verify paper session stopped**: check `session_store_cr046` state
6. **Snapshot current state**: dump positions, PnL, logs
7. **Post-mortem artifact**: `docs/operations/evidence/cr046_phase5a_halt_<timestamp>.md`
8. **A notification**: include artifact link + root cause hypothesis

---

## 7. Activation gate (NOT part of this PR)

When A instructs Phase 5a start, the runbook is:

| Step | Action | Verifier |
|:---:|---|---|
| 1 | Verify §3 (all PASS) | operator |
| 2 | Verify §3.5 G1–G4 (governance) | operator + A |
| 3 | A explicit GO receipt `cr046_phase5a_activation_go_receipt.md` | A |
| 4 | Start paper session (dry-run only) | operator |
| 5 | First 4 hours continuous monitoring | operator |
| 6 | Daily review for 14 days | operator |
| 7 | Phase 5a → 5b promotion review | A |

---

## 8. What this PR does / does not do

### Does ✅
- Document all pre-execution gates (environment / strategy / safety / observability / governance)
- List observation metrics tied to existing rollout plan values
- Specify abort / pause conditions and severity
- Outline the manual abort procedure
- Link all referenced source documents

### Does NOT ❌
- Start Phase 5a
- Modify `cr046_sol_paper_rollout_plan.md`
- Modify any strategy, service, or worker code
- Flip `EXECUTION_ENABLED` or any other flag
- Create the activation receipt
- Create the halt runbook (separate future PR)
- Touch Track A governance chain

---

## 9. References

| 문서 | 역할 |
|---|---|
| `docs/operations/autonomous_execution_loop_plan.md` | Plan A parent |
| `docs/operations/continuous_progress_plan_v1.md` §4.5 | B-5 원본 명세 |
| `docs/operations/evidence/cr046_sol_paper_rollout_plan.md` | Source rollout plan (v1, 2026-04-01 APPROVED) |
| `docs/operations/evidence/cr046_btc_latency_guard_checklist.md` | Parallel BTC latency guard |
| `docs/operations/evidence/cr046_phase5_deployment_readiness.md` | Phase 5 readiness table |
| `docs/operations/evidence/cr046_three_tier_judgment.md` | Three-tier operational path |
| `CLAUDE.md` §CR-046 | Current state summary |

---

## Footer

```
CR-046 Phase 5a Preflight Checklist
Plan ref        : AELP v1 / Plan A / Item A5 (B-5)
Created         : 2026-04-05
Phase 5a status : NOT STARTED (preflight documentation only)
Gate checks     : 26 (Environment 7 + Strategy 10 + Safety 6 + Obs 5 + Governance 4)
  [corrected: E=7, S=10, I=6, O=5, G=4 = 32 — see each §3.x subsection]
Abort matrix    : 11 conditions
Activation step : requires new cr046_phase5a_activation_go_receipt.md
Track A impact  : none
```
