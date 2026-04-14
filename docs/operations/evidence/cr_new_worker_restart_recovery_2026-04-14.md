# CR-NEW v3.1 Worker Restart Recovery Evidence

**Doc ID**: cr_new_worker_restart_recovery_2026-04-14
**Doc Path (repo-relative)**: docs/operations/evidence/cr_new_worker_restart_recovery_2026-04-14.md
**Created At**: 2026-04-15 (operation date: 2026-04-14/15 UTC boundary)
**Signed By**: operator (A)
**approval_basis_doc**: CR-NEW v3.1 + user conditional GO (restart 3-gate framework)
**approval_verdict**: APPROVED_A (restart receipt scope only; B2 explicitly NOT authorized)
**Ledger Class**: VRL (Validation Result Ledger, 영구보존)
**Related Docs**:
- `docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md` (SSOT, PR #100 `fc4a91c`)
- `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` (PR #101 `b26a0dc`)
- `docs/operations/evidence/cr_new_p1_recovery_smoke_2026-04-14.md` (PR #102 `2e8f039`)

---

## 1. Premise (왜 별도 봉인이 필요한가)

PR #102 (`2e8f039`)에 봉인된 **B1 Recovery Smoke**는 **in-process `collect_market_state.apply(args=['SOL/USDT']).get()`** 으로 수행되어, **브로커·워커 프로세스를 거치지 않고** 수집기 코드 경로만 검증했다.

그 결과 B1 receipt §7 (Operational Finding)에 다음 운영 공백이 적시되었다:

- `logs/celery_worker.log` 내 `InvalidSchemaName` 누적 발생: **33,048건**
- B1 smoke 종료(19:39:14) **이후에도** 신규 발생 지속 (최소 +2건 이상)
- 신규 error 페이로드 포맷: `np.float64(…)` (pre-fix 포맷)

**해석**: 백그라운드 Celery worker/beat 프로세스가 main merge(`b26a0dc`, 그 이후 `2e8f039`) 이전에 기동되어 **pre-fix 코드를 메모리에 유지**하고 있었다. 즉:

- **코드 레벨 복구**: ✅ 완료 (B1 PASS)
- **운영 레벨 복구**: ❌ 당시 미완 (장기 상주 worker/beat가 신규 fix 코드를 로드하지 않음)

본 receipt는 **worker/beat 재기동을 통한 운영 레벨 복구의 증거**를 봉인한다.

---

## 2. Scope (blast radius)

| 필드 | 값 |
|---|---|
| `operation_type` | **operational (no-write; process lifecycle only)** |
| `blast_radius` | **`worker_beat_process_restart_only`** |
| `auto_retry` | N/A (process-level, not task-level) |
| `code_change` | **없음** (main tree unchanged, `2e8f039` 그대로) |
| `config_change` | **없음** |
| `bounded_write_consumed` | **0** (activation_gate 미소비 유지) |
| `ops_state_change` | **없음** (`writes_consumed`, `activation_gate` 등 변경 없음) |
| `schema_change` | **없음** |
| `seal_receipt` | 본 문서 |

---

## 3. Pre-Restart State (재기동 직전)

| 항목 | 값 | 증거 |
|---|---|---|
| worker PID | **88008** | `tasklist` / Celery log `spawn_main_pid=88008` |
| beat PID | **97588** | `tasklist` / beat startup log |
| worker start time | **2026-04-09T00:56:38Z** | process metadata |
| elapsed runtime | **6d 3h 53m** (재기동 시점 기준) | computed from start |
| loaded code era | **pre-fix** (before `fba493e`) | new errors format `np.float64(…)` |
| `logs/celery_worker.log` 내 `InvalidSchemaName` 누적 | **33,080건** | log grep (pre-restart snapshot) |
| main tree HEAD | `2e8f039` (PR #102 squash) | `git rev-parse origin/main` |
| activation_gate 상태 | `LOCKED`, `writes_consumed=0`, `write_budget=1` | `ops_state.json` |
| `market_states` row count | **25행** | `SELECT COUNT(*) FROM market_states` |
| latest snapshot | 2026-04-14 19:39:13.901503 (B1 insert) | `ORDER BY snapshot_at DESC LIMIT 1` |

**위험 해석**: 장기 상주 worker는 beat가 보내는 스케줄 task를 받을 때마다 **pre-fix 수집기 함수 객체를 실행**했고, 그 결과 postgres 대상 `INSERT` 시점에 `psycopg2.InvalidSchemaName("np")` 재발이 계속되고 있었다.

---

## 4. Restart Action

### 4.1 수행 방식

- **종료**: 기존 worker PID 88008, beat PID 97588 정상 종료
- **기동**: `celery -A workers.celery_app worker --pool=solo --loglevel=info`, `celery -A workers.celery_app beat --loglevel=info` (Windows Python 3.14 호환 `--pool=solo`)
- **코드 기준**: repo working tree = `2e8f039` (fixed 수집기 포함)
- **DB/broker**: 변경 없음 (동일 Postgres/Redis 접속)

### 4.2 재기동 시각

| 필드 | 값 |
|---|---|
| restart start | 2026-04-15T04:50:20Z (UTC 근사) |
| new worker PID online | **2026-04-15T04:50:26Z** |
| new beat PID online | **2026-04-15T04:50:26Z** (beat는 worker 직후 기동) |

### 4.3 Post-Restart State (재기동 직후)

| 항목 | 값 |
|---|---|
| new worker PID | **187248** |
| new beat PID | **184284** |
| loaded code era | **post-fix** (`2e8f039` tree, `_to_native` / `_classify_failure` 포함) |
| `Startup` 로그 | `celery@<host> ready.` / beat `Scheduler: Sending due task` 정상 |

---

## 5. Gate Verification (3-gate framework)

본 재기동은 사용자가 사전 승인한 **3-gate 검증 프레임워크**를 따른다. 3 gate 전부 PASS해야만 **B2 readiness**가 선언되며, 그 선언 자체는 B2 실행을 의미하지 않는다.

### 5.1 Gate G1 — PID refresh

| 기준 | 측정 | 판정 |
|---|---|---|
| old worker PID 종료 확인 | PID 88008 현재 미존재 (`tasklist` 기준) | ✅ |
| old beat PID 종료 확인 | PID 97588 현재 미존재 | ✅ |
| new worker PID 기동 확인 | **187248** alive, parent = shell, start 04:50:26Z | ✅ |
| new beat PID 기동 확인 | **184284** alive | ✅ |
| new worker가 `2e8f039` 코드 로드 | import path resolves to `workers/tasks/data_collection_tasks.py` with `_to_native` line 43, `_classify_failure` line 72 | ✅ |

**G1 PASS**.

### 5.2 Gate G2 — 신규 `InvalidSchemaName` 0건

| 기준 | 측정 |
|---|---|
| cutoff timestamp | **2026-04-15T04:50:30Z** (new worker ready 직후) |
| pre-cutoff 누적 | 33,080건 |
| post-cutoff 신규 | **0건** |
| 관찰 구간 | 04:50:30Z ~ 본 receipt 작성 시점 (≥ 수 분 경과, beat 스케줄 최소 1 tick 포함) |

**G2 PASS** — `np.float64(…)` 포맷 신규 에러 재발 없음.

### 5.3 Gate G3 — 자연 task 1회 이상 SUCCESS (broker-routed)

**In-process `.apply()`가 아닌, 실제 Celery 브로커를 경유한 자연 실행**이 SUCCESS해야 한다.

| task ID | symbol/context | duration | 결과 | 증거 로그 |
|---|---|---|---|---|
| `aed69fdc-5d5f-464d-868f-a779b4d60180` | `collect_market_state` (beat 자연 schedule) | **2.88s** | **SUCCESS** (BTC price=74137) | worker log `Task collect_market_state[aed69fdc-…] succeeded in 2.88s` |
| `5307623c-****-****-****-************` | `collect_market_state` | **2.86s** | **SUCCESS** | worker log `Task collect_market_state[5307623c-…] succeeded in 2.86s` |

**G3 PASS** — broker-routed 자연 실행이 fix 코드 경로에서 정상 통과.

### 5.4 Summary

| Gate | 내용 | 판정 |
|---|---|---|
| G1 | PID refresh (worker + beat) | ✅ PASS |
| G2 | 신규 `InvalidSchemaName` 0건 | ✅ PASS |
| G3 | 자연 task 1회 이상 SUCCESS | ✅ PASS |

**ALL 3 GATES PASS**.

---

## 6. Natural Write Confirmation (비강제, 관찰만)

B1에서 사용한 `activation_gate.write_budget`은 **소비되지 않았다** (`writes_consumed` 유지). 따라서 아래 2건의 자연 write는 **bounded write 예산과 무관한 beat schedule natural path**이다. 이는 정상 운영 재개의 신호이며, ops_state.json 재편집 없이 단순 관찰로만 기록한다.

| 상태 | total_rows | 증거 |
|---|---|---|
| PRE (restart 직전) | **25행** | B1 insert 포함, latest 2026-04-14 19:39:13.901503 |
| POST (restart 후 관찰) | **27행** | post-restart 2건 자연 insert |
| DELTA | **+2** | beat schedule 자연 실행 결과 |
| 최신 snapshot | **2026-04-14 19:50:40.955706** | `ORDER BY snapshot_at DESC LIMIT 1` |

**주의**: 이 +2 delta는 `activation_gate.write_budget`과 무관하며, 본 receipt는 `ops_state.json` 편집 없이 **관찰 사실만** 기록한다. ops_state.json 상태 변경은 별도 판정에 의해서만 수행된다.

---

## 7. Verdict

### 7.1 운영 레벨 복구

**PASS** — worker/beat 프로세스가 fixed 코드(`2e8f039`)를 로드하고, 신규 `InvalidSchemaName` 재발 없이 자연 task를 정상 수행함이 증명되었다.

### 7.2 복구 완결성 매트릭스

| 층위 | 상태 | 증거 |
|---|---|---|
| **코드 레벨 복구** | ✅ 완료 | PR #99 (`fba493e`) + PR #102 B1 receipt (`2e8f039`) |
| **거버넌스 봉인 (SSOT)** | ✅ 완료 | PR #100 P3 seal receipt (`fc4a91c`) |
| **거버넌스 봉인 (local mirror)** | ✅ 완료 | PR #101 Change-3 local reflection (`b26a0dc`) |
| **코드 경로 검증 (in-process)** | ✅ 완료 | PR #102 B1 Recovery Smoke (`2e8f039`) |
| **운영 레벨 복구 (worker restart)** | ✅ 완료 | **본 receipt (3 gates PASS)** |

### 7.3 Constraint compliance

| 제약 | 준수 여부 |
|---|---|
| `blast_radius = worker_beat_process_restart_only` | ✅ |
| code 변경 없음 | ✅ (main tree `2e8f039` 그대로) |
| config 변경 없음 | ✅ |
| `ops_state.json` 편집 없음 | ✅ |
| `activation_gate` 상태 변경 없음 | ✅ (LOCKED / writes_consumed 유지) |
| bounded write 소비 없음 | ✅ |
| schema 변경 없음 | ✅ |
| B2 자동 연장 금지 | ✅ (본 receipt 종료 후 HOLD) |
| receipt 봉인 필수 | ✅ (본 문서) |

---

## 8. B2 Readiness — Declared, NOT Authorized

### 8.1 Readiness 조건 충족

다음 3 조건이 모두 충족되었다:

1. ✅ B1 코드 경로 검증 PASS (PR #102)
2. ✅ worker/beat 재기동으로 운영 코드 새로고침 (G1)
3. ✅ 신규 `InvalidSchemaName` 재발 없음 (G2) + 자연 task 성공 (G3)

이는 **B2 Observation Integrity Smoke의 필요조건**이다.

### 8.2 충분조건이 아님 — B2 실행 금지 유지

- 본 receipt는 **B2 readiness를 선언**하는 것이지, **B2 execution을 승인하는 것이 아니다**.
- B2는 **별도 사용자 승인**에 의해서만 착수된다.
- B2 자율 착수는 금지된다.

### 8.3 이 receipt가 주장하는 것과 주장하지 않는 것

- **주장함**:
  - 운영 Celery worker/beat가 fixed 코드를 새로 로드했다.
  - 재기동 후 신규 `InvalidSchemaName` 재발이 관찰되지 않는다.
  - broker-routed 자연 task가 fix 코드 경로에서 SUCCESS한다.
- **주장하지 않음**:
  - B2 실행이 승인되었다. (✗)
  - 새 14D P3 창이 개시되었다. (✗)
  - `activation_gate`의 상태가 변경되었다. (✗)
  - `ops_state.json`이 갱신되었다. (✗)

---

## 9. Scope Boundary (명시)

본 receipt의 적용 범위는 **worker/beat process restart 1회 수행의 증거화**에 한정된다. 다음은 명시적으로 범위 외:

- **NOT DONE**: B2 Observation Integrity Smoke
- **NOT DONE**: B3 새 14D P3 창 개시
- **NOT DONE**: `ops_state.json` 재편집 (`writes_consumed`, `activation_gate`, `contaminated_windows` 등)
- **NOT DONE**: `activation_gate` 상태 변경 (LOCKED 유지)
- **NOT DONE**: P3 window seal receipt §5 `recovery_smoke_result` / `observation_smoke_result` / `new_window_started_at` 필드 채움 (deferred to append-only linkage sync PR, B2/B3 완료 이후 일괄 처리 권장)
- **NOT DONE**: restart 후 24h 관찰 (본 receipt는 즉시 수 분간 관찰에 근거)
- **NOT DONE**: Trackedness Preflight rule의 공식 운영 규칙 등재 (별도 docs PR 권장)

---

## 10. Follow-up (후속 작업 후보, 모두 별도 승인 대상)

| 후속 작업 | 성격 | 승인 필요 |
|---|---|---|
| B2 Observation Integrity Smoke | 관찰 (no new bounded write) | **별도 사용자 승인 필수** |
| B3 새 14D P3 창 개시 | 거버넌스 결정 | **별도 PR + 별도 승인 필수** |
| P3 seal receipt §5 linkage sync | append-only linkage 갱신 | B2/B3 이후 별도 PR |
| Testability PR (22 unit tests for `_to_native` / `_classify_failure`, import-safe helper 추출) | 코드 개선 | 별도 CR |
| Trackedness Preflight rule 공식화 | 거버넌스 문서 | 별도 docs PR |

**본 receipt는 위 항목들을 수행하지 않는다.** 각 항목은 별도 판정에 의해서만 수행된다.

---

## 11. Signatures

- **Sealed**: 2026-04-15 operator (A)
- **Change Control**: CR-NEW v3.1
- **Ledger Class**: VRL (영구보존)
- **Supersedes**: 없음 (신규)
- **Main basis commit**: `2e8f039` (PR #102 squash)
- **Restart operation timestamp**: 2026-04-15T04:50:26Z (new worker PID online)
- **Old PIDs**: worker 88008 / beat 97588 (elapsed 6d 3h 53m)
- **New PIDs**: worker 187248 / beat 184284
- **Gates**: G1 ✅ / G2 ✅ / G3 ✅ (ALL PASS)
- **Status**: **Operational recovery PASS + B2 readiness declared + B2 execution NOT authorized** → HOLD
