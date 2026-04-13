# SOL S-1 V-3R1 — Chain B Execution-Mode Static Analysis (SEALED)

**document_state:** SEALED
**review_status:** ACCEPTED_BY_USER_AT_CHAIN_B_STEP_2
**receipt_class:** v3r1_chain_b_opening_static_analysis
**chain_id:** chain_b_execution_mode_root_cause
**parent_chain:** SOL S-1 root-cause chain (NOT CLOSED BY THIS SEAL)
**sibling_chain:** corrective_sub_chain (CLOSED/FAIL/NO_V4_UNLOCK at step 11 SEAL-1)
**draft_created_at:** 2026-04-10
**draft_step:** chain_b_step_1 (opening analysis DRAFT, superseded by SEAL-1 at step 2)
**sealed_at:** 2026-04-10
**sealed_by:** user_accept_chain_b_step2_governance_gap_finding_seal_2026_04_10
**seal_number:** SEAL-1
**seal_step:** chain_b_step_2
**pre_seal_draft_hash:** `ac792ab36c63d9594dcc3d679eeb5af2e37d812afb6682b5b6746bbc211e5fbc`
**auto_advance:** forbidden
**analysis_mode:** read_only_static_analysis
**root_cause_finding_binding_active:** true (governance gap finding now legally effective — SEAL-1 activated at chain B step 2)
**root_cause_finding_class:** governance_gap (primary); code_defect (rejected)
**root_cause_finding_scope:** chain_b_only (does NOT extend to baseline validity, strategy pass/fail, or parent chain closure)
**frozen_script_mutation_by_this_seal:** false
**additional_run_invocation_by_this_seal:** false
**SOL_S1_V3_RUN_AUTHORIZED_state:** NOT SET (unchanged by this SEAL)
**SOL_S1_V3_EXECUTION_MODE_state:** NOT SET (unchanged by this SEAL)
**baseline_mutation_by_this_seal:** false
**count_contract_mutation_by_this_seal:** false
**chain_c_auto_start_by_this_seal:** false
**parent_chain_extension_by_this_seal:** false
**chain_a_reopen_by_this_seal:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_EXECUTION_RESUMPTION:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_V4_UNLOCK:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_ATTEMPT_2:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_ADDITIONAL_RUN:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_CHAIN_C_AUTO_START:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_PARENT_CHAIN_EXTENSION:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_CORRECTIVE_CHAIN_REOPEN:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_CODE_MUTATION_AUTHORITY:** false
**SEAL_OF_THIS_DOCUMENT_GRANTS_GOVERNANCE_REMEDIATION_AUTO_START:** false
**SEAL_OF_THIS_DOCUMENT_ACTIVATES_ROOT_CAUSE_FINDING:** true (governance_gap finding now binding)

---

## §0 Governance Scope Declaration (DRAFT → SEALED, post chain B step 2)

본 문서는 chain B (execution_mode root-cause static analysis) 의 **opening SEAL-1** 이다. chain B step 1 에서 DRAFT-1 로 작성되고, chain B step 2 의 user SEAL instruction 으로 발효되었다:

> "chain B step 1 DRAFT를 ACCEPT한다.
>  `docs/operations/evidence/sol_s1_v3r1_chain_b_execution_mode_analysis_draft.md` 를 SEALED로 전환하라.
>  본 SEAL의 효력은 `execution_mode=ambiguous` 의 1차 근본 원인을 governance gap으로 고정하는 것까지만 제한한다.
>  frozen 스크립트 수정, 추가 `--run` 호출, `SOL_S1_V3_RUN_AUTHORIZED` 및 `SOL_S1_V3_EXECUTION_MODE` 설정,
>  baseline 값 수정, chain C 자동 개시, 부모 chain 확장은 모두 금지한다."

본 SEAL 은 chain B step 1 에 작성된 DRAFT-1 (pre_seal_draft_hash=`ac792ab36c63d9594dcc3d679eeb5af2e37d812afb6682b5b6746bbc211e5fbc`) 의 내용을 그대로 상속하되, "가설 (hypothesis)" / "후보 (candidate)" 용어를 "binding finding" 으로 전환한다.

### 이 SEAL 이 하는 것
- `scripts/sol_s1_v3_shadow_run.py` (frozen, sha256=`94110d24…c3f4a`) 내부 `determine_execution_mode` / `EXECUTION_MODE_SOURCE_INFERRED` / `EXECUTION_MODE_AMBIGUOUS` 관련 코드 경로의 read-only 정적 분석 결과를 **봉인 기록** 으로 고정한다.
- step 8 run 의 `execution_mode=ambiguous` + `source=inferred_from_runtime` 반환 경로를 line-level trace 로 **영구 기록** 한다.
- 1차 근본 원인 (primary root cause) 을 **`governance_gap` 으로 고정** 한다. 코드 결함 후보는 **기각 상태로 봉인** 된다 (§5.4 table row a).
- 12 개 prior artifact + 본 chain B receipt (SEAL-1) = 13 artifact 의 post-SEAL hash 를 §8 에 고정한다.
- root_cause_finding 의 `binding_active = true` 상태를 활성화한다 (`SEAL_OF_THIS_DOCUMENT_ACTIVATES_ROOT_CAUSE_FINDING=true`).
- chain B 의 step_2 단계 (이 SEAL 자체) 를 lifecycle 에 기록한다.

