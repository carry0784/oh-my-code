# P3 Operational Lock Memo

## Status: P3_SHADOW_ACCUMULATION_ACTIVE

## Lock Window

| Field | Value |
|-------|-------|
| Start | 2026-04-14 00:18 KST (2026-04-13T15:18Z) |
| End (14D) | 2026-04-28 00:18 KST (2026-04-27T15:18Z) |
| Active Baseline ID | `59510964-a975-4561-863d-e22584353eda` |
| Scheduler | `ppf-shadow-eval-hourly` (3600s) |
| Concurrency Key | `ppf_shadow_eval_running` (TTL=420s) |

## Change-Frozen Items (14D Window)

| Item | Frozen Value | Modification |
|------|-------------|--------------|
| active_baseline_id | `59510964...` | FORBIDDEN |
| baseline row fields | frozen/sealed/verified | FORBIDDEN |
| beat interval | 3600s | FORBIDDEN |
| risk_filter_pass | False | FORBIDDEN |
| novelty judgment rules | 3% disruption threshold, 20-bar window | FORBIDDEN |
| PPF parameters | default_params | FORBIDDEN |
| comparator | NOT STARTED | FORBIDDEN until window close |
| VAL-PDC-002 | NOT STARTED | FORBIDDEN until window close |

## Time Convention: UTC-Naive

- DB storage: `TIMESTAMP WITHOUT TIME ZONE`, all values are UTC
- Python: `datetime.utcnow()` for all PPF-related timestamps
- Interpretation: all stored timestamps are UTC, no timezone offset stored
- Comparison: always UTC-to-UTC, never mix timezone-aware and naive
- Receipt/log display: append `Z` or `UTC` suffix for human readability

## Fail-Closed Conditions

Any of the following triggers immediate HOLD:

- Shadow task 2+ consecutive misses
- Novelty persistence failure
- Active baseline lookup returns None or wrong ID
- Baseline seal_hash mismatch (tamper detected)
- Duplicate event for same timestamp
- Redis lock conflict > 3 consecutive occurrences

## Hourly Health Check Fields

Each execution should produce:

| Field | Source |
|-------|--------|
| executed_at | task_result.last_run |
| status | task_result.status |
| lock_acquired | task_result.lock_acquired |
| novelty_detected | task_result.novelty_detected |
| novelty_persisted | task_result.novelty_persisted |
| bars_fetched | task_result.ohlcv_bars_fetched |
| windows_advanced | task_result.windows_advanced |
| duration_ms | task_result.duration_ms |

## Next Action After Window Close

`P3_WINDOW_14D_CLOSED` → `COMPARATOR_REVIEW_ELIGIBLE` (user approval required)
