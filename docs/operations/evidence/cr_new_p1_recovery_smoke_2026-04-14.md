# CR-NEW v3.1 P1 Recovery Smoke Evidence

**Doc ID**: cr_new_p1_recovery_smoke_2026-04-14
**Doc Path (repo-relative)**: docs/operations/evidence/cr_new_p1_recovery_smoke_2026-04-14.md
**Created At**: 2026-04-14
**Signed By**: operator (A)
**approval_basis_doc**: CR-NEW v3.1 + user conditional GO (B1)
**approval_verdict**: APPROVED_A (conditional: P0 PASS → B1 1-row bounded)
**Ledger Class**: VRL (Validation Result Ledger, 영구보존)
**Related Docs**:
- `docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md` (SSOT, PR #100 `fc4a91c`)
- `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` (PR #101 `b26a0dc`)

---

## 1. Scope (blast radius)

| 필드 | 값 |
|---|---|
| `blast_radius` | **`single_row_market_states_only`** |
| `auto_retry` | **`false`** |
| `target_table` | `market_states` (no other tables touched) |
| `target_symbol` | `SOL/USDT` (activation_gate.allowed_symbols와 일치) |
| `invocation_path` | in-process `collect_market_state.apply(args=['SOL/USDT']).get()` (no broker consumption) |
| `authorized_writes` | 1 row |
| `executed_writes` | 1 row |
| `extra_table_writes` | 0 |
| `retry_count` | 0 |

---

## 2. P0 Preflight Results (모두 PASS)

| 항목 | 결과 | 증거 |
|---|---|---|
| P0.1 main SHA = `b26a0dc` | **PASS** | `origin/main = b26a0dc41f4ce13aca711ac66e9e1de0826102c9` |
| P0.2 collector fix on main tree | **PASS** | `_sync_engine` line 29, `_SyncSessionFactory` line 36, `_to_native` line 43, `_classify_failure` line 72 |
| P0.2a `_to_native(snapshot.*)` scalar wraps | **PASS** | 31개 (모든 indicator/sentiment/on_chain/microstructure 스칼라 필드) |
| P0.3 `activation_gate.write_budget == 1` | **PASS** | ops_state.json |
| P0.3 `activation_gate.writes_consumed == 0` | **PASS** | ops_state.json |
| P0.3a `contaminated_windows[0].status == SEALED_CONTAMINATED` | **PASS** | P3_CONTAMINATED_PRESEAL_2026-04-14 |
| P0.3b `CRNEW_CARRYOVER_FORBIDDEN` in `prohibitions` | **PASS** | ops_state.json |
| P0.4 Docker services (postgres, redis) reachable | **PASS** | both `Up 8 days` |
| P0.4b `.env` with required keys | **PASS** | DATABASE_URL / DATABASE_URL_SYNC / CELERY_BROKER_URL / BINANCE creds |
| P0.5 `market_states` table exists, pre-baseline | **PASS** | 24 rows, latest 2026-04-06 22:04:56 (staleness 7d 21h, matches contamination window) |
| P0.6 Python can import task + helpers | **PASS** | `celery_app`, `collect_market_state`, `_to_native`, `_classify_failure` all imported |

**Advisory note (not blocking)**: `alembic current` raises `KeyError('027_ppf_baseline_freeze_columns')` — migration metadata issue, not a runtime blocker for B1. Schema already exists and is accessible.

---

## 3. Execution

| 필드 | 값 |
|---|---|
| `started_at` | 2026-04-14T19:39:09.783472+00:00 |
| `finished_at` | 2026-04-14T19:39:14.265417+00:00 |
| `duration` | ~4.5s |
| `invocation` | `collect_market_state.apply(args=['SOL/USDT']).get()` (synchronous, no broker) |
| `exception_raised` | 없음 |
| `celery_task_outcome` | SUCCESS |
| `task_return_value` | `{"exchange": "binance", "symbol": "SOL/USDT", "regime": "ranging", "price": 84.03}` |

### 3.1 Sub-collector log trace (from stdout)

```
04:39:12 funding_rate_not_available (SOL/USDT linear/inverse only) [expected]
04:39:12 market_data_collected exchange=binance has_funding=False has_oi=True ohlcv_bars=200
04:39:12 fear_greed_collected index=21 label='Extreme Fear'
04:39:13 on_chain_collected btc_dominance=57.39 hash_rate=1050.03 mempool_fee_fast=3
04:39:13 market_state_built exchange=binance price=84.03 regime=ranging
04:39:14 market_state_persisted exchange=binance price=84.03 regime=ranging symbol=SOL/USDT
```

`market_state_persisted` 로그 발생 = 성공적으로 `sess.commit()` 완료된 증거.

---

## 4. Row Count Delta (bounded verification)

| State | total_rows | sol_rows | sol_latest_snapshot |
|---|---|---|---|
| PRE | 24 | 15 | 2026-04-06 22:04:56.067444 |
| POST | 25 | 16 | 2026-04-14 19:39:13.901503 |
| **DELTA** | **+1** | **+1** | +8d 21h (freshness restored) |

`delta_total == 1 AND delta_sol == 1` → **bounded write 준수 (1행 정확)**.

---

## 5. Inserted Row Audit (field-level)

| 필드 | 값 | 타입 확인 |
|---|---|---|
| id | `1bf0ffd7-4cf5-4e89-915c-942631065ee6` | UUID |
| exchange | `binance` | str |
| symbol | `SOL/USDT` | str |
| price | 84.03 | Python float (native) |
| rsi_14 | 41.548635462049425 | float (native) |
| macd_line | 0.16355655170070804 | float (native) |
| macd_signal | 0.5162575105785556 | float (native) |
| bb_upper | 87.22281052215588 | float (native) |
| bb_lower | 84.2861894778441 | float (native) |
| atr_14 | 0.80335270606684 | float (native) |
| adx_14 | 31.001828807778246 | float (native) |
| **obv** (원래 leak 필드) | **14213.77200000002** | **float (native, numpy.float64 아님)** |
| sma_20 | 85.7545 | float (native) |
| ema_12 | 85.26360502727147 | float (native) |
| fear_greed_index | 21 | int |
| fear_greed_label | Extreme Fear | str |
| regime | ranging | str |
| snapshot_at | 2026-04-14 19:39:13.901503 | timestamp |

### NULL check (주요 필드)

| 필드 | NULL 여부 |
|---|---|
| price | 0 (not null) |
| obv | 0 (not null) |
| rsi_14 | 0 (not null) |
| atr_14 | 0 (not null) |
| bb_upper | 0 (not null) |
| fear_greed_index | 0 (not null) |

---

## 6. Verdict

### 6.1 B1 narrow verdict

**PASS** (code-path level):

- `_to_native()` 헬퍼가 numpy scalar → Python native 변환을 성공적으로 수행
- `_sync_engine` module-level bounded pool (CR-048 invariant) 작동
- `_classify_failure()` 트리거 없음 (no exception)
- `psycopg2 InvalidSchemaName("np")` 재발 **없음** (fixed code path 기준)
- 1행 정확 insert, bounded 준수
- 모든 indicator/sentiment/on_chain 필드 정상 변환·영속화

### 6.2 Constraint compliance

| 제약 | 준수 여부 |
|---|---|
| `blast_radius = single_row_market_states_only` | ✅ |
| `auto_retry = false` | ✅ (retry_count=0) |
| `market_states` 1행만 허용 | ✅ (delta=1) |
| 추가 테이블 write 금지 | ✅ (no other tables touched) |
| 2회 이상 재시도 금지 | ✅ (single invocation) |
| B2 자동 연장 금지 | ✅ (HOLD 선언 후 종료) |
| receipt 봉인 필수 | ✅ (본 문서) |

---

## 7. Operational Finding (out of B1 scope, follow-up required)

**B1 narrow verdict는 PASS이나, 병행 관찰에서 운영 공백이 발견됨.**

### 7.1 관찰 사실

B1 smoke는 **in-process `.apply()`**로 수행되어 브로커/워커를 거치지 않았다. 그러나 `logs/celery_worker.log`를 감사한 결과:

| 항목 | 값 |
|---|---|
| 로그 전체 `InvalidSchemaName` 발생 건수 | **33,048건** |
| 수집 시점 최초 감지 (receipt §2 발췌) | 31,600건 (2026-04-14 감지 당시) |
| 감지 이후 신규 발생 | +1,448건 |
| B1 smoke 종료 이후 신규 발생 (19:39:14~) | 최소 2건 이상 (19:39:22, 19:39:26, …) |
| 새 error 내 obv 값 포맷 | `np.float64(14093.20400000002)` (pre-fix 포맷) |

### 7.2 해석

백그라운드 Celery worker 프로세스가 **pre-fix 코드를 메모리에 유지**하고 있음. main merge(`b26a0dc`) 이후 **worker/beat 프로세스 재기동이 이루어지지 않았기 때문**으로 판단.

- 고친 코드: `main` 기준으로 이미 repo에 있음 (B1이 이를 직접 로드해 검증)
- 운영 중인 워커: 수집기 파일 변경을 반영하지 않은 장기 상주 프로세스

### 7.3 이 receipt가 주장하는 것과 주장하지 않는 것

- **주장함**: CR-NEW v3.1 deterministic fix는 **코드 경로 수준에서 유효**하다 (B1 실증).
- **주장하지 않음**: 운영 중인 Celery worker가 이미 복구되었다.
- 결론: **코드 레벨 복구 = 완료**, **운영 레벨 복구 = 미완**.

### 7.4 후속 작업 후보 (B1 범위 외)

| 후속 작업 | 성격 | 승인 필요 |
|---|---|---|
| Celery worker / beat 재기동 (stale 코드 언로드) | 운영 작업 (write 아님) | 별도 승인 권장 |
| 재기동 후 ~5분간 beat 스케줄 1주기 관찰 | 관찰 (no-write) | B2 범위에 근접 |
| ops_state.json에 worker restart evidence 반영 | local reflection | 별도 판정 |

**본 receipt는 worker restart를 수행하지 않는다.** 해당 작업은 별도 판정에 의해서만 수행된다.

---

## 8. Scope Boundary (명시)

이 receipt의 적용 범위는 **B1 Recovery Smoke 1회 실행의 증거화**에 한정된다. 다음은 명시적으로 범위 외:

- **NOT DONE**: B2 Observation Integrity Smoke
- **NOT DONE**: B3 새 14D P3 창 개시
- **NOT DONE**: Celery worker / beat 재기동
- **NOT DONE**: `ops_state.json` 재편집 (`writes_consumed` 증가 등)
- **NOT DONE**: `activation_gate` 상태 변경 (LOCKED 유지)
- **NOT DONE**: P3 window seal receipt §5 `recovery_smoke_result` (TBD) 채움 (B2/B3 완료 후 append-only linkage sync PR로 일괄 처리 권장)

---

## 9. Signatures

- **Executed / Sealed**: 2026-04-14 operator (A)
- **Change Control**: CR-NEW v3.1
- **Ledger Class**: VRL (영구보존)
- **Supersedes**: 없음 (신규)
- **Main basis commit**: `b26a0dc41f4ce13aca711ac66e9e1de0826102c9` (PR #101 squash)
- **Inserted row id**: `1bf0ffd7-4cf5-4e89-915c-942631065ee6`
- **Status**: **B1 PASS (narrow) + operational gap flagged** → HOLD
