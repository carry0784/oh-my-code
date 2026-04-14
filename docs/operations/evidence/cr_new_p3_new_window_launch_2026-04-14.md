# CR-NEW v3.1 Layer C — New 14D P3 Window Launch Evidence

**Doc ID**: cr_new_p3_new_window_launch_2026-04-14
**Doc Path (repo-relative)**: docs/operations/evidence/cr_new_p3_new_window_launch_2026-04-14.md
**Created At**: 2026-04-14/15 (UTC boundary)
**Signed By**: operator (A)
**approval_basis_doc**: CR-NEW v3.1 + user explicit Layer C execution GO
**approval_verdict**: APPROVED_A (docs-only, no write/state change)
**Ledger Class**: VRL (Validation Result Ledger, 영구보존)
**Related Docs**:
- `docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md` (contaminated window SSOT, PR #100 `fc4a91c`)
- `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` (PR #101 `b26a0dc`)
- `docs/operations/evidence/cr_new_p1_recovery_smoke_2026-04-14.md` (PR #102 `2e8f039`)
- `docs/operations/evidence/cr_new_worker_restart_recovery_2026-04-14.md` (PR #103 `c00fae9`)
- `docs/operations/evidence/cr_new_p2_observation_smoke_2026-04-14.md` (PR #104 `1f335b9`)

---

## 1. Scope (docs-only, 명시)

| 필드 | 값 |
|---|---|
| `operation_type` | **docs-only new-window declaration** |
| `blast_radius` | **`new_window_metadata_receipt_only`** |
| `code_change` | **없음** (main tree `1f335b9` 그대로) |
| `config_change` | **없음** |
| `schema_change` | **없음** |
| `ops_state_repo_edit` | **없음** (repo에서는 미편집 — local mirror reflection은 별도 operator 작업) |
| `activation_gate_change` | **없음** (LOCKED / `writes_consumed=0` 유지) |
| `bounded_write_consumed` | **0** |
| `P3_seal_receipt_§5_linkage_sync` | **미수행** (후행 append-only PR로 일괄 처리 권장) |
| `contaminated_window_receipt_edit` | **미수행** (immutable) |
| `Layer_A/B_receipt_edit` | **미수행** (immutable) |

---

## 2. Window Declaration

### 2.1 Window Identity

| 필드 | 값 |
|---|---|
| `window_id` | **`P3_POSTSEAL_2026-04-15`** |
| `window_kind` | P3 (14-day production observation window) |
| `baseline_source` | **post-recovery clean window** (post B1 + worker restart + B2 all PASS) |
| `supersedes_window_id` | `P3_CONTAMINATED_PRESEAL_2026-04-14` (SEALED_CONTAMINATED, carryover 금지) |
| `basis_main_sha` | **`1f335b9d5a257c87fdfee16b7e7c58a6f8ca935b`** (PR #104 squash) |

### 2.2 Timestamps

| 필드 | 값 (UTC) | 값 (KST) |
|---|---|---|
| `new_window_started_at` | **2026-04-14T21:24:18Z** | 2026-04-15T06:24:18+0900 |
| `new_window_baseline_at` | **2026-04-14T21:24:18Z** (동일, fresh baseline at window open) | 2026-04-15T06:24:18+0900 |
| `expected_close_at` | **2026-04-28T21:24:18Z** (started_at + 14D) | 2026-04-29T06:24:18+0900 |

**근거**: 
- `new_window_started_at`은 본 receipt 작성 시점의 UTC 시각으로 고정.
- `new_window_baseline_at`은 동일 시각 (fresh 14D window는 선언 시점부터 baseline 측정 시작).
- `expected_close_at`은 starts + 14D, 중도 오염 발생 시 별도 판정으로 변경 가능.

---

## 3. Boundary Declaration — Contaminated ↔ New

### 3.1 이전 창(오염)과의 경계

| 항목 | 값 |
|---|---|
| 이전 창 ID | `P3_CONTAMINATED_PRESEAL_2026-04-14` |
| 이전 창 상태 | `SEALED_CONTAMINATED` (PR #100 `fc4a91c` SSOT) |
| 이전 창 sealed_at | 2026-04-14T18:47Z |
| `carryover_ban` | 유지 (`reset_initial_state=true`, `exclude_from_baseline_thresholds=true`, `exclude_from_cumulative_stats=true`, `exclude_from_evidence_stats=true`) |
| 이전 창 allowed_meta_records | `["seal_receipt", "linkage_records"]` (그 외 기록 금지) |

### 3.2 새 창의 초기 상태 (carryover 차단)

| 항목 | 값 |
|---|---|
| **initial_state** | **reset** (이전 창 누적 통계 / threshold / evidence 일체 비계승) |
| baseline threshold 재계산 | 새 창 내부 관찰값으로만 |
| cumulative stats | 새 창 범위 내 자연 실행만 |
| evidence stats | 새 창 receipt 체인 내부만 |
| 이전 창 복제 금지 | `CRNEW_CARRYOVER_FORBIDDEN` prohibition 유지 (local mirror 반영, PR #101) |

### 3.3 경계 선언 (명문화)

본 시점(`2026-04-14T21:24:18Z` UTC) 이후 발생하는 모든 자연 관찰·실행은 **새 창 `P3_POSTSEAL_2026-04-15`의 맥락**에서만 해석된다. 이전 오염 창(`P3_CONTAMINATED_PRESEAL_2026-04-14`)의 어떠한 수치·판정·threshold도 새 창에 계승되지 않는다.

---

## 4. CR-046 SOL Stage B bar_count Reset Declaration

### 4.1 Reset 선언 (SSOT)

| 필드 | 이전 값 | 신규 값 (본 receipt SSOT) |
|---|---|---|
| `observation_track_id` | `CR-046 SOL Stage B` | (동일) |
| `status` | `ACTIVE` | `ACTIVE` (post-seal, 새 창 기준) |
| `bar_count` | `1/24` (pre-seal, 오염 창 기준) | **`0/24 (post-seal)`** |
| `baseline_at` | `2026-04-07T13:50:17Z` (오염 창 baseline) | **`2026-04-14T21:24:18Z`** (새 창 baseline) |
| `window_basis` | `P3_CONTAMINATED_PRESEAL_2026-04-14` | **`P3_POSTSEAL_2026-04-15`** |
| `invalidated_runs[pre-hotfix]` | 5 bars invalidated | (유지, 이전 창 잔류 기록) |
| `invalidated_runs[pre-seal-contamination]` | (신규) | **bars=1, reason=CRNEW_CARRYOVER_FORBIDDEN, invalidated_at=2026-04-14T21:24:18Z** |

### 4.2 Checkpoints (새 창 기준 재계산)

| checkpoint | 이전 창 기준 | **새 창 기준 (본 receipt SSOT)** |
|---|---|---|
| 6bar | `2026-04-07T19:50Z` | **`2026-04-15T03:24:18Z` UTC** (baseline + 6h) |
| 12bar | `2026-04-08T01:50Z` | **`2026-04-15T09:24:18Z` UTC** (baseline + 12h) |
| 24bar | `2026-04-08T13:50Z` | **`2026-04-15T21:24:18Z` UTC** (baseline + 24h) |

**주의**: 위 checkpoint는 본 receipt가 SSOT이며, `ops_state.json`의 `observation_tracks[CR-046 SOL Stage B]` 항목은 **local mirror**로서 operator가 별도 반영해야 한다 (PR #101 Y1 rule 적용). 본 repo PR에서는 `ops_state.json`을 편집하지 않는다.

### 4.3 Reset 반영 경로 (Y1 rule 준수)

| 경로 | 상태 | 비고 |
|---|---|---|
| **Tracked evidence receipt (본 문서)** | ✅ SSOT | 영구보존, 거버넌스 원본 |
| **Local mirror reflection (`ops_state.json`)** | ⏸ **별도 operator 작업** | gitignored, runtime tooling 편의 |
| repo PR 직접 편집 | ❌ 금지 | gitignored이므로 불가, Y1 rule에 따라 불허 |

---

## 5. Pre-Launch Invariants (재확인)

| 항목 | 값 (본 receipt 작성 시점) | 변경 여부 |
|---|---|---|
| `activation_gate.status` | LOCKED | 불변 |
| `activation_gate.mode` | GUARDED | 불변 |
| `activation_gate.allowed_symbols` | `["SOL/USDT"]` | 불변 |
| `activation_gate.write_budget` | 1 | 불변 |
| `activation_gate.writes_consumed` | **0** | 불변 |
| `contaminated_windows[0].status` | SEALED_CONTAMINATED | 불변 |
| `prohibitions` include `CRNEW_CARRYOVER_FORBIDDEN` | yes (local mirror) | 불변 |
| worker PID | 187248 | 불변 |
| beat PID | 184284 | 불변 |
| main SHA | `1f335b9` | 불변 |

---

## 6. Scope Constraints (명문화)

### 6.1 허용

- ✅ 새 14D P3 창 개시 (본 receipt에 선언)
- ✅ `new_window_started_at` 확정 (§2.2)
- ✅ `new_window_baseline_at` 확정 (§2.2)
- ✅ CR-046 SOL Stage B `bar_count` reset 선언 (§4.1)
- ✅ Layer C evidence receipt 작성 (본 문서)
- ✅ docs-only PR 생성

### 6.2 금지 (본 receipt에서 실제로 건드리지 않음)

- ❌ `ops_state.json` repo PR 편집 (gitignored, Y1 rule)
- ❌ `activation_gate` 상태 변경
- ❌ `writes_consumed` 변경
- ❌ bounded write 신규 소비
- ❌ 코드·설정·스키마 변경
- ❌ Layer A/B/기존 P3 seal receipt 본문 수정
- ❌ P3 seal receipt §5 `recovery_smoke_result` / `observation_smoke_result` / `new_window_started_at` linkage sync
- ❌ Testability PR / Trackedness Preflight docs PR
- ❌ 추가 PR 자율 생성 (본 receipt PR 제외)
- ❌ 자율적 후속 단계 전이

---

## 7. Verdict

### 7.1 최종 판정

**PASS**.

### 7.2 근거 (4개 이내)

1. **Layer A + Layer B 전부 main 봉인 완결** (`1f335b9`까지) — B3 전제조건 8개 전부 충족.
2. **새 창 metadata 필수 3요소 확정**: `window_id=P3_POSTSEAL_2026-04-15` / `new_window_started_at=2026-04-14T21:24:18Z` / `new_window_baseline_at=2026-04-14T21:24:18Z` / expected close = 2026-04-28T21:24:18Z.
3. **Contaminated ↔ new 경계 명문화**: carryover ban 유지, 이전 창 수치 비계승, initial_state reset 선언, CR-046 SOL Stage B `bar_count = 0/24 (post-seal)` 선언.
4. **Scope invariants 전부 보존**: `activation_gate` LOCKED / `writes_consumed=0` / `ops_state.json` repo 미편집 / Layer A/B receipt 불변 / linkage sync 미수행 / bounded write 미소비. docs-only 단일 파일 PR로 봉인.

---

## 8. Scope Boundary (명시, NOT DONE)

본 receipt의 적용 범위는 **Layer C 새 14D P3 창 개시 1회의 증거화**에 한정된다. 다음은 명시적으로 범위 외:

- **NOT DONE**: `ops_state.json` 재편집 (local mirror reflection은 operator 별도 작업)
- **NOT DONE**: `activation_gate` 상태 변경
- **NOT DONE**: P3 seal receipt §5 linkage sync (후행 append-only PR로 일괄 처리 권장)
- **NOT DONE**: Layer A/B receipt 본문 수정 (immutable)
- **NOT DONE**: Testability PR (`_to_native` / `_classify_failure` unit tests)
- **NOT DONE**: Trackedness Preflight rule 공식 운영 규칙 등재 docs PR
- **NOT DONE**: 새 창 6/12/24 bar checkpoint observation receipt (별도 판정 대상)
- **NOT DONE**: `activation_gate` unlock 또는 `write_budget` 신규 할당 (별도 CR)

---

## 9. Follow-up (후속 작업 후보, 모두 별도 승인 대상)

| 후속 작업 | 성격 | 승인 필요 |
|---|---|---|
| Local mirror (`ops_state.json`) 반영 — 새 창 entry / `bar_count` update | local runtime tooling | operator 별도 작업 (Y1 rule) |
| P3 seal receipt §5 linkage sync (B1/B2/new-window 필드 일괄 채움) | append-only docs PR | 별도 승인 |
| 새 창 6/12/24 bar checkpoint 관찰 receipt | 관찰 (no-write) | checkpoint 도달 시 별도 판정 |
| Testability PR (22 unit tests) | 코드 개선 | 별도 CR |
| Trackedness Preflight rule 공식화 | 거버넌스 문서 | 별도 docs PR |
| 14D 창 종료 후 window close receipt | 봉인 | 2026-04-28T21:24:18Z 이후 별도 판정 |

**본 receipt는 위 항목들을 수행하지 않는다.**

---

## 10. Declaration — HOLD after Layer C Launch

본 receipt는 다음을 **주장한다**:
- 새 14D P3 창 `P3_POSTSEAL_2026-04-15`이 `2026-04-14T21:24:18Z` UTC에 개시되었다.
- 새 창의 baseline은 동일 시각으로 확정되었다 (fresh baseline).
- CR-046 SOL Stage B `bar_count`는 `0/24 (post-seal)`로 reset되었음을 본 receipt SSOT로 선언한다.
- 오염 창과의 carryover 차단 원칙은 유지된다.

본 receipt는 다음을 **주장하지 않는다**:
- `ops_state.json` local mirror가 갱신되었다. (✗ — operator 별도 작업)
- `activation_gate`가 재구성되었다. (✗)
- 새 창의 관찰 결과 (bar_count 진행, threshold 재계산) 가 시작되었다. (✗ — 후속 receipt)
- §5 linkage sync가 수행되었다. (✗)

**Layer C 완료 후 자율적 후속 단계 전이는 금지된다.** HOLD 재진입.

---

## 11. Signatures

- **Sealed**: 2026-04-14 (KST 04-15) operator (A)
- **Change Control**: CR-NEW v3.1
- **Ledger Class**: VRL (영구보존)
- **Supersedes**: 없음 (신규, Layer C 개시 receipt)
- **Main basis commit**: `1f335b9` (PR #104 squash, Layer B 완결)
- **Window id**: `P3_POSTSEAL_2026-04-15`
- **Window started_at**: 2026-04-14T21:24:18Z UTC
- **Window baseline_at**: 2026-04-14T21:24:18Z UTC
- **Expected close**: 2026-04-28T21:24:18Z UTC
- **Final verdict**: **PASS**
- **Status**: **Layer C launched + docs-only seal complete + HOLD 재진입** — 자율 후속 전이 금지
