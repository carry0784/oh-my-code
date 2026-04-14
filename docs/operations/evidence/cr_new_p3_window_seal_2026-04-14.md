# CR-NEW: P3 Validation Window Contamination Seal

**Doc ID**: cr_new_p3_window_seal_2026-04-14
**Doc Path (repo-relative)**: docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md
**Sealed At**: 2026-04-14
**Signed By**: operator (A)
**approval_basis_doc**: CR-NEW v3.1
**approval_verdict**: APPROVED_A
**Ledger Class**: VRL (Validation Result Ledger, 영구보존)

---

## 1. Window Identification

- **window_id**: P3 ~2026-04-28
- **window_source**: PR #98 merged (commit 48915d2)
- **window_started_at**: 2026-04-14
- **intended_end**: 2026-04-28 (14D)
- **track_ref**: project_ppf_validation_chain_sealed

---

## 2. Contamination Cause

- **root_cause**: collector numpy scalar leak → psycopg2 `InvalidSchemaName("np")`
- **leak_field**: `snapshot.indicators.obv` (numpy.float64)
- **entry_point**: `workers/tasks/data_collection_tasks.py` — `MarketState(...)` construction
- **commit_failure_mode**: `schema "np" does not exist`
- **log_evidence**:
  - file: `logs/celery_beat.log` + `logs/celery_worker.log`
  - occurrence_count: 31,600
- **first_failure_at**: 2026-04-08 00:25:02
- **detection_at**: 2026-04-14 (TRCC run via `scripts/health_check.py`)

---

## 3. Window Validity Assessment

- **collector_state_at_window_start**: BROKEN (6 days prior, since 2026-04-08)
- **market_states_freshness_during_window**: STALE → UNAVAILABLE (>4h) throughout
- **orchestrator_outcome_during_window**: skip_unavailable (BTC/USDT, SOL/USDT)
- **shadow_observation_inserts_during_window**: effectively 0 (write path blocked at quality gate)
- **paper_observations_inserts_during_window**: 0
- **Conclusion**: 이 창은 P3 승급·봉인·PASS/FAIL 판정 근거로 사용할 수 없음.

---

## 4. Seal Decision

**Window `P3 ~04-28`을 오염창(contaminated window)으로 봉인한다.**

### 4.1 Carryover Ban (명문화)

오염창 내부에서 수집/파생된 어떤 값도:

- **(i)** 새 창의 초기 상태로 계승 금지
- **(ii)** 새 창의 baseline/threshold 산정에 포함 금지
- **(iii)** P3 누적 통계(streak, bar_count, pass_ratio 등)에 가산 금지
- **(iv)** SEALED 문서·receipt·ledger의 통계 근거로 인용 금지

**예외**: 이 봉인 메타 receipt 자체(근거 문서) 및 그에 연결된 메타 기록은 허용.

### 4.2 New Window Prerequisite

새 14D P3 창은 다음 모두 충족 시에만 개시한다:

- Change-1 (Option-α `_to_native()`) merge 완료
- Change-2 (terminal_failure 명시 분류) merge 완료
- Change-3 반영 (ops_state.json 오염창 플래그 + carryover 주석)
- P0 Preflight PASS
- P1 Recovery Smoke PASS
- P2 Observation Integrity Smoke PASS

---

## 5. Recovery Linkage