### 이 SEAL 이 하지 않는 것 (step 2 user instruction 의 6 forbidden axes + 보조 금지)
- **frozen 스크립트 `sol_s1_v3_shadow_run.py` 를 수정하지 않는다** (`frozen_script_mutation_by_this_seal=false`)
- **추가 `--run` 호출을 하지 않는다** (`additional_run_invocation_by_this_seal=false`)
- **`SOL_S1_V3_RUN_AUTHORIZED` 를 설정하지 않는다** (env var 계속 NOT SET)
- **`SOL_S1_V3_EXECUTION_MODE` 를 설정하지 않는다** (env var 계속 NOT SET — 단순 분석이지 재-run 을 위한 환경 준비 아님)
- **baseline (64.3 / 35.7 / 70.9) 값을 수정하지 않는다**
- **chain C (baseline re-verification) 를 자동 개시하지 않는다** (`chain_c_auto_start_by_this_seal=false`)
- **부모 chain (SOL S-1 root-cause chain) 을 확장하지 않는다** (`parent_chain_extension_by_this_seal=false`)
- **step 11 SEAL-1 으로 CLOSED 된 corrective sub-chain (chain A) 을 재오픈하지 않는다** (`chain_a_reopen_by_this_seal=false`)
- **step 9 SEAL-1 의 FAIL (CORRECTIVE_RED_STOP) 판정을 수정하지 않는다** (locked inherit 유지)
- **count contract 2종 (28/20) 을 변경하지 않는다**
- **13 개 artifact 중 본 chain B receipt 외 12 개를 수정하지 않는다**
- **auto_advance 를 허용하지 않는다** (forbidden 유지)
- **strategy 소스 (`strategies/*.py`) / 기타 production 코드 를 수정하지 않는다**
- **governance-layer remediation (run GO 템플릿 수정 등) 을 자동 개시하지 않는다** — 이것은 별도 chain (governance remediation proposal chain) 의 영역이며, 본 SEAL 은 해당 체인 개시를 권고만 기록할 뿐 자동 트리거 없음
- **전략(SMC+WaveTrend) 자체의 성패를 선언하지 않는다** — 본 SEAL 은 execution_mode 경로의 root cause 만 고정한다

---

## §1 Chain B Lifecycle Context

| chain | status | 비고 |
|---|---|---|
| SOL S-1 root-cause chain (parent) | NOT CLOSED | 본 SEAL 은 parent chain 을 확장하지 않음 |
| corrective sub-chain (sibling, chain A) | **CLOSED / FAIL (CORRECTIVE_RED_STOP) / NO_V4_UNLOCK** (SEAL-1, step 11) | 본 SEAL 은 chain A 를 재오픈하지 않음 |
| **chain B (this document) — step 1** | DRAFT-1 (chain_b_step_1) — **SUPERSEDED by SEAL-1 at chain_b_step_2** | 2026-04-10, pre_seal_draft_hash=`ac792ab36c63d9594dcc3d679eeb5af2e37d812afb6682b5b6746bbc211e5fbc` — 내용 상속되어 본 SEAL 로 이관됨 |
| **chain B (this document) — step 2** | **SEAL-1 (chain_b_step_2, ACTIVE)** | 2026-04-10, user SEAL instruction at step 13 — root-cause finding (governance_gap) binding ACTIVE |
| chain C (baseline re-verification) | SEPARATE_CHAIN_NOT_OPENED | 본 SEAL 이 자동 개시하지 않음 |
| governance remediation proposal chain (separate) | NOT_OPENED_BY_THIS_SEAL | 본 SEAL 은 해당 chain 을 권고만 할 뿐 자동 개시하지 않음 (§10 d 참조) |

**chain A 의 판정 상속:** chain B SEAL-1 은 chain A 의 `FAIL (CORRECTIVE_RED_STOP)` 판정을 **수정하지 않는다**. chain B 의 임무는 step 8 run 에서 `execution_mode=ambiguous` 가 나온 **이유** 를 규명하는 것이며, FAIL 판정 자체는 chain A SEAL-1 에서 이미 불변화되었다. 본 SEAL 의 root-cause finding 도 chain A FAIL 판정을 뒤집지 않는다 (§5.5 참조).

**SEAL-1 의 권한 범위:** 본 SEAL 은 chain B 의 **1차 근본 원인 (primary root cause)** 을 `governance_gap` 으로 **봉인 고정** 하는 것에 한정된다. 2차 원인 (runner 의 env var 누락) 은 1차 원인의 귀결로 자동 분류되며, 별도 단독 판정 대상이 아니다. chain C (baseline 유효성 재검증) 및 governance remediation proposal (run GO 템플릿 수정 등) 은 **본 SEAL 의 효력 범위에서 명시적으로 제외** 된다.

---

## §2 Authority Chain — 12 prior hash-pinned artifacts (pre-chain-B, read-only)

| # | Artifact | sha256 | State (pre-chain-B) |
|---|---|---|---|
| 1 | docs/operations/evidence/sol_s1_v3_design.md | `b01ee65577a792d02bacff993cde006d95cccc2d214f922d1a9be85b5adad174` | SEALED |
| 2 | docs/operations/evidence/sol_s1_v3r1_go_receipt.md | `61e0070978bed68414f6a68c33fd7aff880a6639466cf52609100fe0a3454fae` | SEALED |
| 3 | docs/operations/evidence/sol_s1_v3r1_scope_lock_go.md | `8f5c0674289a64c64d16ab12ee5dd090a738bd7aee03e6e24084ac7b749c8bee` | SEALED |
| 4 | docs/operations/evidence/sol_s1_v3r1_impl_start_go.md | `e8961ae90348bf81cb5b4932636bc37dd368efdadb952cb0017c89eb590f5965` | SEALED |
| 5 | docs/operations/evidence/sol_s1_v3r1_impl_completion_receipt.md | `a799f485f53213b732c0409966d346b239a7c009723b5e2da183ac58496c16f9` | SEALED |
| 6 | docs/operations/evidence/sol_s1_v3r1_run_go_review_report.md | `c5b7b58d9d0023d2e73c6100b36d370116654c61544e92cbe34ae9fe807c2515` | DRAFT (permanent review) |
| 7 | docs/operations/evidence/sol_s1_v3r1_run_go_receipt.md | `b34947962aced58095fbaa7d2420c4218f31b9a098a0b689366c2e88e3ce3f38` | SEALED (SEAL-1) |
| 8 | scripts/sol_s1_v3_shadow_run.py | `94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` | FROZEN (read target) |
| 9 | docs/operations/evidence/sol_s1_v3_shadow_log.json | `34473335e1c890b63c99a080feec7b680810d32ae0757f00fc4bc7c6c46dc886` | run output (immutable) |
| 10 | docs/operations/evidence/sol_s1_v3_completion_receipt.md | `2d458eb6f466ad3a6bf3233a03012d828542f9bcd8c2339ff3f37485cf04c3f4` | run output (immutable) |
| 11 | docs/operations/evidence/sol_s1_v3r1_run_completion_receipt.md | `8f07d4eb3b5508a2ae02dc8e2d7f4566257608ea79d7acc3f085d00ce7ffb0f6` | SEALED (step 9 SEAL-1, FAIL locked) |
| 12 | docs/operations/evidence/sol_s1_v3r1_corrective_chain_closure_receipt.md | `a84713d31e4e124f77eaa0000edc21cf1ca42b9f48eaea9e088fe433ee4ebb41` | SEALED (step 11 SEAL-1, chain A CLOSED) |

