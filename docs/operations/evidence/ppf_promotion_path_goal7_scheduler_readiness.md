# PPF Scheduler Readiness (Goal 7)

```
document_id                = PPF-SCHED-READINESS-001
scope                      = SCHEDULER_REGISTRATION_VERIFICATION
authority_boundary         = READINESS_ASSESSMENT
execution_binding          = NONE
scheduler_registration     = COMPLETE
assessed_at                = 2026-04-13
```

---

## Current Beat Schedule

Source: `workers/celery_app.py` `beat_schedule` dict (15 entries)

| # | Schedule Key | Task | Interval |
|---|-------------|------|---------|
| 1 | sol-paper-trading-hourly | workers.tasks.sol_paper_tasks.run_sol_paper_bar | 3600s |
| 2 | expire-old-signals | workers.tasks.signal_tasks.expire_signals | 300s |
| 3 | record-asset-snapshot-every-5m | workers.tasks.snapshot_tasks.record_asset_snapshot | 300s |
| 4 | ops-daily-check | workers.tasks.check_tasks.run_daily_ops_check | 86400s |
| 5 | ops-hourly-check | workers.tasks.check_tasks.run_hourly_ops_check | 3600s |
| 6 | governance-monitor-daily | workers.tasks.governance_monitor_tasks.run_daily_governance_report | 86400s |
| 7 | governance-monitor-weekly | workers.tasks.governance_monitor_tasks.run_weekly_governance_summary | 604800s |
| 8 | collect-market-state-every-5m | workers.tasks.data_collection_tasks.collect_market_state (BTC/USDT) | 300s |
| 9 | collect-sol-market-state-every-5m | workers.tasks.data_collection_tasks.collect_market_state (SOL/USDT) | 300s |
| 10 | collect-sentiment-hourly | workers.tasks.data_collection_tasks.collect_sentiment_only | 3600s |
| 11 | shadow-observation-5m | workers.tasks.shadow_observation_tasks.run_shadow_observation | 300s |
| 12 | strategy-cycle-crypto-5m | workers.tasks.cycle_runner_tasks.run_strategy_cycle (CRYPTO) | 300s |
| 13 | strategy-cycle-kr-stock-5m | workers.tasks.cycle_runner_tasks.run_strategy_cycle (KR_STOCK) | 300s |
| 14 | strategy-cycle-us-stock-5m | workers.tasks.cycle_runner_tasks.run_strategy_cycle (US_STOCK) | 300s |
| 15 | **ppf-shadow-eval-hourly** | workers.tasks.ppf_shadow_tasks.run_ppf_shadow_eval (SOL/USDT) | 3600s |

**Total entries: 15**
Note: 2 additional entries are present in code comments as DISABLED
(sync-positions-every-minute, check-order-status-every-30s — require private API, re-enable at PAPER mode).

---

## PPF Task Registration

| Item | Status | Evidence |
|------|--------|---------|
| ppf_shadow_tasks.py created | PASS | workers/tasks/ppf_shadow_tasks.py |
| Task registered in include[] | PASS | celery_app.py include list entry: "workers.tasks.ppf_shadow_tasks" |
| Beat schedule entry added | PASS | ppf-shadow-eval-hourly at position #15 (3600s) |
| Task name matches @celery_app.task name= | PASS | name="workers.tasks.ppf_shadow_tasks.run_ppf_shadow_eval" |
| Schedule interval matches PPF 1H candle cadence | PASS | 3600s comment: "matches PPF 1H candle cadence" |
| kwargs symbol configured | PASS | {"symbol": "SOL/USDT", "exchange_name": "binance"} |
| SHADOW_MANIFEST enforced in task | PASS | manifest=SHADOW_MANIFEST hardcoded in _run_ppf_shadow_eval_async |
| Redis lock configured | PASS | _LOCK_KEY="ppf_shadow_eval_running", TTL=420s |
| Lock prevents overlap | PASS | returns status="skipped", error="ALREADY_RUNNING" if lock exists |
| Fail-closed on error | PASS | all exceptions caught, task_result["status"]="failed", no side effects |
| max_retries=0 | PASS | @celery_app.task(max_retries=0) — no retry on failure |
| expires=3000 configured | PASS | task expires after 3000s if not started (< 3600s schedule) |
| acks_late=True | PASS | task ack deferred until completion |

---

## Beat Schedule Count

| State | Count | Notes |
|-------|-------|-------|
| Before PPF addition | 14 | Entries 1–14 above |
| After PPF addition | 15 | +1 ppf-shadow-eval-hourly |
| Disabled entries (not counted) | 2 | sync-positions, check-order-status (private API) |

---

## Schedule Conflict Analysis

| Comparison | Interval | Conflict | Notes |
|-----------|----------|----------|-------|
| ppf-shadow-eval-hourly vs sol-paper-trading-hourly | Both 3600s | None | Independent tasks, different scopes |
| ppf-shadow-eval-hourly vs ops-hourly-check | Both 3600s | None | Independent tasks; ops-check is read-only |
| ppf-shadow-eval-hourly vs collect-sentiment-hourly | Both 3600s | None | Independent tasks |
| ppf-shadow-eval-hourly vs shadow-observation-5m | 3600s vs 300s | None | Different cadence, different scope |
| ppf-shadow-eval-hourly vs strategy-cycle-* | 3600s vs 300s | None | PPF is post-cycle gate, not cycle itself |

Redis lock (TTL=420s) prevents intra-task overlap without affecting other tasks.

---

## Task Behavior Summary

```
On each hourly tick (ppf-shadow-eval-hourly):
  1. Acquire Redis lock (fail-safe: skip if already running)
  2. Fetch 100 OHLCV bars via ExchangeFactory.create_fresh (public API)
  3. Build PPFGateHandler with SHADOW_MANIFEST
  4. Run check_gate(risk_filter_pass=False)
  5. If novelty detected (deny_reason_code=NOVELTY_BRAKE):
     - Persist PPFNoveltyEvent row (best-effort)
  6. Advance observation windows for existing events (best-effort)
  7. Release Redis lock
  8. Return task_result dict (status/gate_allowed/novelty_detected/...)

Write scope: PPFNoveltyEvent table only.
State mutation: observation_window_closed, bars_elapsed updates only.
Order execution: NONE (shadow mode, enforce_deny=False).
```

---

## Readiness Summary

```
scheduler_registration     = COMPLETE
task_definition            = COMPLETE
redis_lock                 = CONFIGURED
fail_closed                = VERIFIED
shadow_mode_enforced       = VERIFIED (SHADOW_MANIFEST hardcoded)
first_execution            = PENDING (awaiting next hourly beat)
```
