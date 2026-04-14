# CR-NEW v3.1 P2 Observation Integrity Smoke Evidence

**Doc ID**: cr_new_p2_observation_smoke_2026-04-14
**Doc Path (repo-relative)**: docs/operations/evidence/cr_new_p2_observation_smoke_2026-04-14.md
**Created At**: 2026-04-14/15 (UTC boundary)
**Signed By**: operator (A)
**approval_basis_doc**: CR-NEW v3.1 + user explicit B2 GO (observation-only)
**approval_verdict**: APPROVED_A (B2 observation-only, auto-transition to B3 FORBIDDEN)
**Ledger Class**: VRL (Validation Result Ledger, 영구보존)
**Related Docs**:
- `docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md` (SSOT, PR #100 `fc4a91c`)
- `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` (PR #101 `b26a0dc`)
- `docs/operations/evidence/cr_new_p1_recovery_smoke_2026-04-14.md` (PR #102 `2e8f039`)
- `docs/operations/evidence/cr_new_worker_restart_recovery_2026-04-14.md` (PR #103 `c00fae9`)

---

## 1. Scope (observation-only, 명시)

| 필드 | 값 |
|---|---|
| `operation_type` | **observation-only** (no forced invocation, no new bounded write) |
| `blast_radius` | **`natural_beat_schedule_observation_only`** |
| `allowed_source` | natural Celery beat schedule만 허용 |
| `forbidden_source` | `.apply()`, `.apply_async()`, 수동 호출 전면 금지 |
| `code_change` | **없음** (main tree `c00fae9` 그대로) |
| `config_change` | **없음** |
| `schema_change` | **없음** |
| `ops_state_change` | **없음** |
| `bounded_write_consumed` | **0** (`activation_gate.writes_consumed` 유지) |
| `B3_auto_transition` | **금지** (본 receipt 종료 후 HOLD) |

---

## 2. Observation Window

| 필드 | 값 |
|---|---|
| t0 (window start, UTC) | **2026-04-14T20:40:25Z** |
| t0 (KST) | 2026-04-15T05:40:25+0900 |
| t1 (window close, UTC) | **2026-04-14T20:52:29Z** |
| t1 (KST) | 2026-04-15T05:52:29+0900 |
| elapsed | ~12m 04s |
| termination rule | 자연 실행 **3회** 또는 **2시간** 중 먼저 도달 |
| termination reason | **3회 기준 먼저 도달** (실제 4회 관찰, 12분 경과 시점) |
| main SHA during window | `c00fae9aa6a8e0b6393175e74637f09c2661a69d` (PR #103 squash) |
| worker PID throughout window | 187248 (변경 없음) |
| beat PID throughout window | 184284 (변경 없음) |

---

## 3. t0 Baseline

| 필드 | 값 |
|---|---|
| `market_states` total | **47행** |
| 가장 최근 snapshot | 2026-04-14 20:40:40.863947 UTC (t0 직전 자연 insert) |
| `InvalidSchemaName` 누적 | **33,088건** (전부 pre-restart, KST ≤ 04:49:59) |
| post-restart natural SUCCESS (context only, window 외) | 22회 |
| `activation_gate.status` | LOCKED |
| `activation_gate.write_budget` | 1 |
| `activation_gate.writes_consumed` | **0** |
| `ops_state.last_updated` | `2026-04-14T18:57Z` (PR #101 반영 시점 유지, 이후 미편집) |

---

## 4. In-Window Measurements (t0 → t1)

### 4.1 Natural task SUCCESS trace (broker-routed, beat schedule)

| # | task_id | received (KST) | succeeded (KST) | duration |
|---|---|---|---|---|
| 1 | `0a65308e-30cd-4541-9f1e-f6891ec356fa` | 2026-04-15T05:45:35.408+0900 | 2026-04-15T05:45:38 | 3.5s |
| 2 | `2c41ad3c-ff9f-45a3-85a9-17c7c7fbc1dc` | 2026-04-15T05:45:38.941+0900 | 2026-04-15T05:45:41 | 2.8s |
| 3 | `f94b0f7b-391d-42f1-8ad5-b183adaa1548` | 2026-04-15T05:50:36.161+0900 | 2026-04-15T05:50:39 | 3.1s |
| 4 | `4329fb76-cfdf-4c81-8bfa-2771387f232b` | 2026-04-15T05:50:39.273+0900 | 2026-04-15T05:50:42 | 2.8s |

- 관찰 패턴: beat scheduler가 **5분 간격(05:45, 05:50)**으로 2 task 묶음 발사 (symbol pair)
- 평균 task duration: 3.05s
- 전부 **SUCCESS** (FAILURE / RETRY / REVOKED 로그 없음)
- 전부 **broker-routed** (log entry `Task … received` 존재 — in-process `.apply()` 경로가 아님)

### 4.2 Error log delta

| 지표 | t0 값 | t1 값 | delta |
|---|---|---|---|
| `InvalidSchemaName` 누적 | 33,088 | 33,088 | **0** |
| 윈도우 내 신규 `InvalidSchemaName` | N/A | **0** | ✓ |
| 윈도우 내 `np.float64(...)` 포맷 재발 | N/A | **0** | ✓ |

### 4.3 Forced invocation audit

| 탐색 키워드 | 발견 |
|---|---|
| `.apply()` (in-process) | **0** |
| `apply_async` (manual) | **0** |
| `manual_*` / `direct_*` invocation marker | **0** |
| 그 외 operator-triggered 호출 흔적 | **0** |

### 4.4 Database row-count delta (natural only)

| 상태 | total_rows | 증거 |
|---|---|---|
| t0 | 47 | `SELECT COUNT(*) FROM market_states` |
| t1 | **51** | 동일 쿼리 |
| delta | **+4** | 4건 모두 natural beat schedule에 의한 자연 insert |
| 최신 snapshot | 2026-04-14 20:50:41.862671 UTC | `ORDER BY snapshot_at DESC LIMIT 1` |

**해석**: +4 delta는 §4.1의 natural SUCCESS 4회와 정합. bounded write 예산 소비는 0 유지.

### 4.5 Runtime state invariants (unchanged throughout window)

| 항목 | 값 | 변경 여부 |
|---|---|---|
| `activation_gate.status` | LOCKED | 불변 |
| `activation_gate.write_budget` | 1 | 불변 |
| `activation_gate.writes_consumed` | 0 | 불변 |
| `ops_state.last_updated` | 2026-04-14T18:57Z | 불변 (미편집) |
| worker PID | 187248 | 불변 |
| beat PID | 184284 | 불변 |

---

## 5. Success Criteria Match Matrix

| 기준 | 목표 | 측정 | 판정 |
|---|---|---|---|
| 신규 `InvalidSchemaName` 0건 | = 0 | 0 | ✅ PASS |
| natural task SUCCESS ≥ 3회 | ≥ 3 | 4 | ✅ PASS |
| bounded write 신규 소비 0 | = 0 | 0 | ✅ PASS |
| 강제 호출 0건 | = 0 | 0 | ✅ PASS |

**4/4 PASS.**

---

## 6. Failure Criteria Match Matrix (negative check)

| 기준 | 발생 여부 |
|---|---|
| 오류 재발 (`InvalidSchemaName` 신규 / `np.float64` 포맷 재등장) | ❌ 없음 |
| 강제 호출 흔적 (`.apply()`, `apply_async` 수동, manual 호출) | ❌ 없음 |
| runtime state 편집 (`ops_state.json` 갱신 / `activation_gate` 변경) | ❌ 없음 |
| B3 scope bleed (14D P3 창 개시 / baseline 확정) | ❌ 없음 |

**0/4 FAIL trigger.**

---

## 7. Verdict

### 7.1 최종 판정

**PASS**.

### 7.2 근거 (4개 이내)

1. **성공 기준 4/4 전부 충족**: 신규 `InvalidSchemaName` 0건 / natural SUCCESS 4회 / bounded write 소비 0 / 강제 호출 0건.
2. **실패 기준 0/4 전부 미발생**: 오류 재발·강제 호출·runtime state 편집·B3 scope bleed 모두 없음.
3. **Runtime invariants 전부 보존**: `activation_gate` LOCKED / `writes_consumed=0` / `ops_state.last_updated` 미편집 / worker·beat PID 불변.
4. **Broker-routed 자연 실행 경로 정상**: 4건 전부 `Task … received` → `succeeded` 로그 쌍으로 확인, duration 2.8~3.5s 범위로 일관. main tree `c00fae9` (fixed 수집기) 경로가 운영 실행에서 deterministic하게 통과.

---

## 8. Constraint Compliance

| 제약 | 준수 여부 |
|---|---|
| `blast_radius = natural_beat_schedule_observation_only` | ✅ |
| 강제 invocation 금지 (`.apply()`, manual) | ✅ (§4.3) |
| `activation_gate` 상태 변경 금지 | ✅ (§4.5) |
| `writes_consumed` 증가 금지 | ✅ (§4.5) |
| `ops_state.json` 편집 금지 | ✅ (§4.5, `last_updated` 불변) |
| 코드/설정/스키마 변경 금지 | ✅ (main tree `c00fae9` 유지) |
| P3 seal receipt §5 linkage sync 금지 | ✅ (본 receipt에서 수행하지 않음) |
| 추가 PR 생성 금지 (본 receipt PR 제외) | ✅ |
| B3 자율 전이 금지 | ✅ (본 receipt 종료 후 HOLD 선언) |
| receipt 봉인 필수 | ✅ (본 문서) |

---

## 9. Scope Boundary (명시)

본 receipt의 적용 범위는 **B2 Observation Integrity Smoke 1회 실행의 증거화**에 한정된다. 다음은 명시적으로 범위 외:

- **NOT DONE**: B3 새 14D P3 창 개시 (별도 PR + 별도 승인 필수)
- **NOT DONE**: CR-046 SOL Stage B `bar_count: "0/24 (post-seal)"` 초기화 (별도 PR)
- **NOT DONE**: `ops_state.json` 재편집 (`activation_gate` / `writes_consumed` / `contaminated_windows` 전부 불변)
- **NOT DONE**: P3 seal receipt §5 `recovery_smoke_result` / `observation_smoke_result` / `new_window_started_at` 필드 채움 (deferred to append-only linkage sync PR, B3 완료 이후 일괄 처리 권장)
- **NOT DONE**: Testability PR (22 unit tests, helper import-safe 분리, ADX pollution isolation)
- **NOT DONE**: Trackedness Preflight rule 공식화 docs PR

---

## 10. Declaration — HOLD after B2

B2 PASS 결과는 다음을 **주장한다**:
- 복구 후 운영 관찰 무결성이 확인되었다 (오류 재발 없음, 자연 실행 성공, runtime invariants 보존).
- B3 진입의 **필요조건**이 추가로 충족되었다.

B2 PASS 결과는 다음을 **주장하지 않는다**:
- B3 실행이 승인되었다. (✗)
- 새 14D P3 창이 개시되었다. (✗)
- `activation_gate` 상태가 변경되었다. (✗)
- ops_state.json이 갱신되었다. (✗)

**B3 자율 전이는 금지된다.** B3는 별도 사용자 승인에 의해서만 착수된다.

---

## 11. Follow-up (후속 작업 후보, 모두 별도 승인 대상)

| 후속 작업 | 성격 | 승인 필요 |
|---|---|---|
| B3 새 14D P3 창 개시 | 거버넌스 결정 | **별도 PR + 별도 사용자 승인** |
| P3 seal receipt §5 linkage sync (recovery/observation/new-window 필드) | append-only linkage 갱신 | B3 이후 별도 PR |
| CR-046 SOL Stage B `bar_count` 초기화 (post-seal) | local reflection or evidence | 별도 판정 |
| Testability PR (`_to_native` / `_classify_failure` 유닛 테스트) | 코드 개선 | 별도 CR |
| Trackedness Preflight rule 공식 문서화 | 거버넌스 문서 | 별도 docs PR |

**본 receipt는 위 항목들을 수행하지 않는다.**

---

## 12. Signatures

- **Sealed**: 2026-04-14 (KST 04-15) operator (A)
- **Change Control**: CR-NEW v3.1
- **Ledger Class**: VRL (영구보존)
- **Supersedes**: 없음 (신규)
- **Main basis commit**: `c00fae9` (PR #103 squash)
- **Window**: 2026-04-14T20:40:25Z → 2026-04-14T20:52:29Z UTC (~12m 04s)
- **Natural SUCCESS count**: 4 / 3 (목표) — 조기 충족 (2시간 한도 도달 전)
- **Final verdict**: **PASS**
- **Status**: **B2 PASS + B3 readiness declared + B3 execution NOT authorized** → HOLD