**integrity_witness_pre_chain_b:** 12/12 = UNCHANGED since step 11 SEAL-1 (cross-verified at chain_b_step_1 start)
**integrity_witness_at_chain_b_step_2_pre_seal:** 12/12 = UNCHANGED (re-verified immediately before SEAL-1 write)
**env_at_chain_b_step_2_pre_seal:** `SOL_S1_V3_RUN_AUTHORIZED` = NOT SET, `SOL_S1_V3_EXECUTION_MODE` = NOT SET
**count_contract_2종:** 28 physical / 20 actual (unchanged since step 3)
**chain_b_step_1_DRAFT-1_hash (frozen at SEAL boundary):** `ac792ab36c63d9594dcc3d679eeb5af2e37d812afb6682b5b6746bbc211e5fbc`

(**note:** post-SEAL 13-artifact witness table is in §8.3 — this §2 pins only the 12 **prior** artifacts.)

---

## §3 Target Code Surface (scope-locked to `scripts/sol_s1_v3_shadow_run.py`)

| surface | line range | 역할 |
|---|---|---|
| enum 상수 정의 | 192–204 | `EXECUTION_MODE_AMBIGUOUS`, `EXECUTION_MODE_SOURCE_INFERRED`, `MODE_CONSISTENCY_AMBIGUOUS` 정의 |
| runtime 환경 변수 키 | 216–217 | `EXECUTION_MODE_ENV_KEY = "SOL_S1_V3_EXECUTION_MODE"` |
| `determine_execution_mode` 함수 | 734–790 | primary 판정 로직 (declared value → mode 결정) |
| `build_completion_receipt_v3r1` 함수 | 816–885 | receipt 조립, `determine_execution_mode` 호출 지점 |
| main_async() 의 env var 읽기 | 1752–1766 | `os.environ.get(EXECUTION_MODE_ENV_KEY, "")` → `declared_mode` 결정 |
| validator (정적 검증) | 1474–1545 | `validate_execution_mode_logic_v3r1` — 4 case 단위 테스트 |
| validator (소스 스캔) | 1622–1666 | `validate_no_speed_only_execution_mode_code` — 속도 단독 판정 코드 금지 검사 |

**범위 외 (분석 대상이 아님):** `EvidenceLog` (line 400 이하), block taxonomy (line 221 이하), ohlcv loading (line 1680 이하), 기타 strategy 호출부. 본 chain B 는 **execution_mode 경로에만** 국한된다.

---

## §4 Code Path Trace — step 8 run 의 `ambiguous` 반환 경로

### 4.1 run-time 분기점 (main_async, line 1752–1756)

```python
# scripts/sol_s1_v3_shadow_run.py, lines 1752–1756
declared_mode = os.environ.get(EXECUTION_MODE_ENV_KEY, "").strip()
if declared_mode:
    mode_source_for_build = EXECUTION_MODE_SOURCE_RUNNER
else:
    mode_source_for_build = EXECUTION_MODE_SOURCE_INFERRED
```

- `EXECUTION_MODE_ENV_KEY` = `"SOL_S1_V3_EXECUTION_MODE"` (line 217).
- step 8 run 시점에 이 환경 변수는 **설정되지 않았다** (`NOT SET`).
- 따라서 `declared_mode = ""` (strip 후 빈 문자열), 조건문 `if declared_mode:` 는 falsy.
- 실행 분기: `else` → `mode_source_for_build = EXECUTION_MODE_SOURCE_INFERRED` = `"inferred_from_runtime"`.

### 4.2 receipt 빌드 호출 (line 1758–1766)

```python
# scripts/sol_s1_v3_shadow_run.py, lines 1758–1766
receipt_v3r1 = build_completion_receipt_v3r1(
    evidence=evidence,
    authorization_source=IMPL_START_GO_V3R1_REF,
    implementation_receipt_ref=IMPL_COMPLETION_RECEIPT_V3R1_REF,
    declared_execution_mode=declared_mode or None,   # ← None (declared_mode is "")
    execution_mode_source=mode_source_for_build,     # ← "inferred_from_runtime"
    run_started_monotonic=run_started_monotonic,
    run_completed_monotonic=run_completed_monotonic,
)
```

- `declared_execution_mode = declared_mode or None` = `None` (빈 문자열은 falsy).
- `execution_mode_source = "inferred_from_runtime"` (line 1756 에서 결정됨).

### 4.3 `determine_execution_mode` 내부 (line 758–769)

```python
# scripts/sol_s1_v3_shadow_run.py, lines 758–769
# --- Primary judgment: declared value only ---
if declared_value in (
    EXECUTION_MODE_REALTIME_SHADOW,
    EXECUTION_MODE_HISTORICAL_REPLAY,
):
    mode = declared_value
    source = declared_source
else:
    # No valid declared value → ambiguous.
    # The speed witness is intentionally IGNORED here.
    mode = EXECUTION_MODE_AMBIGUOUS         # ← "ambiguous"
    source = EXECUTION_MODE_SOURCE_INFERRED # ← "inferred_from_runtime"
```

