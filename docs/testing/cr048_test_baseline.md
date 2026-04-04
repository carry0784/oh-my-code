# CR-048 Test Baseline Manifest

**Sealed**: 2026-04-02
**Phase coverage**: 0 + 1 + Immutability + Recovery + 2 + 3A + 4A + 4B + 4C + 5A + 5B + 6A + 6B-1 + 6B-2 + 6B-2h + 6B-2a + 6B-beat + 6B-pool

## File Inventory

| # | File | Tests | Phase |
|---|------|-------|-------|
| 1 | `tests/test_registry.py` | 75 | 0 + 1 (Constitution + Control Plane) |
| 2 | `tests/test_strategy_registry.py` | 8 | 1 (Strategy Registry) |
| 3 | `tests/test_asset_registry.py` | 49 | 2 (Asset Registry) |
| 4 | `tests/test_symbol_screener.py` | 65 | 3A (Symbol Screener) |
| 5 | `tests/test_backtest_qualification.py` | 49 | 4A (Backtest Qualification) |
| 6 | `tests/test_paper_shadow.py` | 52 | 4B (Paper Shadow + Promotion Gate) |
| 7 | `tests/test_paper_evaluation.py` | 51 | 4C (Paper Evaluation + Promotion Wiring) |
| 8 | `tests/test_runtime_loader.py` | 122 | 5A+5B (Runtime Loader + Router + Cache + Integrity Hardening) |
| 9 | `tests/test_universe_runner.py` | 209 | 6A + 6B-1 + 6B-2 + 6B-2h + 6B-2a + 6B-beat + 6B-pool + CR-048A (Universe + Runner + Analyze + Receipt + TradingHours + Periodic + State + DB Wiring + Beat + Pool + Async Lifecycle) |

## Totals

- **Files**: 9
- **Reported by pytest**: 620
- **All green at time of seal**: YES

> **CI status on main (as of PR #25, 2026-04-04)**:
> 7 of these 9 files are in **central skip** via `conftest.py`
> `_CR048_FORWARD_TEST_FILES` because prerequisite model/service code
> (CR-048+) has not yet landed on main. The skip will be removed
> file-by-file as each prerequisite CR merges. See `tests/conftest.py`
> for the authoritative skip list.

## Notes

- Previous sessions reported "320 tests" which included CR-046 test files
  (`test_cr046_*.py`) and possibly transient test files from earlier phases.
  This manifest covers CR-048 tests only.
- The 289 vs 278 difference is due to `test_registry.py` reporting 15 in
  the table above but collecting 75 via pytest (class-based test expansion).
  The pytest `--co -q` count of **289** is the authoritative number.
- Immutability Zone and Recovery Hardened tests are embedded within the
  registry and safe_mode model tests, not in separate files.

## Authoritative Count

**620 tests from 9 files** as of CR-048A async lifecycle seal.

### History

| Phase | Files | Tests | Date |
|-------|-------|-------|------|
| 4C seal | 7 | 289 | 2026-04-02 |
| 5A seal | 8 | 369 | 2026-04-02 |
| 5B seal | 8 | 415 | 2026-04-02 |
| 6A seal | 9 | 476 | 2026-04-02 |
| 6B-1 seal | 9 | 496 | 2026-04-02 |
| 6B-2 seal | 9 | 537 | 2026-04-02 |
| 6B-2h seal | 9 | 564 | 2026-04-02 |
| 6B-2a seal | 9 | 584 | 2026-04-02 |
| 6B-beat seal | 9 | 592 | 2026-04-02 |
| 6B-pool seal | 9 | 598 | 2026-04-02 |
| 6B-ops seal | 9 | 598 | 2026-04-02 |
| CR-048A seal | 9 | 620 | 2026-04-02 |

All future batches must report against this manifest.
Additions are appended; removals require explicit justification.