| 필드 | 값 | 상태 |
|---|---|---|
| `seal_basis_receipt` | cr_new_p3_window_seal_2026-04-14 | **THIS** (자기참조 앵커, 후속 receipt의 backward-link 기준점) |
| `fix_commit_sha` | `fba493e6f1d69c5f3135e6248296c08597a14442` | **SEALED** (PR #99 squash merge, 2026-04-14T14:23:00Z) |
| `source_branch_ref` | `origin/cr-new/collector-numpy-leak-fix` | **PRESERVED** (auto-delete 후 즉시 re-push 복구, 2026-04-14) |
| `pre_squash_commit_chain` | `5ed0171 → ec5384a → 7a23150` | **PRESERVED** (docs receipt → collector fix → CI corrective; source branch에서 fetch 가능) |
| `merge_method` | `squash` | repo policy `allow_squash_merge=true, allow_merge_commit=false, allow_rebase_merge=false` 하의 유일 허용 경로 |
| `branch_auto_deleted_recovered` | `true` | repo policy `delete_branch_on_merge=true`로 인한 auto-delete 발생 → local objects 기반 re-push로 회복 |
| `recovery_smoke_result` | (TBD) | P1 Recovery Smoke receipt 참조 (`cr_new_p1_recovery_smoke_<date>.md`) |
| `observation_smoke_result` | (TBD) | P2 Observation Integrity 결과 참조 |
| `new_window_started_at` | (TBD) | P2 PASS 후 새 창 개시 시 기록 |
| `new_window_baseline_at` | (TBD) | 새 창 baseline 확정 시 기록 |

### 5.1 Squash Merge Recovery Note

저장소 정책이 `squash-only` + `delete_branch_on_merge=true`로 고정되어 있어,
PR merge 완료 시점에 source branch가 remote에서 자동 소실된다.

본 건은 merge 직후 local objects로부터 즉시 `git push origin cr-new/collector-numpy-leak-fix`
재푸시를 수행하여 pre-squash 3-commit chain을 remote ref에 복원하였다.

이 저장소에서의 squash merge 표준 시퀀스는 다음과 같다:

```
PR squash merge → main 반영 SHA 확인 → 즉시 source branch re-push
→ remote ref 존재 확인 → receipt linkage 봉인
```

본 시퀀스 미이행 시 pre-squash commit chain이 garbage collection 대상이 되어
거버넌스 추적성이 영구 손실될 위험이 있다.

---

## 6. CR-046 SOL Stage B Impact

- 현 `bar_count: "1/24"` 표기는 봉인 이전 수기 주석 (수집기 고장 이후 자동 증분 없음)
- 봉인 이전 bar는 24-bar zero-failure 판정 근거에서 제외
- 새 창 개시 시 `bar_count` 재설정 예정: `0/24 (post-seal)`
- Stage B → Stage C 승격 판정은 **새 창의 24-bar zero-failure**를 기준으로 한다

---

## 7. Operator Notes

- **P2 Observation Integrity Smoke**는 자체 write를 생성하지 않음.
  단, 관찰 대상 task(예: `shadow-observation-5m`)의 자연 write는 별도 해석한다.
- **activation_gate**는 LOCKED 유지. `write_budget` 미소비.
- **Recovery Smoke(P1)**의 bounded write(`market_states` 1행)는 activation_gate write_budget과 분리된 경로이며, 수집기 복구 검증 용도로 한정한다.
- **carryover 금지**는 문서/receipt/metric/ledger 모든 레이어에 적용된다.

---

## 8. Change Control Reference

- **CR ID**: CR-NEW (deterministic collector recovery + P3 window seal)
- **Version**: v3.1
- **Units**:
  - Change-1: Option-α `_to_native()` helper — `workers/tasks/data_collection_tasks.py`
  - Change-2: `terminal_failure` 명시 분류 (deterministic vs transient)
  - Change-3: ops_state.json 오염창 플래그 + carryover ban 반영
- **Smoke Structure**: P0 Preflight (no-write) → P1 Recovery Smoke (bounded real write) → P2 Observation Integrity Smoke (no new write)

---

## 9. Signatures

- **Sealed**: 2026-04-14 operator (A)
- **Change Control**: CR-NEW v3.1
- **Ledger Class**: VRL (영구보존)
- **Supersedes**: 없음 (신규 봉인)
- **Related Docs**:
  - `docs/operations/evidence/cr_new_p1_recovery_smoke_<date>.md` (실행 후 생성 예정)
  - `ops_state.json` (Change-3 반영 예정)