- 입력: `declared_value = None` (from line 1762).
- `None` 은 `(REALTIME_SHADOW, HISTORICAL_REPLAY)` tuple membership 테스트에서 false.
- 분기: `else` 절 진입.
- **출력:** `mode = "ambiguous"`, `source = "inferred_from_runtime"`.

### 4.4 `mode_consistency_check` 보조 판정 (line 771–789)

```python
# scripts/sol_s1_v3_shadow_run.py, lines 771–789
# --- Auxiliary witness: consistency check only ---
# This block NEVER overrides `mode`. It only sets a consistency label.
if mode == EXECUTION_MODE_HISTORICAL_REPLAY:
    ...
elif mode == EXECUTION_MODE_REALTIME_SHADOW:
    ...
else:
    # Ambiguous: by definition no consistency check is possible.
    consistency = MODE_CONSISTENCY_AMBIGUOUS
```

- `mode = "ambiguous"` 이므로 최종 `else` 분기 → `consistency = "ambiguous"`.
- 주석 "This block NEVER overrides `mode`" — 속도 witness 가 mode 를 덮어쓸 가능성 원천 차단.

### 4.5 step 8 run 에서 실제 반환된 값 (step 9 SEAL-1 §7 에서 고정된 수치와 일치)

| 필드 | 값 | 출처 |
|---|---|---|
| `execution_mode` | `ambiguous` | §4.3 else-branch |
| `execution_mode_source` | `inferred_from_runtime` | §4.1 else-branch + §4.3 |
| `mode_consistency_check` | `ambiguous` | §4.4 else-branch |

---

## §5 Root-Cause Finding — Governance Gap (code is correct) — **BINDING ACTIVE by SEAL-1**

> **SEAL-1 BINDING NOTE (chain_b_step_2, 2026-04-10):**
> 본 §5 의 내용은 chain B step 1 DRAFT-1 에서 "가설 / 후보 (candidate)" 상태로 작성되었고, chain B step 2 의 user SEAL instruction 에 의해 **봉인 고정 (binding)** 되었다. 이제 다음 사실들이 governance-layer legal record 로 확정된다:
>
> 1. **1차 근본 원인 = `governance_gap`** (§5.4 row d). V-3R1 governance 체인 12 문서 중 어느 것도 `SOL_S1_V3_EXECUTION_MODE` 환경 변수 protocol 을 명시하지 않았다. 이는 기각 불가능한 바인딩 사실로 기록된다.
> 2. **code defect 가설 = 기각 고정** (§5.4 row a). `scripts/sol_s1_v3_shadow_run.py` 의 `determine_execution_mode` / `EXECUTION_MODE_SOURCE_INFERRED` / `EXECUTION_MODE_AMBIGUOUS` 경로는 V-3R1 impl_start_go.md 의 "execution_mode 판정 규칙 잠금" 조항을 정확히 반영한다. 향후 이 경로를 code defect 로 재분류하려면 별도 chain + user GO 가 필요하다.
> 3. **2차 원인 = `(c) runner 의 env var 설정 누락`** 은 1차 원인의 귀결로 종속 분류된다. 단독 판정 대상이 아니며 별도 remediation target 도 아니다.
> 4. **chain A FAIL (CORRECTIVE_RED_STOP) 판정은 본 finding 과 독립적으로 유효** 하다 (§5.5). SEAL-1 은 chain A FAIL 판정을 수정하거나 뒤집지 않는다.
> 5. **baseline (64.3 / 35.7 / 70.9) 유효성 판단은 본 SEAL 의 범위 외** (chain C 영역). SEAL-1 은 baseline 에 대해 어떤 판단도 내리지 않는다.
> 6. **본 SEAL 은 governance remediation 을 자동 개시하지 않는다** — 별도 user GO 를 통한 별도 chain (governance remediation proposal chain) 에서만 개시 가능.
>
> 이 BINDING 효력은 `root_cause_finding_binding_active=true` 및 `SEAL_OF_THIS_DOCUMENT_ACTIVATES_ROOT_CAUSE_FINDING=true` header field 에 의해 legal 하게 고정된다.

### 5.1 결론 1 — **코드는 V-3R1 explicit GO § "execution_mode 판정 규칙 잠금" 을 정확히 구현한다**

V-3R1 impl_start_go.md (line 93–97) 는 다음 규칙을 설계 잠금으로 명시:

> ```
> execution_mode 판정 규칙 잠금
> - 주 판정 기준 = 명시 선언값 (execution_mode_source 로 출처 기록)
> - 보조 witness = run_duration_ms / bars_per_second (판정 근거 아님, 일치성 경고용)
> - 속도값(bars_per_second / run_duration_ms) 단독으로 execution_mode 를 확정 판정하는 설계 절대 금지
> - ambiguous 구간 명시 허용
> ```

§4.3 의 else-branch (`mode = EXECUTION_MODE_AMBIGUOUS`) 는 이 규칙의 **정확한 반영** 이다:
- declared_value 가 없으면 → `ambiguous` 반환 (속도로 추론하지 **않음**)
- 주석 line 766–768: `"No valid declared value → ambiguous. The speed witness is intentionally IGNORED here."`
- validator `validate_execution_mode_logic_v3r1` (line 1474) 의 **Case 3** 은 이 규칙을 단위 테스트로 고정:
  > `declared=None + VERY fast speed → ambiguous (NOT historical_replay)`

**즉, 코드 결함 아님.** step 8 run 에서 `ambiguous` 가 나온 것은 설계된 방어적 행동.

### 5.2 결론 2 — **governance gap: run GO 가 `SOL_S1_V3_EXECUTION_MODE` 설정 protocol 을 명시하지 않았다**

