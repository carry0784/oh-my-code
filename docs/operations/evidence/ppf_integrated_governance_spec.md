# PPF Integrated Backtest — Governance Specification
> Issued: 2026-04-13 | Status: SEALED | Version: 1.0

---

## 1. Doctrine Check

### 1.1 자동 (Automation)

Every stage in the PPF integrated backtest pipeline is fully automated. No human action is required to complete individual steps; human gates exist only at promotion decision points.

| Component | Entry Point | Automation Level |
|-----------|-------------|------------------|
| Preflight validation | `OhlcvPreflightValidator.run(session, exchange, symbol, timeframe)` | Fully automated, fail-closed |
| Phase A backtest | `PPFIntegratedBacktester.run(session, symbol, exchange, timeframe)` | Fully automated |
| Baseline freeze | `PPFBaselineManager.freeze_baseline(session, baseline_id, frozen_by, preflight_hash)` | Automated + system-triggered |
| Phase B shadow | `PPFBacktestComparator.compare(session, baseline_id)` called from Celery Beat hourly task `ppf_shadow_tasks.run_ppf_shadow_eval` | Celery Beat, hourly, automated |
| Judgment auto-close | `NoveltyJudgmentEngine.judge_from_replay(ohlcv, novelty_events)` on window completion | Automated on bar close |
| VAL-PDC-002 verdict | `ValPDC002Judge.judge(comparison_report, seal_valid, governance_has_hard_block, novelty_events, bars_collected, baseline_id)` | Automated computation, human reads verdict |

### 1.2 자율 (Autonomous Governance)

The system enforces governance rules without human intervention. Violations cannot be bypassed programmatically.

| Mechanism | Implementation | Scope |
|-----------|----------------|-------|
| State machine ordering | `PPFGovernanceEngine.transition(target, reason)` — raises `ValueError` on invalid transition | All pipeline stages |
| Fail-closed rules FC-01 through FC-10 | `PPFGovernanceEngine.check_*` methods return `PPFBlockLevel.HARD_BLOCK` or `PPFBlockLevel.SOFT_BLOCK` | Per-step gate |
| Baseline seal tamper detection | `PPFBaselineManager.verify_seal()` — SHA-256 of `(deny_rate, novelty_rate, fpr, evaluated_bars, allow_count, deny_count, state_distribution, deny_reason_distribution)` | Post-freeze, pre-Phase B |
| Promotion tier computation | `PPFGovernanceEngine.compute_tier(novelty_events, all_checks_passed)` | GREEN / YELLOW / RED auto-computed |
| Live entry hard prohibition | `PPFGovernanceEngine.check_live_entry()` always returns `(HARD_BLOCK, "LIVE_ENTRY_PROHIBITED")` | Permanent, no override path |
| Live authorization hard prohibition | `ValPDC002Judge.check_live_authorized()` always returns `(False, reason)` | Permanent, no override path |

### 1.3 자가진화 (Self-Evolution)

**STATUS: NOT IMPLEMENTED — by design.**

The governance layer contains no self-modifying logic. The following are explicitly absent:

- No runtime parameter adaptation (C10: PPFParameters is a frozen dataclass)
- No auto-promotion from any verdict tier to a higher execution mode
- No feedback loop that modifies thresholds based on observed results
- No auto-generation of Change Requests

Any evolution of thresholds, tier logic, or tolerance bands requires a new Change Request approved outside this codebase.

---

## 2. Skeleton Mapping (7 Layers)

| Layer | Module(s) | Class(es) | Responsibility |
|-------|-----------|-----------|----------------|
| L1 Data | `app/services/history_data_manager.py` | `HistoryDataManager` | OHLCV bulk ingest, `get_replay_candles()`, `check_coverage()` returning `CoverageReport` |
| L2 Preflight | `app/services/ohlcv_preflight_validator.py` | `OhlcvPreflightValidator` | Symbol/TF lock, coverage threshold, gap count, duplicate detection, hourly alignment; emits `PreflightResult` with `data_hash` |
| L3 Replay | `app/services/ppf_replay_engine.py` | `PPFReplayEngine` | Bar-by-bar PPF gate evaluation; emits `ReplayResult` with `state_distribution`, `deny_reason_distribution`, `novelty_events` list |
| L4 Judgment | `app/services/ppf_novelty_judgment.py` | `NoveltyJudgmentEngine` | Post-hoc TP/FP/UNRESOLVED classification of novelty brake events; emits `JudgmentReport` with `fpr`, `tp_count`, `fp_count`, `unresolved_count` |
| L5 Orchestration | `app/services/ppf_integrated_backtester.py` | `PPFIntegratedBacktester` | Phase A: composes L1 + L3 + L4; aggregates into `PPFBacktestResult`; persists `PPFBacktestBaseline` row |
| L6 Comparison | `app/services/ppf_backtest_comparator.py` | `PPFBacktestComparator` | Phase B: loads baseline + live `PPFNoveltyEvent` rows; computes `ComparisonMetric` list; emits `PPFComparisonReport` |
| L7 Governance | `app/services/ppf_governance_engine.py`, `app/services/ppf_val_pdc_002.py`, `app/services/ppf_baseline_manager.py` | `PPFGovernanceEngine`, `ValPDC002Judge`, `PPFBaselineManager` | State machine enforcement, fail-closed rules FC-01—FC-10, VAL-PDC-002 verdict issuance, baseline freeze/seal lifecycle |

