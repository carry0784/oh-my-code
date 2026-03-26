# C-04 Genesis Baseline — 2026-03-26

**evidence_id**: C04-GENESIS-BASELINE-2026-03-26
**date**: 2026-03-26
**type**: CONTROLLED_EXECUTION_FREEZE_RECEIPT

---

## Core Principle

**이번 세션의 진짜 산출물은 실행 성공 자체가 아니라, SSOT 정렬된 통제 실행 기준선을 확보했다는 점이다.**

**all_clear=true grants controlled execution eligibility, not unconditional production freedom.**

**Dashboard, Gate, Approval, and Policy must derive score-dependent decisions from the same freshness-aligned SSOT path.**

---

## 1. Commit Set (14 commits)

| # | Hash | Message |
|---|------|---------|
| 1 | 33fd0c0 | feat: seal C-04 Manual Action Phase 1-9 baseline |
| 2 | 4374bca | feat: seal C-04 Phase 10 boundary hardening |
| 3 | ba7cc6a | docs: C-04 Manual Action final completion freeze |
| 4 | c0b92d6 | docs: C-04 operational authorization documents |
| 5 | 64b5052 | feat: B-19 Execution Pipeline viewer |
| 6 | 3a568b2 | refactor: Tab 3 layout section dividers |
| 7 | 87981a5 | fix: resolve aiodns DNS failure in exchange wrappers |
| 8 | 54f601e | fix: snapshot_age fallback to AssetSnapshot |
| 9 | 599bb45 | fix: align Gate ops_score with real DB snapshot |
| 10 | 2455b9b | fix: resolve STALE_SNAPSHOT hardcoded unknown |
| 11 | 2a48d70 | fix: check runner reads real DB values |
| 12 | a6e0f13 | fix: align Approval ops_score with real DB |
| 13 | 7e4d852 | fix: align Policy and CheckRunner with real DB SSOT |
| 14 | af46b97 | fix: _build_ops_safety_summary import and field alignment |

---

## 2. Test Baseline

| Suite | Count |
|-------|-------|
| Full regression | **2174 passed** |
| C-04 tests | **336 passed** |
| Pre-existing failures | 13 (C-04 unrelated) |

---

## 3. Chain State at Genesis

| Stage | Value |
|-------|-------|
| Pipeline | ALL_CLEAR |
| Preflight | READY (8/8) |
| Gate | OPEN (4/4) |
| Approval | APPROVED |
| Policy | MATCH |
| ops_score | 0.925 |
| all_clear | **true** |
| blocked | **[]** |

---

## 4. First Controlled Execution

| Field | Value |
|-------|-------|
| decision | **EXECUTED** |
| receipt_id | **RCP-046d7776fa14** |
| action_id | MA-9b8db8df1640 |
| audit_id | **AUD-3618c237** |
| chain_state | 9/9 ALL PASS |
| reason | All 9 stages passed. Validated intent recorded. |
| timestamp | 2026-03-26T00:58:21Z |

---

## 5. SSOT Principle

All score-dependent decisions must derive from the same freshness-aligned path:

```
Position.updated_at (primary)
  → AssetSnapshot.snapshot_at (fallback)
    → snapshot_age_seconds
      → connectivity score
        → ops_score average
```

Consumers aligned to this SSOT:
- Dashboard `_compute_integrity_panel`
- Gate `_check_ops_score`
- Approval `_collect_ops_score`
- Policy `_recheck_ops_score`
- CheckRunner `_get_snapshot_age_sync`
- Preflight `exchange_snapshot` assessment

---

## 6. Forbidden Regressions

Any of the following would invalidate this baseline:

| # | Regression |
|---|-----------|
| 1 | Hardcoded snapshot_age=None reintroduced in any score consumer |
| 2 | SSOT path divergence between Dashboard/Gate/Approval/Policy |
| 3 | Evidence store fallback accepted as OK grade |
| 4 | Auto-execution path introduced |
| 5 | Chain bypass or hidden flag |
| 6 | Receipt-less execution |
| 7 | Audit-less execution |
| 8 | Test count regression below 2174/336 |
| 9 | all_clear=true without full 9-stage chain satisfaction |

---

## 7. Scope-External Changes

The following modified files are from prior sessions and are NOT part of this baseline:

- `.gitignore`, `alembic/env.py`, `app/agents/governance_gate.py`
- `app/core/config.py`, `app/core/logging.py`, `app/main.py`
- `app/models/*`, `app/schemas/position.py`, `app/services/*`
- `exchanges/factory.py`, `pyproject.toml`, `requirements.txt`
- `src/kdexter/*`, `workers/*`

These require separate cleanup in a future session.

---

## 8. Freeze Receipt Checksum

| Field | Value |
|-------|-------|
| **commit_final** | d66ecf9 |
| **test_total** | 2174 passed |
| **test_c04** | 336 passed |
| **receipt_id** | RCP-046d7776fa14 |
| **audit_id** | AUD-3618c237 |
| **chain_state** | 9/9 ALL PASS, all_clear=true |
| **SSOT_principle** | All score consumers use same freshness-aligned DB path |

---

## 9. Operational Rules (Post-Genesis)

### Genesis Regression Gate
> 모든 후속 변경은 C-04 Genesis Baseline 대비 회귀 없음이 증명되어야 한다.

### UI Before Guard Prohibition
> Guard/Block 검증이 끝나기 전에는 UI 확장 금지.

### SSOT Drift Sentinel
> Dashboard / Gate / Approval / Policy의 score source path가 서로 다르면 즉시 실패로 간주.

---

## 10. Genesis Protected Fields

Changes to any of the following require Genesis Regression Gate review:

| Field | Location |
|-------|----------|
| receipt_id schema | `app/schemas/manual_action_schema.py` |
| audit_id generation path | `app/core/manual_action_handler.py` |
| chain_state aggregation | `ManualActionChainState.all_pass` |
| score source path | `_compute_integrity_panel` → `snapshot_age_seconds` |
| all_clear derivation | `OpsSafetySummary.all_clear` |
| SSOT freshness path | Position.updated_at → AssetSnapshot.snapshot_at fallback |

---

## 11. Allowed / Forbidden Next Steps

**Allowed:**
- Guard/block validation testing
- Scope-external change cleanup
- Auto-execution block verification
- SSOT Drift Sentinel test creation
- Operator UI connection (after guard verification)

**Forbidden:**
- UI-first expansion before guard verification
- Score path duplication (new independent calculation)
- Receipt/audit schema breaking changes
- Chain bypass or hidden enable flag
- Execution without full 9-stage chain satisfaction

---

## 12. Baseline Delta Review Template

All future changes must be reviewed against:

```
1. Genesis 대비 변경 파일
2. Genesis 대비 상태 변화
3. Genesis 대비 금지선 침범 여부
4. Genesis Regression Gate 결과 (2174/336 유지?)
5. SSOT Drift Sentinel 결과 (경로 일치?)
```

---

## 13. Next Session Priority

1. Baseline preservation verification (2174/336 tests)
2. Scope-external change cleanup
3. Auto-execution block verification
4. Operator UI connection (chain/state/evidence invariance)
5. Phase 9+ expansion decision