체인 A 의 12 개 V-3R1 governance 문서 전수 grep 결과:
- `SOL_S1_V3_EXECUTION_MODE` 환경 변수 키 이름이 언급된 **governance 문서 0 개**
- `execution_mode` 라는 용어는 7 개 문서에 존재하나, 이는 receipt 필드 / 판정 규칙 / 금지 사항 맥락이며, **runner 가 실행 시 설정해야 하는 환경 변수로서의 protocol** 은 어디에도 명시되어 있지 않다
- sol_s1_v3r1_run_go_receipt.md (step 7 SEAL-1) grep 결과: `execution_mode`, `SOL_S1_V3_EXECUTION_MODE`, `declared_value`, `declared_execution` 전부 **0 매치**

run_go_review_report.md 의 env var 선언 (line 318):

> ```
> - env var : SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted
> - env var set timing : run GO 문서가 SEALED 된 직후에만
> ```

— 여기서 **단 한 개** 의 env var 만 언급되고 있다. 두 번째 env var (`SOL_S1_V3_EXECUTION_MODE`) 는 누락.

### 5.3 결론 3 — **runner 가 단일 env var 만 설정하고 --run 호출 → 설계된 `ambiguous` 경로 진입**

step 8 run 실제 동작:
1. `SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted` 설정 (governance 지시대로)
2. `SOL_S1_V3_EXECUTION_MODE` 설정 **안 함** (governance 가 지시하지 않았으므로)
3. `python scripts/sol_s1_v3_shadow_run.py --run` 호출
4. main_async line 1752: `declared_mode = ""` (env var 없음)
5. line 1755 else-branch: `mode_source_for_build = "inferred_from_runtime"`
6. line 1762: `declared_execution_mode=None` 전달
7. determine_execution_mode line 765 else-branch: `mode = "ambiguous"` 반환
8. receipt 에 `execution_mode=ambiguous`, `source=inferred_from_runtime` 기록

### 5.4 근본 원인 (root cause) 분류

| 후보 원인 | 판정 | 근거 |
|---|---|---|
| (a) 코드 로직 결함 | **기각** | §5.1 — 설계 잠금 규칙 정확 반영, validator 4-case 통과, 속도 단독 판정 방지 |
| (b) 환경 변수 이름 오타 (코드 vs 문서) | **기각** | governance 문서에 키 이름 자체가 없으므로 비교 불가. 코드 내부 정의 line 217 유일 출처 |
| (c) runner 의 env var 설정 누락 | **2 차 원인** | runner 는 governance 가 명시하지 않은 env var 를 독자 판단으로 설정할 권한 없음 — 이 누락은 (d) 의 결과임 |
| (d) **run GO 가 `SOL_S1_V3_EXECUTION_MODE` 설정 protocol 을 명시하지 않았다** | **1 차 원인 (governance gap)** | §5.2 — V-3R1 governance 문서 12 개 전수 검색에서 키 이름 0 매치. 보조 env var 의 존재 자체가 governance 레이어에 기록되지 않았음 |
| (e) baseline 값 (64.3 / 35.7 / 70.9) 문제 | **범위 외** | chain C 영역. 본 chain B 는 판정하지 않음 |

**1 차 근본 원인:** **governance gap** — V-3R1 impl_start_go (step 4) 가 코드 수정 scope 에 `execution_mode` 필드 추가를 허용했지만, 같은 GO 와 이후 scope_lock_go / run_go 중 **어느 것도 `SOL_S1_V3_EXECUTION_MODE` 환경 변수 설정을 run 사전조건으로 명시하지 않았다**. 따라서 runner 는 `SOL_S1_V3_RUN_AUTHORIZED` 하나만 설정했고, 코드는 설계된 `ambiguous` 경로로 정확히 진입했다.

### 5.5 해석 귀결

- **FAIL (CORRECTIVE_RED_STOP) 판정의 유효성:** chain A SEAL-1 의 FAIL 판정은 `execution_mode=ambiguous` 와 **독립적으로** ecr=50.0%, block_rate=50.0%, sd_delta=29.1pp 의 3-axis yellow threshold violation 으로 확정됨. `execution_mode=ambiguous` 는 "PASS 주장을 불가능하게 만드는 meta-layer 보조 사유" 였지 primary fail driver 가 아니다. 따라서 본 chain B 의 발견이 chain A FAIL 판정을 뒤집지 않는다.
- **전략 성패 해석:** 전략(SMC+WaveTrend) 자체의 성패는 본 chain B 로 판정할 수 없다. ambiguous mode 상태에서 전개된 관측이므로 "전략이 실제로 RED 였는가" 에 대한 단정이 불가능하다.
- **재-run 정당성:** 이론적으로 동일 코드로 `SOL_S1_V3_EXECUTION_MODE=historical_replay` (또는 realtime_shadow) 를 설정하여 재실행하면 `execution_mode=historical_replay` (또는 realtime_shadow) + `source=declared_by_runner` 로 기록될 것이다. 다만 재-run 자체는 본 chain B 의 권한 밖이며 `additional_run_status = NOT_AUTHORIZED` 상태는 유지된다. 재-run 은 별도 user GO + run GO 재발행 + env var protocol 명시 가 선행되어야 한다.

---

## §6 Forbidden Axes (this SEAL does NOT do any of these)

