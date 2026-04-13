# Step 6 — Type Safety: Blocking Typecheck Tier Criteria

## Tier Classification

### Tier 1 — Blocking (CI must pass)

Strict mypy with `--disallow-untyped-defs --disallow-incomplete-defs`.
Failures block PR merge.

| Module | Status | Since |
|--------|--------|-------|
| `app/services/data_provider.py` | PASS | pre-existing |
| `app/services/strategy_genome.py` | PASS | pre-existing |
| `app/services/system_health.py` | PASS | pre-existing |
| `app/services/strategy_runner.py` | PASS | pre-existing |
| `app/services/screening_transform.py` | PASS | pre-existing |
| `app/services/strategy_tournament.py` | PASS | pre-existing |
| `app/services/sector_rotator.py` | PASS | pre-existing |
| `app/services/sentiment_collector.py` | PASS | pre-existing |
| `app/services/screening_qualification_pipeline.py` | PASS | pre-existing |
| `app/services/strategy_lifecycle.py` | PASS | pre-existing |
| `app/services/walk_forward_validator.py` | PASS | pre-existing |
| `app/services/strategy_registry.py` | PASS | pre-existing |
| `app/services/trend_observation_service.py` | PASS | pre-existing |
| `app/services/watch_volume_service.py` | PASS | pre-existing |
| `app/services/symbol_screener.py` | PASS | pre-existing |
| `app/services/full_cycle_backtester.py` | PASS | Step 6 |
| `app/services/history_data_manager.py` | PASS | Step 6 |

Total: 17 files (15 pre-existing + 2 fixed in Step 6)

Note: `case_accumulation.py`, `observation_chain_service.py`, `observation_chain.py` will be
added to Tier 1 once PR #95 (Step 5) is merged.

### Tier 2 — Advisory (CI non-blocking)

Full `app/` scan with relaxed settings. `continue-on-error: true`.
Failures are visible but do not block merge.

Baseline: ~771 errors / 146 files (as of 2026-04-14).

### Promotion Path

To promote a module from Tier 2 to Tier 1:
1. Fix all mypy strict errors in the file
2. Verify with `--follow-imports=skip` (no transitive dependency breakage)
3. Add to CI `typecheck-blocking` job file list
4. PR review + merge

## Error Category Breakdown (Tier 2 baseline)

| Error Code | Count | Description |
|------------|-------|-------------|
| `type-arg` | 294 | Missing generic type arguments |
| `no-untyped-def` | 151 | Functions without type annotations |
| `no-any-return` | 74 | Returning Any from typed function |
| `assignment` | 49 | Type mismatch in assignment |
| `arg-type` | 36 | Argument type mismatch |
| `attr-defined` | 35 | Missing attribute access |
| `index` | 32 | Invalid index operation |
| Other | 100 | Various (union-attr, dict-item, etc.) |

## Configuration

### pyproject.toml

```toml
[tool.mypy]
python_version = "3.11"
strict = true

[[tool.mypy.overrides]]
module = ["app.api.routes.*", "app.agents.*", "app.core.*", ...]
disallow_untyped_defs = false  # relaxed for Tier 2
```

### CI Jobs

- `typecheck-blocking`: Tier 1 files, strict, **failures block merge**
- `typecheck-advisory`: Full `app/`, relaxed, `continue-on-error: true`