### Layer Dependency Direction

```
L7 Governance
  ├── consumes: PPFBacktestBaseline (DB), PPFComparisonReport (L6 output)
  └── enforces: transition ordering over L2→L3→L4→L5→L6 sequence

L6 Comparison
  ├── reads: PPFBacktestBaseline (DB), PPFNoveltyEvent (DB)
  └── emits: PPFComparisonReport → consumed by L7 (ValPDC002Judge.judge)

L5 Orchestration
  ├── calls: L1.get_replay_candles → L3.replay_segment → L4.judge_from_replay
  └── writes: PPFBacktestBaseline (DB) via _persist_baseline()

L2 Preflight
  ├── calls: L1.check_coverage
  └── emits: PreflightResult.data_hash → stored in PPFBacktestBaseline.preflight_hash at freeze

L1 Data
  └── reads: ohlcv_history table (OhlcvHistory ORM)
```

---

## 3. Slot Decomposition (Rule Categories)

### 3.1 Preflight Rules (L2 — OhlcvPreflightValidator)

| Slot ID | Check Key | Threshold / Condition | Enforcement Point |
|---------|-----------|----------------------|-------------------|
| PRE-01 | `symbol_lock` | `symbol == "SOL/USDT"` | `_check_symbol_lock()` |
| PRE-02 | `timeframe_lock` | `timeframe == "1h"` | `_check_symbol_lock()` |
| PRE-03 | `coverage` (candle count) | `candle_count >= 9600` (400 days × 24 hours) | `_check_coverage()` via `HistoryDataManager.check_coverage()` |
| PRE-04 | `coverage` (coverage_pct) | `coverage_pct >= 95.0%` | `_check_coverage()` |
| PRE-05 | `gap_count` | `gap_count <= 48` (2 days' worth of 1h gaps) | post-coverage, `result.gap_count <= MAX_GAP_COUNT` |
| PRE-06 | `no_duplicates` | `duplicate_open_time_groups == 0` | `_check_duplicates()` SQL: `GROUP BY open_time HAVING COUNT(*) > 1` |
| PRE-07 | `timestamp_alignment` | `open_time % 3_600_000 == 0` for all rows | `_check_timestamp_alignment()` SQL: `WHERE (open_time % 3600000) != 0` |

All 7 checks run unconditionally (no short-circuit). `PreflightResult.passed = all(checks.values())`.

Reproducibility hash: `SHA-256("{first_ts}:{last_ts}:{candle_count}")` stored in `PreflightResult.data_hash`.

### 3.2 Baseline Freeze Rules (L7 — PPFBaselineManager)

| Slot ID | Condition | Effect |
|---------|-----------|--------|
| FREEZE-01 | `baseline.frozen == False` | Required before freeze is permitted |
| FREEZE-02 | `baseline.invalidated == False` | Invalidated baselines cannot be frozen |
| FREEZE-03 | Freeze sets `frozen=True`, `frozen_at=UTC`, `frozen_by`, `seal_hash` | One-way; irreversible |
| FREEZE-04 | `seal_hash = SHA-256(JSON({deny_rate, novelty_rate, fpr, evaluated_bars, allow_count, deny_count, state_distribution, deny_reason_distribution}))` | Tamper detection anchor |
| FREEZE-05 | `phase_b_started` requires `frozen == True` | `start_phase_b()` returns error if not frozen |
| FREEZE-06 | DELETE is PROHIBITED | No delete path exists in `PPFBaselineManager` |

### 3.3 Fail-Closed Rules (L7 — PPFGovernanceEngine)

| Rule | Check Method | Condition Checked | Block Level on Failure |
|------|-------------|-------------------|----------------------|
| FC-01 | `check_phase_a_ready(preflight_passed)` | `preflight_passed == True` | `SOFT_BLOCK` |
| FC-02 | `check_baseline_freeze_ready(unresolved_rate)` | `unresolved_rate <= 0.05` (5%) | `SOFT_BLOCK` |
| FC-03 | `check_phase_b_ready(baseline_frozen)` | `baseline_frozen == True` AND state in `{BASELINE_FROZEN, PHASE_B_COLLECTING, VALIDATION_READY, VAL_PDC_002_ISSUED}` | `SOFT_BLOCK` |
| FC-04 | `check_validation_ready(bars_collected, novelty_events)` | `bars_collected >= 336` | `EVIDENCE_INSUFFICIENT` |
| FC-05 | `check_validation_ready(bars_collected, novelty_events)` | `novelty_events >= 10` | `EVIDENCE_INSUFFICIENT` |
| FC-06 | `check_val_pdc_002_ready(all_metrics_in_tolerance)` | `all_metrics_in_tolerance == True` AND state in `{VALIDATION_READY, VAL_PDC_002_ISSUED}` | `SOFT_BLOCK` |
| FC-07 | `check_live_entry()` | Unconditional prohibition | `HARD_BLOCK` always |
| FC-08 | `check_paper_entry(tier)` | `state == VAL_PDC_002_ISSUED` AND `tier == GREEN` | `HARD_BLOCK` |
| FC-09 | `transition(target)` state machine ordering | Shadow must precede validation (BASELINE_FROZEN → PHASE_B_COLLECTING before VALIDATION_READY) | `ValueError` on invalid transition |
| FC-10 | State tracking in `PPFGovernanceEngine` + `PPFBaselineManager.freeze_baseline()` idempotency | Baseline immutable after freeze (no field updates post-freeze) | `SOFT_BLOCK` ("ALREADY_FROZEN") |

### 3.4 VAL-PDC-002 Criteria (L7 — ValPDC002Judge)

| Criterion | Name | Threshold | Metric Source |
|-----------|------|-----------|---------------|
| C1 | `C1_MIN_BARS` | `bars_collected >= 336` | Phase B bar counter |
| C2 | `C2_DENY_RATE_DELTA` | `|backtest_deny_rate - live_deny_rate| <= 5 pp` (0.05 on [0,1]) | `ComparisonMetric("deny_rate")` or insufficiency note |
| C3 | `C3_FPR_DELTA` | `|backtest_fpr - live_fpr| <= 5 pp` (0.05 on [0,1]) | `ComparisonMetric("fpr")` |
| C4 | `C4_STATE_JS_DIVERGENCE` | JS divergence <= 0.1 | `ComparisonMetric("deny_reason_distribution_js")` |
| C5 | `C5_MIN_NOVELTY_EVENTS` | `novelty_events >= 10` | `PPFNoveltyEvent` count |
| C6 | `C6_SEAL_INTEGRITY` | `seal_valid == True` | `PPFBaselineManager.verify_seal()` |
| C7 | `C7_NO_HARD_BLOCK` | `governance_has_hard_block == False` | `PPFGovernanceEngine.check_live_entry()` |

Verdict mapping:
- **GO**: all 7 criteria pass AND tier == GREEN (novelty_events >= 10)
- **HOLD**: C1–C5 + C7 pass AND tier == YELLOW (5–9 events); OR C1–C5 + C7 pass but C6 fails (seal re-verification needed)
- **BLOCK**: any of C1–C4 fail; OR tier == RED (< 5 events or critical metric failure); OR governance HARD_BLOCK active (C7)

`ValPDC002Report.live_authorized` is **always False**. Hard prohibition, no code path sets it to True.

### 3.5 Promotion Tier Logic (L7 — PPFGovernanceEngine.compute_tier)

| Tier | Novelty Events | `all_checks_passed` | Allowed Actions |
|------|---------------|---------------------|-----------------|
| GREEN | >= 10 | True | Paper entry gate opens (FC-08 CLEAR) |
| YELLOW | 5–9 | True | HOLD verdict only; paper gate blocked |
| RED | < 5 | any | BLOCK verdict; all gates blocked |
| RED | any | False | BLOCK verdict; all gates blocked |

### 3.6 Comparator Tolerance Bands (L6 — PPFBacktestComparator)

| Metric | Comparison Method | Tolerance | Default |
|--------|------------------|-----------|---------|
| `novelty_rate` | Absolute: `|live - backtest| <= tolerance_pct / 100` | ±5 pp | `DEFAULT_TOLERANCE_PCT = 5.0` |
| `fpr` | Absolute: `|live - backtest| <= tolerance_pct / 100` | ±5 pp | `DEFAULT_TOLERANCE_PCT = 5.0` |
| `deny_reason_distribution_js` | Jensen–Shannon divergence <= `js_threshold` | <= 0.1 | `DEFAULT_JS_THRESHOLD = 0.1` |
| `deny_rate` | NOT COMPUTED | n/a — live deny_count not tracked in `PPFNoveltyEvent` | Absence recorded in `insufficiency_reasons` when `baseline.deny_rate > 0.01` |
| `state_distribution_js` | NOT COMPUTED | n/a — live gate-state counter not yet implemented | Absence recorded in `insufficiency_reasons` when baseline field present |

`PPFComparisonReport.val_pdc_002_eligible = True` only when: `all_within_tolerance == True` AND `len(insufficiency_reasons) == 0`.

---

## 4. Forbidden Zones

| ID | Prohibition | Enforcement Mechanism | Severity |
|----|------------|----------------------|----------|
| FZ-01 | Baseline modification after freeze | `PPFBaselineManager.freeze_baseline()` returns `{"success": False, "error": "ALREADY_FROZEN"}` on second call; no UPDATE path for metric fields | HARD |
| FZ-02 | Baseline deletion | No `DELETE` path in `PPFBaselineManager`; `invalidate_baseline()` sets `invalidated=True` and truncates reason to 500 chars, never deletes | HARD |
| FZ-03 | Live entry (any path) | `PPFGovernanceEngine.check_live_entry()` always returns `(HARD_BLOCK, "LIVE_ENTRY_PROHIBITED: PPF live mode not authorized")`; no conditional branch can clear it | HARD |
| FZ-04 | Live authorization via VAL-PDC-002 | `ValPDC002Judge.check_live_authorized()` always returns `(False, "LIVE_NOT_AUTHORIZED: PPF production deployment requires explicit human approval beyond VAL-PDC-002")`; `ValPDC002Report.live_authorized` field is hardcoded False | HARD |
| FZ-05 | Test PASS inferred as production approval | `ValPDC002Report.live_authorized = False` hardcoded; GO verdict does not authorize live; production requires separate human change request | HARD |
| FZ-06 | Invalid state machine transition | `PPFGovernanceEngine.transition(target)` raises `ValueError` on any transition not listed in `ALLOWED_TRANSITIONS`; terminal state `VAL_PDC_002_ISSUED` has empty allowed-targets list | HARD |
| FZ-07 | Paper entry without VAL_PDC_002_ISSUED + GREEN | `check_paper_entry(tier)` returns `HARD_BLOCK` when either `state != VAL_PDC_002_ISSUED` or `tier != GREEN`; both conditions must hold simultaneously | HARD |
| FZ-08 | Phase A start without preflight PASS | FC-01 `check_phase_a_ready(False)` returns `SOFT_BLOCK` blocking state transition `DATA_READY → PHASE_A_RUNNING` | SOFT |
| FZ-09 | Phase B start without frozen baseline | FC-03 `check_phase_b_ready(False)` returns `SOFT_BLOCK`; also enforced structurally by state machine (must be in `BASELINE_FROZEN` state) | SOFT |
| FZ-10 | Freezing baseline with unresolved_rate > 5% | FC-02 `check_baseline_freeze_ready(unresolved_rate)` returns `SOFT_BLOCK` when `unresolved_rate > 0.05` | SOFT |

---

## 5. Execution Checklist

### Gate 0: Pre-Conditions

- [ ] PostgreSQL `ohlcv_history` table populated for `exchange=binance`, `symbol=SOL/USDT`, `timeframe=1h`
- [ ] `PPFGovernanceEngine` instance initialized; `state == NOT_INITIALIZED`
- [ ] `PPFParameters` frozen dataclass constructed (C10 compliance)
- [ ] Database session available (`AsyncSession`)

### Gate 1: DATA_READY — Preflight Validation

- [ ] Call `OhlcvPreflightValidator().run(session, exchange="binance", symbol="SOL/USDT", timeframe="1h")`
- [ ] Assert `PreflightResult.checks["symbol_lock"] == True`
- [ ] Assert `PreflightResult.checks["timeframe_lock"] == True`
- [ ] Assert `PreflightResult.checks["coverage"] == True` (`candle_count >= 9600`, `coverage_pct >= 95.0`)
- [ ] Assert `PreflightResult.checks["gap_count"] == True` (`gap_count <= 48`)
- [ ] Assert `PreflightResult.checks["no_duplicates"] == True` (`duplicate_count == 0`)
- [ ] Assert `PreflightResult.checks["timestamp_alignment"] == True` (`misaligned_count == 0`)
- [ ] Assert `PreflightResult.passed == True`
- [ ] Record `PreflightResult.data_hash` (64-char SHA-256 hex)
- [ ] Call `governance_engine.check_phase_a_ready(preflight_passed=True)` — must return `(CLEAR, _)`
- [ ] Call `governance_engine.transition(DATA_READY, reason="preflight passed")`

### Gate 2: PHASE_A_RUNNING — Phase A Backtest

- [ ] Confirm `governance_engine.state == DATA_READY`
- [ ] Call `governance_engine.transition(PHASE_A_RUNNING, reason="starting Phase A")`
- [ ] Call `PPFIntegratedBacktester(ppf_params=...).run(session, symbol="SOL/USDT", exchange="binance", timeframe="1h")`
- [ ] Assert `IntegratedBacktestResult.ppf.overall_evaluated_bars > 0`
- [ ] Assert `IntegratedBacktestResult.baseline_id` is a non-empty UUID string
- [ ] Record `PPFBacktestResult.fpr`, `deny_rate`, `novelty_rate`, `unresolved_count`
- [ ] Compute `unresolved_rate = unresolved_count / max(novelty_event_count, 1)`
- [ ] Call `governance_engine.check_baseline_freeze_ready(unresolved_rate)` — must return `(CLEAR, _)` (FC-02: unresolved_rate <= 0.05)

### Gate 3: BASELINE_FROZEN — Freeze and Seal

- [ ] Call `PPFBaselineManager().freeze_baseline(session, baseline_id, frozen_by="system", preflight_hash=data_hash)`
- [ ] Assert `result["success"] == True`
- [ ] Record `seal_hash = result["seal_hash"]` (64-char SHA-256 hex)
- [ ] Call `PPFBaselineManager().verify_seal(session, baseline_id)` — assert `result["valid"] == True`
- [ ] Call `governance_engine.transition(BASELINE_FROZEN, reason=f"baseline_id={baseline_id} sealed")`
- [ ] Assert `governance_engine.state == BASELINE_FROZEN`
- [ ] Confirm `PPFBacktestBaseline.frozen == True`, `frozen_at` set, `seal_hash` set

### Gate 4: PHASE_B_COLLECTING — Live Shadow Accumulation

- [ ] Call `governance_engine.check_phase_b_ready(baseline_frozen=True)` — must return `(CLEAR, _)` (FC-03)
- [ ] Call `PPFBaselineManager().start_phase_b(session, baseline_id)` — assert `result["success"] == True`
- [ ] Call `governance_engine.transition(PHASE_B_COLLECTING, reason="Phase B started")`
- [ ] Verify Celery Beat task `ppf_shadow_tasks.run_ppf_shadow_eval` is scheduled hourly
- [ ] Accumulate live shadow bars; poll `governance_engine.check_validation_ready(bars_collected, novelty_events)` hourly
- [ ] Continue until both conditions met:
  - `bars_collected >= 336` (FC-04: ~14 days at 1h)
  - `novelty_events >= 10` (FC-05: VAL-QTY-001 S2P-EI1)

### Gate 5: VALIDATION_READY — Transition

- [ ] Confirm `governance_engine.check_validation_ready(bars_collected, novelty_events)` returns `(CLEAR, _)`
- [ ] Call `governance_engine.transition(VALIDATION_READY, reason=f"bars={bars_collected} events={novelty_events}")`

### Gate 6: VAL_PDC_002_ISSUED — Comparator + Verdict

- [ ] Call `PPFBacktestComparator().compare(session, baseline_id)` — produces `PPFComparisonReport`
- [ ] Call `PPFBaselineManager().verify_seal(session, baseline_id)` — record `seal_valid`
- [ ] Call `governance_engine.check_val_pdc_002_ready(comparison_report.all_within_tolerance)` — must return `(CLEAR, _)` (FC-06)
- [ ] Assert `comparison_report.live_bars_evaluated >= 336`
- [ ] Assert `comparison_report.live_novelty_count >= 10`
- [ ] Call `ValPDC002Judge().judge(comparison_report, seal_valid, governance_has_hard_block=False, novelty_events, bars_collected, baseline_id)`
- [ ] Record `ValPDC002Report.verdict` (`GO` / `HOLD` / `BLOCK`)
- [ ] Assert `ValPDC002Report.live_authorized == False` (invariant check)
- [ ] Call `governance_engine.transition(VAL_PDC_002_ISSUED, reason=f"verdict={verdict.value}")`
- [ ] State is now terminal (`ALLOWED_TRANSITIONS[VAL_PDC_002_ISSUED] == []`)

---

## 6. Receipt / Log Field List

### 6.1 OhlcvPreflightValidator — log event: `ohlcv_preflight_complete`

| Field | Type | Description |
|-------|------|-------------|
| `passed` | bool | Overall pass/fail |
| `exchange` | str | Exchange identifier |
| `symbol` | str | Trading pair |
| `timeframe` | str | Candle timeframe |
| `candle_count` | int | Total candles in DB for this symbol/TF |
| `coverage_pct` | float | Coverage percentage (0–100) |
| `days_covered` | float | Days spanned by OHLCV range |
| `gap_count` | int | Number of 1h gap sequences detected |
| `duplicate_count` | int | Number of open_time groups with duplicates |
| `misaligned_count` | int | Candles where `open_time % 3_600_000 != 0` |
| `first_ts` | int | Earliest open_time (Unix ms) |
| `last_ts` | int | Latest open_time (Unix ms) |
| `data_hash` | str | SHA-256 hex of `f"{first_ts}:{last_ts}:{candle_count}"` |
| `checks` | dict[str, bool] | Per-check results: `symbol_lock`, `timeframe_lock`, `coverage`, `gap_count`, `no_duplicates`, `timestamp_alignment` |
| `failure_reasons` | list[str] | Ordered list of all failure strings |

### 6.2 PPFBaselineManager — log events

**`ppf_baseline_frozen`**

| Field | Type | Description |
|-------|------|-------------|
| `baseline_id` | str | UUID of the frozen baseline |
| `frozen_by` | str | Process/user identifier |
| `seal_hash` | str | SHA-256 hex of frozen field digest |

**`ppf_baseline_seal_mismatch`** (warning)

| Field | Type | Description |
|-------|------|-------------|
| `baseline_id` | str | UUID |
| `stored_hash` | str | Hash stored in DB at freeze time |
| `computed_hash` | str | Hash recomputed from current field values |

**`ppf_baseline_seal_verified`**

| Field | Type | Description |
|-------|------|-------------|
| `baseline_id` | str | UUID |

**`ppf_baseline_phase_b_started`**

| Field | Type | Description |
|-------|------|-------------|
| `baseline_id` | str | UUID |

**`ppf_baseline_invalidated`**

| Field | Type | Description |
|-------|------|-------------|
| `baseline_id` | str | UUID |
| `reason` | str | Truncated to first 200 chars in log (stored up to 500) |

### 6.3 PPFGovernanceEngine — log events

**`ppf_governance_transition`**

| Field | Type | Description |
|-------|------|-------------|
| `from_state` | str | Previous `PPFGovernanceState` value |
| `to_state` | str | New `PPFGovernanceState` value |
| `reason` | str | Caller-supplied explanation |

**`ppf_governance_transition_blocked`** (error)

| Field | Type | Description |
|-------|------|-------------|
| `from_state` | str | Current state at block time |
| `to_state` | str | Attempted target state |
| `block_reason` | str | Either `TERMINAL_STATE` or `INVALID_TRANSITION` message |

**FC check warning events** (emitted on block returns):
- `ppf_governance_fc01_block` — preflight not passed
- `ppf_governance_fc02_block` — unresolved_rate too high (`unresolved_rate` field)
- `ppf_governance_fc02_invalid_rate` — rate outside [0, 1] (`rate` field)
- `ppf_governance_fc03_block` — no frozen baseline
- `ppf_governance_fc03_state_order_block` — state ordering violation (`state` field)
- `ppf_governance_fc04_block` — bars deficit (`bars_collected`, `deficit` fields)
- `ppf_governance_fc05_block` — events deficit (`novelty_events`, `deficit` fields)
- `ppf_governance_fc06_block` — metrics out of tolerance
- `ppf_governance_fc06_state_block` — state not VALIDATION_READY (`state` field)
- `ppf_governance_fc08_block_both` — state and tier both fail (`state`, `tier` fields)
- `ppf_governance_fc08_block_state` — state fails (`state` field)
- `ppf_governance_fc08_block_tier` — tier fails (`tier` field)
- `ppf_governance_fc08_clear` — paper entry authorized (`tier` field)

### 6.4 PPFIntegratedBacktester — log events

| Event Pattern | Fields |
|---------------|--------|
| `ppf_integrated_backtest_no_candles` | `symbol`, `exchange` |
| `ppf_integrated_backtest_loaded` | `symbol`, `bars` |
| `ppf_integrated_backtest_replay_done` | `total`, `evaluated`, `allow`, `deny`, `novelty` |
| `ppf_integrated_backtest_judgment_done` | `total`, `tp`, `fp`, `unresolved`, `fpr` |
| `ppf_integrated_backtest_baseline_persisted` | `id` (baseline_id UUID) |
| `ppf_integrated_backtest_baseline_persist_failed` | `error` (truncated to 200 chars) |

### 6.5 PPFBacktestComparator — log events

| Event Pattern | Fields |
|---------------|--------|
| `compare: baseline_id not found` (warning) | `baseline_id` |
| `compare: loaded baseline` | `id`, `symbol`, `exchange`, `evaluated_bars`, `novelty_rate`, `fpr` |
| `compare: found N live novelty events` | event count, `symbol`, `exchange` |
| `compare: live_novelty_rate / live_fpr / tp / fp / resolved` (debug) | rates and counts |
| `compare: deny_reason_distribution JS` (debug) | `JS`, `within` |
| `compare: DONE` | `baseline_id`, `live_bars`, `novelty`, `all_within_tolerance`, `eligible`, `reasons` count |

### 6.6 ValPDC002Judge — log event: `VAL-PDC-002 verdict issued`

| Field | Type | Description |
|-------|------|-------------|
| `verdict` | str | `GO`, `HOLD`, or `BLOCK` |
| `tier` | str | `GREEN`, `YELLOW`, or `RED` |
| `baseline_id` | str | UUID |
| `bars_collected` | int | Phase B bars counted |
| `novelty_events` | int | Phase B novelty count |
| `all_criteria_passed` | bool | All 7 criteria satisfied |
| `core_hard_criteria_passed` | bool | C1–C4 all satisfied |
| `seal_valid` | bool | C6 seal check result |
| `governance_has_hard_block` | bool | C7 input |
| `failure_count` | int | `len(failure_reasons)` |
| `live_authorized` | bool | Always False |

### 6.7 PPFBacktestBaseline — DB Table Fields (`ppf_backtest_baselines`)

| Column | Type | Immutability |
|--------|------|-------------|
| `id` | String(36) UUID PK | Immutable after INSERT |
| `symbol` | String(32) | Immutable |
| `exchange` | String(32) | Immutable |
| `timeframe` | String(10) | Immutable |
| `ppf_params_hash` | String(64) | Immutable |
| `total_bars` | Integer | Immutable |
| `evaluated_bars` | Integer | Immutable (in seal hash) |
| `deny_rate` | Float | Immutable (in seal hash) |
| `novelty_rate` | Float | Immutable (in seal hash) |
| `novelty_count` | Integer | Immutable |
| `fpr` | Float | Immutable (in seal hash) |
| `allow_count` | Integer | Immutable (in seal hash) |
| `deny_count` | Integer | Immutable (in seal hash) |
| `deny_reason_distribution` | Text (JSON) | Immutable (in seal hash) |
| `state_distribution` | Text (JSON) | Immutable (in seal hash) |
| `result_json` | Text (JSON) | Immutable |
| `frozen` | Boolean | Write-once: False → True |
| `frozen_at` | DateTime UTC | Write-once on freeze |
| `frozen_by` | String(100) | Write-once on freeze |
| `seal_hash` | String(64) | Write-once on freeze |
| `preflight_hash` | String(64) | Write-once on freeze |
| `phase_b_started` | Boolean | Write-once: False → True |
| `phase_b_started_at` | DateTime UTC | Write-once on Phase B start |
| `invalidated` | Boolean | Write-once: False → True |
| `invalidated_reason` | String(500) | Write-once on invalidation |
| `created_at` | DateTime UTC | Immutable |

Indexes: `ix_ppf_baseline_symbol_exchange_tf (symbol, exchange, timeframe)`, `ix_ppf_baseline_params_hash (ppf_params_hash)`

---

## 7. State Transition Table

States: `NOT_INITIALIZED (NI)`, `DATA_READY (DR)`, `PHASE_A_RUNNING (AR)`, `BASELINE_FROZEN (BF)`, `PHASE_B_COLLECTING (BC)`, `VALIDATION_READY (VR)`, `VAL_PDC_002_ISSUED (VI)`

| From \ To | NI | DR | AR | BF | BC | VR | VI |
|-----------|----|----|----|----|----|----|-----|
| **NI** | — | ALLOWED (FC-01 must be CLEAR before triggering) | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| **DR** | BLOCKED | — | ALLOWED (requires FC-01 CLEAR) | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| **AR** | BLOCKED | ALLOWED (reset on failure) | — | ALLOWED (requires FC-02 CLEAR + baseline persisted) | BLOCKED | BLOCKED | BLOCKED |
| **BF** | BLOCKED | BLOCKED | BLOCKED | — | ALLOWED (requires FC-03 CLEAR) | BLOCKED | BLOCKED |
| **BC** | BLOCKED | BLOCKED | BLOCKED | ALLOWED (reset to re-run Phase A) | — | ALLOWED (FC-04 + FC-05 CLEAR) | BLOCKED |
| **VR** | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | — | ALLOWED (FC-06 CLEAR) |
| **VI** | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | — (TERMINAL) |

**Enforcement**: `PPFGovernanceEngine.transition(target)` raises `ValueError` for any BLOCKED cell.
**Reset paths**: `PHASE_A_RUNNING → DATA_READY` (Phase A failure); `PHASE_B_COLLECTING → BASELINE_FROZEN` (Phase B reset before re-accumulation).

### 7.1 FC Rule Activation by Transition

| Transition | FC Rules Checked Before Executing |
|-----------|-----------------------------------|
| `NI → DR` | FC-01 `check_phase_a_ready(preflight_passed)` |
| `DR → AR` | FC-01 must already be CLEAR (confirmed at NI→DR) |
| `AR → BF` | FC-02 `check_baseline_freeze_ready(unresolved_rate)` |
| `BF → BC` | FC-03 `check_phase_b_ready(baseline_frozen=True)` |
| `BC → VR` | FC-04 + FC-05 `check_validation_ready(bars_collected, novelty_events)` |
| `VR → VI` | FC-06 `check_val_pdc_002_ready(all_metrics_in_tolerance)` |
| Any → Live | FC-07 `check_live_entry()` — always `HARD_BLOCK`; no transition to live exists |
| VI → Paper | FC-08 `check_paper_entry(tier)` — `HARD_BLOCK` unless `tier == GREEN` |

---

## 8. Shadow → Paper → Live Application Order

### 8.1 Stage 1: Shadow (REQUIRED FIRST)

**Entry condition**: `governance_engine.state == PHASE_B_COLLECTING`

**Activities**:
- Celery Beat task `ppf_shadow_tasks.run_ppf_shadow_eval` runs hourly
- Each bar evaluation emits `PPFNoveltyEvent` rows to DB (when O9=True fires)
- `PPFNoveltyEvent` fields populated: `symbol`, `exchange`, `event_ts`, `deny_reason_code`, `judgment` (initially null, filled by `NoveltyJudgmentEngine` post-hoc)
- `PPFGateHandler` operates in shadow mode: evaluates gate, logs result, does NOT block real orders

**Exit conditions** (both required simultaneously, FC-04 + FC-05):
- `bars_collected >= 336` (14 days × 24h of 1H bars)
- `novelty_events >= 10` (VAL-QTY-001 S2P-EI1)

**Prohibition**: Cannot advance to paper until `VAL_PDC_002_ISSUED` state is reached AND tier is GREEN.

### 8.2 Stage 2: Validation Gate (VAL-PDC-002)

**Entry condition**: `governance_engine.state == VALIDATION_READY`

**Activities**:
1. Run `PPFBacktestComparator().compare(session, baseline_id)` → `PPFComparisonReport`
2. Verify seal: `PPFBaselineManager().verify_seal(session, baseline_id)` → `seal_valid`
3. Issue verdict: `ValPDC002Judge().judge(...)` → `ValPDC002Report`
4. Check FC-06: `governance_engine.check_val_pdc_002_ready(all_within_tolerance)`
5. Transition: `governance_engine.transition(VAL_PDC_002_ISSUED, reason=f"verdict={verdict.value}")`

**Verdict outcomes**:
- `GO` + GREEN tier: paper entry gate opens (proceed to Stage 3)
- `HOLD` + YELLOW tier: continue shadow accumulation; do NOT advance to paper
- `BLOCK`: investigate failure_reasons; do NOT advance to paper

### 8.3 Stage 3: Paper (CONDITIONAL)

**Entry condition**: ALL of the following must hold:
1. `governance_engine.state == VAL_PDC_002_ISSUED`
2. `tier == GREEN` (novelty_events >= 10, all criteria passed)
3. `ValPDC002Report.verdict == GO`
4. `governance_engine.check_paper_entry(PPFGovernanceTier.GREEN)` returns `(CLEAR, _)` (FC-08)
5. Human operator has reviewed the `ValPDC002Report` and issued explicit paper-start authorization (outside automated system)

**Activities**:
- `PPFGateHandler` operates in paper mode: gate evaluation actively filters signals
- Real executions are suppressed; paper account filled
- Monitoring: `PPFBacktestComparator().compare()` continues to run to detect drift

**Prohibitions**:
- FC-07 `check_live_entry()` remains `HARD_BLOCK` throughout paper stage
- `ValPDC002Judge.check_live_authorized()` returns `(False, ...)` throughout paper stage
- No auto-escalation from paper to live

### 8.4 Stage 4: Live (PERMANENTLY PROHIBITED — current codebase)

**Status**: NOT AUTHORIZED

**Hard prohibitions (cannot be cleared by any code path)**:
- `PPFGovernanceEngine.check_live_entry()` → always `(HARD_BLOCK, "LIVE_ENTRY_PROHIBITED: PPF live mode not authorized")`
- `ValPDC002Judge.check_live_authorized()` → always `(False, "LIVE_NOT_AUTHORIZED: PPF production deployment requires explicit human approval beyond VAL-PDC-002")`
- `ValPDC002Report.live_authorized` → hardcoded `False` in constructor and `judge()` method

**Required action to authorize**: A new Change Request must be opened. The CR must:
1. Define explicit live entry criteria beyond VAL-PDC-002
2. Include a separate human approval gate
3. Remove or conditionalize the hard prohibition in `check_live_entry()` and `check_live_authorized()`
4. Receive governance sign-off outside this codebase

**Application order summary**:

```
NOT_INITIALIZED
  → [preflight PASS + FC-01 CLEAR] →
DATA_READY
  → [FC-01 confirmed] →
PHASE_A_RUNNING
  → [Phase A complete + FC-02 CLEAR (unresolved_rate <= 5%)] →
BASELINE_FROZEN  ← seal_hash computed and stored
  → [FC-03 CLEAR + Phase B start] →
PHASE_B_COLLECTING  ← shadow mode ACTIVE (PPFGateHandler observes, does not block)
  → [bars >= 336 AND events >= 10 (FC-04 + FC-05 CLEAR)] →
VALIDATION_READY
  → [FC-06 CLEAR + VAL-PDC-002 issued] →
VAL_PDC_002_ISSUED  ← TERMINAL STATE
  → [verdict=GO + tier=GREEN + FC-08 CLEAR + human authorization] →
PAPER MODE  ← gate actively filters (not a governance state; external authorization)
  → [live: HARD_BLOCK permanent] →
LIVE: PROHIBITED
```