| # | 금지 항목 | 상태 (post this SEAL-1) |
|---|---|---|
| 1 | frozen 스크립트 (`sol_s1_v3_shadow_run.py`) 수정 | NOT PERFORMED (sha256 unchanged) |
| 2 | 추가 `--run` 호출 | NOT PERFORMED |
| 3 | `SOL_S1_V3_RUN_AUTHORIZED` 설정 | NOT PERFORMED (env var NOT SET) |
| 4 | `SOL_S1_V3_EXECUTION_MODE` 설정 | NOT PERFORMED (env var NOT SET) |
| 5 | baseline (64.3 / 35.7 / 70.9) 값 수정 | NOT PERFORMED |
| 6 | chain C (baseline re-verification) 자동 개시 | NOT PERFORMED (`SEPARATE_CHAIN_NOT_OPENED` 유지) |
| 7 | 부모 chain (SOL S-1 root-cause chain) 확장 | NOT PERFORMED |
| 8 | corrective sub-chain (chain A) 재오픈 | NOT PERFORMED (SEAL-1 binding ACTIVE 유지) |
| 9 | step 9 SEAL-1 run_completion_receipt 의 FAIL 판정 수정 | NOT PERFORMED (locked inherit) |
| 10 | chain A step 11 SEAL-1 의 closure triplet (CLOSED/FAIL/NO_V4_UNLOCK) 수정 | NOT PERFORMED |
| 11 | count contract 2종 (28/20) 변경 | NOT PERFORMED |
| 12 | strategy 소스 / production 코드 수정 | NOT PERFORMED |
| 13 | auto_advance 활성화 | NOT PERFORMED (forbidden 유지) |
| 14 | governance remediation proposal chain 자동 개시 | NOT PERFORMED (별도 user GO 필요) |
| 15 | 동일 코드 재-run 을 위한 run GO 자동 재발행 | NOT PERFORMED (별도 user GO + 새로운 run GO chain 필요) |
| 16 | 전략 성패 (SMC+WaveTrend) 선언 | NOT PERFORMED (chain B scope 밖) |
| 17 | 본 chain B receipt 외 12 개 prior artifact 수정 | NOT PERFORMED (sha256 all unchanged) |

---

## §7 Count Contract 2종 Invariance Witness

| 지표 | 값 | 원 고정 시점 | chain B 시점 |
|---|---|---|---|
| physical count | 28 | step 3 (scope_lock_go.md) | 28 (unchanged) |
| actual count | 20 | step 3 (scope_lock_go.md) | 20 (unchanged) |

step 3 → chain B step 1 동안 **mutation 0 건**. chain B 는 이 값을 참조도 하지 않으며 수정도 하지 않는다.

---

## §8 SEAL Integrity Self-Declaration

### 8.1 SEAL Metadata

- document_state: **SEALED**
- governance_wrapper_format: chain_b_opening_analysis_v1 (unchanged from DRAFT-1)
- chain_b_step_1_DRAFT-1_status: SUPERSEDED (content inherited into SEAL-1; pre_seal_draft_hash=`ac792ab36c63d9594dcc3d679eeb5af2e37d812afb6682b5b6746bbc211e5fbc`)
- chain_b_step_2_SEAL-1_status: ACTIVE
- sealed_by: `user_accept_chain_b_step2_governance_gap_finding_seal_2026_04_10`
- sealed_at: 2026-04-10
- seal_number: SEAL-1
- seal_step: chain_b_step_2
- seal_grant_scope: governance_gap_finding_binding_only
- root_cause_finding_binding_active: **true**
- analysis_mode: read_only_static_analysis (unchanged)
- files_read_during_analysis: `scripts/sol_s1_v3_shadow_run.py`, 12 V-3R1 governance / evidence artifacts (grep 범위)
- files_modified_during_SEAL: 1 (this chain B receipt only — DRAFT-1 → SEAL-1 transition)
- frozen_script_sha256: `94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` (unchanged)
- env_SOL_S1_V3_RUN_AUTHORIZED: NOT SET (unchanged by this SEAL)
- env_SOL_S1_V3_EXECUTION_MODE: NOT SET (unchanged by this SEAL)
- baseline_values_referenced: 64.3 / 35.7 / 70.9 (read-only citation, no mutation)
- chain_a_closure_triplet: UNTOUCHED (CLOSED / FAIL / NO_V4_UNLOCK binding ACTIVE)
- parent_chain_status: NOT CLOSED BY THIS SEAL
- chain_c_status: SEPARATE_CHAIN_NOT_OPENED
- governance_remediation_proposal_chain_status: NOT_OPENED_BY_THIS_SEAL (recommended for separate user GO in §10 d)
- count_contract_2종: 28 / 20 (unchanged since step 3)

### 8.2 SEAL Effect Declarations (what this SEAL does / does not do)

| # | grant axis | value |
|---|---|---|
| 1 | `SEAL_OF_THIS_DOCUMENT_GRANTS_EXECUTION_RESUMPTION` | **false** |
| 2 | `SEAL_OF_THIS_DOCUMENT_GRANTS_V4_UNLOCK` | **false** |
| 3 | `SEAL_OF_THIS_DOCUMENT_GRANTS_ATTEMPT_2` | **false** |
| 4 | `SEAL_OF_THIS_DOCUMENT_GRANTS_ADDITIONAL_RUN` | **false** |
| 5 | `SEAL_OF_THIS_DOCUMENT_GRANTS_CHAIN_C_AUTO_START` | **false** |
| 6 | `SEAL_OF_THIS_DOCUMENT_GRANTS_PARENT_CHAIN_EXTENSION` | **false** |
| 7 | `SEAL_OF_THIS_DOCUMENT_GRANTS_CORRECTIVE_CHAIN_REOPEN` | **false** |
| 8 | `SEAL_OF_THIS_DOCUMENT_GRANTS_CODE_MUTATION_AUTHORITY` | **false** |
| 9 | `SEAL_OF_THIS_DOCUMENT_GRANTS_GOVERNANCE_REMEDIATION_AUTO_START` | **false** |
| 10 | `SEAL_OF_THIS_DOCUMENT_ACTIVATES_ROOT_CAUSE_FINDING` | **true** (governance_gap finding now binding) |

**유일한 positive grant:** (10) root-cause finding 의 binding activation. 다른 모든 axis 는 false.

### 8.3 Post-SEAL 13-Artifact Integrity Witness

