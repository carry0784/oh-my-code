# CR-NEW v3.1 P3 Structural Issue Resolved Declaration

**Doc ID**: cr_new_p3_structural_resolved_declaration_2026-04-15
**Doc Path (repo-relative)**: docs/operations/evidence/cr_new_p3_structural_resolved_declaration_2026-04-15.md
**Created At**: 2026-04-15 (KST)
**Signed By**: operator (A)
**approval_basis_doc**: GCF-STRUCTURAL-ISSUE-RESOLVED-DECLARATION-v1 (draft v2.1 FROZEN)
**approval_verdict**: APPROVED_A (scope-limited: REGISTRY+DATA, PROBE deferred)
**form_id**: GCF-STRUCTURAL-ISSUE-RESOLVED-DECLARATION-v1
**form_version_reference**: draft_v2.1_FROZEN
**Ledger Class**: VRL (Validation Result Ledger, 영구보존) — 문서 등록만, rhl/iwl/dql 편집 없음
**Receipt Filename Lock**: true (재논쟁 차단)
**Main SHA at issuance**: `1d0ad55`

**Related Docs**:
- `docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md` (SSOT, PR #100)
- `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` (PR #101)
- `docs/operations/evidence/cr_new_p1_recovery_smoke_2026-04-14.md` (PR #102)
- `docs/operations/evidence/cr_new_worker_restart_recovery_2026-04-14.md` (PR #103)
- `docs/operations/evidence/cr_new_p2_observation_smoke_2026-04-14.md` (PR #104)
- `docs/operations/evidence/cr_new_p3_new_window_launch_2026-04-14.md` (PR #105)

---

## 1. Declaration Scope

| 필드 | 값 |
|---|---|
| `resolved` | `REGISTRY_STRUCTURAL_ISSUE`, `DATA_STRUCTURAL_ISSUE` |
| `explicitly_deferred` | `PROBE_FLOWER_API_AUTH_REQUIRED` |
| `scope_fingerprint` | **REGISTRY+DATA_ONLY / PROBE_DEFERRED / EXECUTION_SCOPE_UNCHANGED** |
| `application_layer` | observation layer (runtime behavior unchanged) |
| `execution_authority_change` | **없음** (shadow/paper/live 권한 불변) |

본 선언은 **관측 계층(observation layer)**의 구조 이슈 해소를 선언하는 것이며, 운영 집행 권한(execution scope)의 변경을 포함하지 않는다.

---

## 2. Mandatory Dual Phrasing (English preserved verbatim)

- **Sentence A**: `REGISTRY/DATA structural issue resolved at observation layer.`
- **Sentence B**: `PROBE auth issue remains deferred and out of scope.`

두 문장은 본 receipt의 의미를 정의하는 **정규 문구(canonical phrasing)**이며, 영어 원문 그대로 보존된다. 주변 주석은 한국어로 작성하되, 위 두 문장은 수정·번역·요약되지 않는다.

---

## 3. Prerequisite Check Table (6/6 PASS)

| # | 조건 | 기대값 | 실측값 | 판정 |
|---|---|---|---|---|
| 1 | `streak_positive_verdict_len` | ≥ 3 | 3 (TRCC 3 consecutive 정상가동) | ✅ PASS |
| 2 | `registry_incident_recurrence` | 0 | 0 (PID drift 해소 후 재발 없음) | ✅ PASS |
| 3 | `data_stale_recurrence` | 0 | 0 (last_observation_age 정상화 후 재발 없음) | ✅ PASS |
| 4 | `writes_consumed_unchanged` | true | true (`activation_gate.writes_consumed=0` 유지) | ✅ PASS |
| 5 | `main_sha_unchanged` | true, value=`1d0ad55` | `1d0ad55` (본 receipt 발행 시점까지 불변) | ✅ PASS |
| 6 | `probe_deferred_explicit` | true | true (PROBE Flower auth 401 persistent, 별도 chain에 이관) | ✅ PASS |

### 3.1 Machine-readable YAML block

```yaml
prerequisite_check:
  streak_positive_verdict_len: 3
  registry_incident_recurrence: 0
  data_stale_recurrence: 0
  writes_consumed_unchanged: true
  main_sha_unchanged: true
  main_sha_value: "1d0ad55"
  probe_deferred_explicit: true
  overall: 6/6_PASS
```

---

## 4. Evidence Chain

### 4.1 REGISTRY 해소 증거

| 항목 | 이전 (drift 상태) | 현재 (정렬 완료) | 증거 |
|---|---|---|---|
| worker PID (ops_state registered) | 88008 | **187248** | ops_state.json `observation_tracks[0].worker_pid` |
| beat PID (ops_state registered) | 97588 | **184284** | ops_state.json `observation_tracks[0].beat_pid` |
| worker PID (OS alive) | 187248 | 187248 | `Get-CimInstance Win32_Process` |
| beat PID (OS alive) | 184284 | 184284 | `Get-CimInstance Win32_Process` |
| PID match | drift detected | **매칭 일치** | registry = alive |
| TRCC REGISTRY axis verdict | `PID_STALE_OR_UNKNOWN` (prior) | `OBSERVED_CELERY_MATCHES` (3 consecutive) | rhl.jsonl |

### 4.2 DATA 해소 증거

| 항목 | 이전 | 현재 | 증거 |
|---|---|---|---|
| last_observation_age (seconds) | 654,064 (stale) | 54~65 (fresh) | DATA axis telemetry |
| DATA axis verdict | `OBSERVATION_SOURCE_STALE` (prior) | `DB_OK` (3 consecutive) | rhl.jsonl |
| market_states row delta in P2 window | n/a | +4 (natural beat, bounded write 소비 0) | cr_new_p2_observation_smoke_2026-04-14.md §4.4 |

### 4.3 TRCC 3 consecutive 정상가동 streak

| Run | timestamp (UTC) | exit_code | verdict | REGISTRY | PROBE | DATA |
|---|---|---|---|---|---|---|
| 1 | 2026-04-14T23:50:13Z | 0 | 정상가동 | OBSERVED_CELERY_MATCHES | FLOWER_UI_OK_API_AUTH_REQUIRED (deferred) | DB_OK |
| 2 | 2026-04-15T00:01:44Z | 0 | 정상가동 | OBSERVED_CELERY_MATCHES | FLOWER_UI_OK_API_AUTH_REQUIRED (deferred) | DB_OK |
| 3 | 2026-04-15T00:21:32Z | 0 | 정상가동 | OBSERVED_CELERY_MATCHES | FLOWER_UI_OK_API_AUTH_REQUIRED (deferred) | DB_OK |

- Rate limit rule 준수: "하루 1~3회, 이상 징후 시 추가 허용" 범위 내.
- iwl.jsonl 추가 행 0 (정상가동이므로 skip 규칙 적용, DQL rate-limit write는 수행).

### 4.4 PROBE 지연 증거 (out of scope)

- PROBE axis verdict: `FLOWER_UI_OK_API_AUTH_REQUIRED` — 지속 (streak n=6 관측).
- 원인: Flower API BasicAuth 요구, 현재 credentials 미구성.
- **처리**: 본 receipt 범위에서 해소하지 않음. 별도 체인 `GCF-FLOWER-PROBE-CONFIG-REMEDIATION-v1`에 이관(명시적 deferral).
- 이유: PROBE는 observation telemetry 경로이며, execution authority에 영향 없음. 또한 REGISTRY/DATA 해소와 직교(orthogonal)하여 동일 receipt에서 묶을 경우 scope 혼탁 위험.

---

## 5. Positive-Streak Semantic Label (STRUCTURAL_STABILITY_LOCKED)

### 5.1 Label 정의

| 필드 | 값 |
|---|---|
| `name` | `STRUCTURAL_STABILITY_LOCKED` |
| `application_scope` | `docs_level_only` |
| `script_modification` | **PROHIBITED** (`plral_streak_check.py`, `health_check.py` 등 어떤 스크립트도 수정하지 않음) |
| `adoption_basis` | draft v2.1 `positive_streak_label` 블록 |

### 5.2 Uniform streak interpretation rule (mirror for positive)

- n=1: 단일 관측
- n=2: 원인 재확인
- **n≥3: 구조적 안정성 잠금 (STRUCTURAL_STABILITY_LOCKED)**

본 declaration 시점 REGISTRY+DATA 2축 모두 n=3 positive streak 달성 → 구조 이슈 해소 선언의 정량 근거 충족.

### 5.3 Label 적용 범위의 명시적 제한

- 본 label은 **문서(receipt) 계층에서만 선언적으로 사용**되며, 스크립트의 판정 로직·출력·threshold·문자열을 바꾸지 않는다.
- `plral_streak_check.py`는 현재 출력을 그대로 유지한다.
- 이후 스크립트 레벨 채택이 필요하면 **별도 CR + 별도 승인**으로만 착수한다.

---

## 6. Verdict

### 6.1 최종 판정

**APPROVED_A — STRUCTURAL ISSUE RESOLVED (REGISTRY + DATA, observation layer), PROBE DEFERRED.**

### 6.2 근거 요약 (4개 이내)

1. **6/6 prerequisite PASS**: streak=3 / registry_recurrence=0 / data_recurrence=0 / writes_consumed 불변 / main_sha 불변 / PROBE deferred 명시 — 전부 충족(§3).
2. **REGISTRY/DATA 2축 양의 streak n=3 달성**: PID 정렬 후 TRCC 3 consecutive 정상가동, uniform streak rule의 구조적 안정성 문턱 도달(§4.3, §5.2).
3. **PROBE 축 명시적 이관**: Flower auth 401은 observation telemetry 경로이며 execution authority와 직교, 동일 receipt scope에서 묶지 않고 별도 체인에 이관(§4.4).
4. **Runtime invariants 보존**: `activation_gate.status=LOCKED`, `writes_consumed=0`, `write_budget=1`, `contaminated_windows` 불변, PR/코드/설정/스키마 변경 없음(§8).

---

## 7. Scope Boundary (명시)

본 receipt의 적용 범위는 **REGISTRY + DATA 2축 구조 이슈의 observation-layer 해소 선언**에 한정된다. 다음은 명시적으로 범위 외이며, 본 발행에 포함되지 않는다:

- **NOT DONE**: PROBE (Flower API auth) 해소 — 별도 `GCF-FLOWER-PROBE-CONFIG-REMEDIATION-v1` 필수.
- **NOT DONE**: 본 receipt 파일을 포함한 commit/PR 생성 — 별도 `GCF-GENERIC-PR-SEAL-v1` 필수.
- **NOT DONE**: `ops_state.json` 편집 (activation_gate / observation_tracks / contaminated_windows / last_updated 전부 불변).
- **NOT DONE**: `plral_streak_check.py`, `health_check.py`, 그 외 어떤 스크립트·코드·설정·스키마 수정.
- **NOT DONE**: VRL 별도 operator note append (본 GO에서는 `vrl_append_in_this_go=EXCLUDED`; 옵션 단계로 지정된 `VRL_OPERATOR_NOTE_APPENDED`는 실행하지 않음).
- **NOT DONE**: execution authority 상향 (shadow → paper/live), CR-046 SOL Stage B `bar_count` 초기화, P3 6/12/24bar checkpoint receipt, testability PR, Trackedness Preflight rule 공식화 등.
- **NOT DONE**: B3 자율 전이, 새 14D P3 창 개시(이미 PR #105에서 별도로 처리), state_schema v3 / go_command_schema v2 / go_command_forms v2 승격.

---

## 8. Constraint Compliance

| 제약 | 준수 여부 | 근거 |
|---|---|---|
| `scope_fingerprint = REGISTRY+DATA_ONLY / PROBE_DEFERRED / EXECUTION_SCOPE_UNCHANGED` | ✅ | §1, §6.2, §10 |
| mandatory_dual_phrasing (English verbatim) | ✅ | §2 (Sentence A / Sentence B 원문 보존) |
| receipt_filename_locked | ✅ | 본 파일 경로가 locked path와 일치 |
| `pr_inclusion = EXCLUDED` | ✅ | 본 GO는 file write만 수행, commit/PR 없음 |
| `vrl_append_in_this_go = EXCLUDED` | ✅ | vrl.jsonl 무편집 |
| `activation_gate` 상태 변경 금지 | ✅ | LOCKED, writes_consumed=0, write_budget=1 불변 |
| `ops_state.json` 편집 금지 | ✅ | last_updated 포함 불변 |
| 코드/설정/스키마 변경 금지 | ✅ | main sha `1d0ad55` 불변 |
| 스크립트 수정 금지 (`script_modification = PROHIBITED`) | ✅ | `plral_streak_check.py` / `health_check.py` 무수정 |
| positive_streak_semantic_label `docs_level_only` 적용 | ✅ | §5.3 |
| CRNEW_CARRYOVER_FORBIDDEN | ✅ | `P3_CONTAMINATED_PRESEAL_2026-04-14` carryover_ban 유지 |
| Squash Merge Recovery Rule | ✅ | main basis `1d0ad55` 기준 |
| B3 자율 전이 금지 | ✅ | post_state = HOLD (§10) |
| CR-049 Phase 3 구현 금지 | ✅ | DESIGN_ONLY 유지 |
| ETH 운영 경로 금지 (CR-046) | ✅ | 해당 없음 |
| L3/L4 변경 금지 | ✅ | 해당 없음 |
| Gate 무단 개방 금지 | ✅ | 해당 없음 |

---

## 9. Follow-up (후속 작업 후보, 모두 별도 승인 대상)

| 후속 작업 | 성격 | 승인 필요 | 비고 |
|---|---|---|---|
| 본 receipt 파일 commit + PR | append-only docs | `GCF-GENERIC-PR-SEAL-v1` 별도 GO | squash merge → main |
| PROBE Flower API auth 해소 | config remediation | `GCF-FLOWER-PROBE-CONFIG-REMEDIATION-v1` 별도 GO | streak n=6 관측 해소 필요 |
| P3 6/12/24bar checkpoint receipt | observation progression | `GCF-CHECKPOINT-RECEIPT` 별도 GO | 창 기간 내 단계적 발행 |
| CR-046 SOL Stage B `bar_count` reset receipt (post-seal) | local reflection | 별도 판정 | post-P3 linkage sync 시점 조율 |
| P3 seal receipt §5 linkage sync | append-only linkage | B3 이후 별도 PR | recovery/observation/new-window 필드 |
| positive_streak_label 스크립트 레벨 채택 | 코드 변경 | 별도 CR | 본 GO에서는 PROHIBITED |
| Testability PR (22 unit tests, helper import-safe 분리) | 코드 개선 | 별도 CR | |
| Trackedness Preflight rule 공식 문서화 | governance docs | 별도 docs PR | |
| Execution authority 상향 (shadow → paper/live) | 집행 권한 변경 | 별도 CR 체인 | 본 receipt의 scope 외 |

**본 receipt는 위 항목들을 수행하지 않는다.**

---

## 10. Declaration — HOLD after Structural Resolved

본 receipt의 발행 결과는 다음을 **주장한다**:

- REGISTRY 및 DATA 축의 구조 이슈가 observation layer에서 **해소되었다**.
- 해소의 정량 근거는 TRCC 3 consecutive 정상가동 + 재발 0 + prerequisite 6/6 PASS이다.
- PROBE 축의 auth 이슈는 **명시적으로 범위 외(deferred)**이다.

본 receipt의 발행 결과는 다음을 **주장하지 않는다**:

- PROBE 축이 해소되었다. (✗)
- execution authority (shadow/paper/live 권한)가 변경되었다. (✗)
- `activation_gate` 상태가 변경되었다. (✗)
- `ops_state.json`이 갱신되었다. (✗)
- 스크립트나 코드가 수정되었다. (✗)
- commit/PR이 생성되었다. (✗)
- VRL operator note가 추가되었다. (✗)

**post_state = HOLD.** 다음 단계는 오직 별도 사용자 명시 GO 호출에 의해서만 착수된다.

### 10.1 Scope Fingerprint (재기재, 정규 요약)

```
scope_fingerprint: "REGISTRY+DATA_ONLY / PROBE_DEFERRED / EXECUTION_SCOPE_UNCHANGED"
```

---

## 11. Signatures

- **Sealed**: 2026-04-15 (KST) operator (A)
- **Change Control**: CR-NEW v3.1
- **Form**: GCF-STRUCTURAL-ISSUE-RESOLVED-DECLARATION-v1 (draft v2.1 FROZEN)
- **Ledger Class**: VRL (영구보존, 본 문서 등록)
- **Supersedes**: 없음 (신규)
- **Main basis commit**: `1d0ad55` (본 GO 시점까지 불변)
- **Prerequisite**: 6/6 PASS (§3)
- **Dual phrasing (English verbatim)**:
  - Sentence A: `REGISTRY/DATA structural issue resolved at observation layer.`
  - Sentence B: `PROBE auth issue remains deferred and out of scope.`
- **Scope fingerprint**: `REGISTRY+DATA_ONLY / PROBE_DEFERRED / EXECUTION_SCOPE_UNCHANGED`
- **Positive-Streak Semantic Label**: `STRUCTURAL_STABILITY_LOCKED` (docs_level_only; script_modification PROHIBITED)
- **Final verdict**: **APPROVED_A — STRUCTURAL ISSUE RESOLVED (REGISTRY + DATA), PROBE DEFERRED**
- **Status**: DECLARATION ISSUED → **HOLD**