| # | Artifact | sha256 | State (post chain B step 2 SEAL-1) |
|---|---|---|---|
| 1 | docs/operations/evidence/sol_s1_v3_design.md | `b01ee65577a792d02bacff993cde006d95cccc2d214f922d1a9be85b5adad174` | UNCHANGED since pre-chain-B |
| 2 | docs/operations/evidence/sol_s1_v3r1_go_receipt.md | `61e0070978bed68414f6a68c33fd7aff880a6639466cf52609100fe0a3454fae` | UNCHANGED since pre-chain-B |
| 3 | docs/operations/evidence/sol_s1_v3r1_scope_lock_go.md | `8f5c0674289a64c64d16ab12ee5dd090a738bd7aee03e6e24084ac7b749c8bee` | UNCHANGED since pre-chain-B |
| 4 | docs/operations/evidence/sol_s1_v3r1_impl_start_go.md | `e8961ae90348bf81cb5b4932636bc37dd368efdadb952cb0017c89eb590f5965` | UNCHANGED since pre-chain-B |
| 5 | docs/operations/evidence/sol_s1_v3r1_impl_completion_receipt.md | `a799f485f53213b732c0409966d346b239a7c009723b5e2da183ac58496c16f9` | UNCHANGED since pre-chain-B |
| 6 | docs/operations/evidence/sol_s1_v3r1_run_go_review_report.md | `c5b7b58d9d0023d2e73c6100b36d370116654c61544e92cbe34ae9fe807c2515` | UNCHANGED since pre-chain-B |
| 7 | docs/operations/evidence/sol_s1_v3r1_run_go_receipt.md | `b34947962aced58095fbaa7d2420c4218f31b9a098a0b689366c2e88e3ce3f38` | UNCHANGED since pre-chain-B |
| 8 | scripts/sol_s1_v3_shadow_run.py | `94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` | UNCHANGED since pre-chain-B (FROZEN) |
| 9 | docs/operations/evidence/sol_s1_v3_shadow_log.json | `34473335e1c890b63c99a080feec7b680810d32ae0757f00fc4bc7c6c46dc886` | UNCHANGED since pre-chain-B |
| 10 | docs/operations/evidence/sol_s1_v3_completion_receipt.md | `2d458eb6f466ad3a6bf3233a03012d828542f9bcd8c2339ff3f37485cf04c3f4` | UNCHANGED since pre-chain-B |
| 11 | docs/operations/evidence/sol_s1_v3r1_run_completion_receipt.md | `8f07d4eb3b5508a2ae02dc8e2d7f4566257608ea79d7acc3f085d00ce7ffb0f6` | UNCHANGED since pre-chain-B |
| 12 | docs/operations/evidence/sol_s1_v3r1_corrective_chain_closure_receipt.md | `a84713d31e4e124f77eaa0000edc21cf1ca42b9f48eaea9e088fe433ee4ebb41` | UNCHANGED since pre-chain-B |
| 13 | docs/operations/evidence/sol_s1_v3r1_chain_b_execution_mode_analysis_draft.md (**this file**) | *(reported externally in the chain B step 13 SEAL-1 report — self-referential hash embedding intentionally avoided)* | **SEAL-1 (chain_b_step_2, ACTIVE)** |

**integrity_witness_post_SEAL-1:** 12/12 prior artifacts UNCHANGED (bytewise preserved). 1 artifact transitioned DRAFT-1 → SEAL-1 (this document).

**env_witness_post_SEAL-1:** `SOL_S1_V3_RUN_AUTHORIZED` = NOT SET, `SOL_S1_V3_EXECUTION_MODE` = NOT SET. Neither env var was set at any point during chain B.

**frozen_script_witness_post_SEAL-1:** `scripts/sol_s1_v3_shadow_run.py` sha256 = `94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` (unchanged — read-only analysis confirmed).

---

## §9 Global State Declaration (post chain B step 2 SEAL-1)

```
GLOBAL STATE                                      = STANDBY
V-3R1 RUN STATE                                   = EXECUTED_ONCE (frozen)
V-3R1 RUN PASS/FAIL JUDGMENT                      = FAIL (CORRECTIVE_RED_STOP) [inherited, locked]
V-3R1 CORRECTIVE SUB-CHAIN (chain A)              = CLOSED / FAIL / NO_V4_UNLOCK (step 11 SEAL-1, binding ACTIVE)
CHAIN B (execution_mode root-cause) — step 1      = DRAFT-1 SUPERSEDED (content inherited)
CHAIN B (execution_mode root-cause) — step 2      = SEAL-1 ACTIVE (this document)
CHAIN B ROOT-CAUSE FINDING                        = governance_gap (primary, BINDING ACTIVE)
CHAIN B code_defect HYPOTHESIS                    = REJECTED AND LOCKED
CHAIN C (baseline reverification)                 = SEPARATE_CHAIN_NOT_OPENED
GOVERNANCE REMEDIATION PROPOSAL CHAIN             = NOT_OPENED_BY_THIS_SEAL (recommended, requires separate user GO)
PARENT CHAIN (SOL S-1 root-cause chain)           = NOT CLOSED, NOT EXTENDED BY CHAIN B
V-4 UNLOCK                                        = NOT AUTHORIZED
ATTEMPT_2                                         = NOT AUTHORIZED
ADDITIONAL_RUN_INVOCATION                         = NOT AUTHORIZED
SOL_S1_V3_RUN_AUTHORIZED                          = NOT SET
SOL_S1_V3_EXECUTION_MODE                          = NOT SET
EXECUTION_RESUMPTION_AUTHORITY                    = NOT GRANTED BY THIS SEAL
CODE_MUTATION_AUTHORITY                           = NOT GRANTED BY THIS SEAL
GOVERNANCE_REMEDIATION_AUTO_START_AUTHORITY       = NOT GRANTED BY THIS SEAL
CHAIN_C_AUTO_START_AUTHORITY                      = NOT GRANTED BY THIS SEAL
CORRECTIVE_CHAIN_REOPEN_AUTHORITY                 = NOT GRANTED BY THIS SEAL
count_contract_2종                                = 28 / 20 (unchanged since step 3)
auto_advance                                      = forbidden
next_legal_action                                 = user decision (open governance remediation proposal chain,
                                                    open chain C, or maintain STANDBY — all require explicit user GO)
```

---

## §10 Next Legal Actions (reference only — user decision required)

본 SEAL-1 이후 합법적인 다음 행동 후보:

| 후보 | 설명 | 필요 사전조건 | 상태 |
|---|---|---|---|
| ~~a~~ | ~~본 chain B DRAFT 의 검수 및 SEAL~~ | ~~user SEAL GO~~ | **COMPLETED at chain_b_step_2 SEAL-1 (this document)** |
| ~~b~~ | ~~본 chain B DRAFT 의 내용 수정 요청~~ | ~~user revision instruction~~ | NOT INVOKED (step 13 was ACCEPT, not revise) |
| c | chain C (baseline re-verification) 개시 | 별도 user GO (chain B 결과와 독립) | AVAILABLE (priority 3 per user checklist) |
| d | 별도 체인 — governance remediation proposal chain — 예: run GO 템플릿에 `SOL_S1_V3_EXECUTION_MODE` protocol 추가 권고 | 별도 user GO | **AVAILABLE (priority 2 per user checklist, user's recommended next action)** |
| e | chain B 의 후속 단계 — 동일 코드 재실행을 위한 run GO 재발행 | **별도 user GO + 새로운 run GO 체인 전체 + env var protocol 명시** | AVAILABLE (not recommended until d is done) |
| f | STANDBY 유지 | 지시 없음 시 기본 | ACTIVE (default) |

본 SEAL 은 c~f 중 **어떤 것도 자동 개시하지 않는다**. 특히 (d) governance remediation proposal chain 은 user step 13 의 checklist priority 2 로 권고되지만, **본 SEAL 의 효력은 해당 chain 을 자동 개시하지 않는다** (`SEAL_OF_THIS_DOCUMENT_GRANTS_GOVERNANCE_REMEDIATION_AUTO_START=false`).

---

## §11 Revision Log

- **DRAFT-1** (2026-04-10, chain_b_step_1) — initial chain B opening analysis DRAFT created per user step 12 instruction. Read-only static analysis of `scripts/sol_s1_v3_shadow_run.py` (frozen) `inferred_from_runtime` / `ambiguous` return path. Root-cause finding: governance gap (run GO did not specify `SOL_S1_V3_EXECUTION_MODE` protocol). 0 mutation on 12 prior artifacts. 0 mutation on frozen script. 0 additional run invocations. 0 env var changes. chain A SEAL-1 binding preserved. chain C NOT opened. parent chain NOT extended. DRAFT-1 post-creation sha256 is reported externally in the chain B opening report (self-referential embedding intentionally avoided). **Status at chain B step 2: SUPERSEDED by SEAL-1 (content inherited).** pre_seal_draft_hash=`ac792ab36c63d9594dcc3d679eeb5af2e37d812afb6682b5b6746bbc211e5fbc`.

- **SEAL-1** (2026-04-10, chain_b_step_2) — chain B DRAFT-1 ACCEPTED and transitioned to SEALED per user step 13 instruction. SEAL effect scoped strictly to binding the primary root-cause finding of `execution_mode=ambiguous` as `governance_gap` (§5 BINDING NOTE). Edits applied in this SEAL transition: title → "(SEALED)"; header metadata block fully replaced (document_state=SEALED, sealed_by, seal_number=SEAL-1, pre_seal_draft_hash, 9 `SEAL_OF_THIS_DOCUMENT_GRANTS_*=false`, 1 `SEAL_OF_THIS_DOCUMENT_ACTIVATES_ROOT_CAUSE_FINDING=true`); §0 rewritten as "Governance Scope Declaration (DRAFT → SEALED, post chain B step 2)" embedding the user step 13 SEAL quote; §1 Chain B Lifecycle table extended with step 1 SUPERSEDED row + step 2 SEAL-1 ACTIVE row + governance remediation proposal chain row; §2 integrity witness extended with `integrity_witness_at_chain_b_step_2_pre_seal`; §5 Root-Cause Finding prefixed with SEAL-1 BINDING NOTE locking the governance_gap finding and rejecting the code_defect hypothesis; §6 renamed to "Forbidden Axes (this SEAL does NOT do any of these)" and expanded from 13 → 17 forbidden items; §8 rewritten as "SEAL Integrity Self-Declaration" with 8.1 SEAL Metadata, 8.2 SEAL Effect Declarations (10-row grant axis table), 8.3 post-SEAL 13-artifact Integrity Witness table; §9 Global State Declaration updated to "post chain B step 2 SEAL-1"; §10 Next Legal Actions updated with a/b strikethrough as completed, d marked as user's checklist priority 2. Bytewise invariance witnesses: 12 prior artifacts UNCHANGED (`b01ee65…`, `61e0070…`, `8f5c067…`, `e8961ae…`, `a799f48…`, `c5b7b58…`, `b349479…`, `94110d2…`, `34473335…`, `2d458eb…`, `8f07d4e…`, `a84713d…`). frozen_script sha256=`94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` (unchanged, read-only only). env `SOL_S1_V3_RUN_AUTHORIZED`=NOT SET, `SOL_S1_V3_EXECUTION_MODE`=NOT SET throughout SEAL transition. 0 additional `--run` invocations. 0 baseline value mutations. 0 parent-chain extensions. chain A closure triplet UNTOUCHED. count_contract_2종 unchanged at 28/20. chain C NOT auto-started. governance remediation proposal chain NOT auto-started. auto_advance remains forbidden. SEAL-1 post-write sha256 of this document is reported externally in the chain B step 13 SEAL-1 report (self-referential hash embedding intentionally avoided).
