# SOL S-1 V-3R1 — Governance Remediation Proposal (DRAFT)

**document_state:** DRAFT
**review_status:** PENDING_USER_REVIEW
**receipt_class:** v3r1_governance_remediation_proposal_opening_draft
**chain_id:** governance_remediation_proposal_chain
**parent_chain:** SOL S-1 root-cause chain (NOT CLOSED, NOT EXTENDED)
**sibling_chain_a:** corrective_sub_chain (CLOSED / FAIL / NO_V4_UNLOCK at step 11 SEAL-1)
**sibling_chain_b:** execution_mode_root_cause_chain (SEALED at chain_b_step_2, governance_gap finding BINDING ACTIVE)
**draft_created_at:** 2026-04-11
**draft_step:** grp_chain_step_1 (opening remediation DRAFT)
**auto_advance:** forbidden
**analysis_mode:** document_layer_design_only
**frozen_script_mutation_by_this_draft:** false
**additional_run_invocation_by_this_draft:** false
**SOL_S1_V3_RUN_AUTHORIZED_state:** NOT SET (unchanged by this DRAFT)
**SOL_S1_V3_EXECUTION_MODE_state:** NOT SET (unchanged by this DRAFT)
**baseline_mutation_by_this_draft:** false
**count_contract_mutation_by_this_draft:** false
**chain_c_auto_start_by_this_draft:** false
**parent_chain_extension_by_this_draft:** false
**chain_a_reopen_by_this_draft:** false
**chain_b_seal_mutation_by_this_draft:** false
**run_go_template_actual_edit_by_this_draft:** false (only proposes changes at document-layer design level)
**DRAFT_OF_THIS_DOCUMENT_GRANTS_EXECUTION_RESUMPTION:** false
**DRAFT_OF_THIS_DOCUMENT_GRANTS_V4_UNLOCK:** false
**DRAFT_OF_THIS_DOCUMENT_GRANTS_ATTEMPT_2:** false
**DRAFT_OF_THIS_DOCUMENT_GRANTS_ADDITIONAL_RUN:** false
**DRAFT_OF_THIS_DOCUMENT_GRANTS_CHAIN_C_AUTO_START:** false
**DRAFT_OF_THIS_DOCUMENT_GRANTS_PARENT_CHAIN_EXTENSION:** false
**DRAFT_OF_THIS_DOCUMENT_GRANTS_CORRECTIVE_CHAIN_REOPEN:** false
**DRAFT_OF_THIS_DOCUMENT_GRANTS_CODE_MUTATION_AUTHORITY:** false
**DRAFT_OF_THIS_DOCUMENT_GRANTS_ACTUAL_RUN_GO_TEMPLATE_EDIT:** false
**DRAFT_OF_THIS_DOCUMENT_IS_PROPOSAL_ONLY:** true (binding effect requires subsequent explicit SEAL + separate template edit GO)

---

## §0 Governance Scope Declaration

본 문서는 **governance remediation proposal chain (GRP chain)** 의 **opening DRAFT-1** 이다. 2026-04-11 user directive 에 의해 개시됨:

> "governance remediation proposal chain을 시작하라.
>  범위는 run GO 템플릿 및 governance protocol 보강안 DRAFT 작성까지만 제한한다.
>  핵심 목표는 `SOL_S1_V3_EXECUTION_MODE={realtime_shadow|historical_replay}` 를 run execution 사전조건으로 명시하는 remediation proposal을 설계하는 것이다.
>  다음 4 slot 을 반드시 포함하라:
>  1) 관측 규칙: execution_mode 선언 필수 조건
>  2) 상태 전이 규칙: 선언 누락 시 run GO 발행 불가
>  3) 실행 제한 규칙: `SOL_S1_V3_RUN_AUTHORIZED` 와 `SOL_S1_V3_EXECUTION_MODE` 중 하나라도 누락 시 execution 금지
>  4) 헌법/거버넌스 제한 규칙: runner 독자 판단으로 env var 설정 금지
>  frozen 스크립트 수정, 추가 `--run` 호출, `SOL_S1_V3_RUN_AUTHORIZED` 설정, `SOL_S1_V3_EXECUTION_MODE` 실제 설정, baseline 값 수정, chain C 자동 개시, 부모 chain 확장은 모두 금지한다."

### 이 DRAFT 가 하는 것

- chain B SEAL-1 에서 binding 된 `governance_gap` finding 을 직접 상속받아 **remediation proposal 설계** 를 문서 레이어에서 작성한다.
- 4 slot (관측 / 상태 전이 / 실행 제한 / 헌법·거버넌스 제한) 을 **필수 구성 요소** 로 포함하여 proposal 을 구조화한다.
- run GO 템플릿 및 governance protocol 의 **제안된 diff** 를 문서 내부 inline 형태로 기재한다 (**실제 템플릿 파일 수정은 하지 않음**).
- chain B SEAL-1 sha256 (`865336ea…0ddc`) 을 authority pin 으로 고정하여 chain continuity 를 보장한다.
- 13 개 prior artifact + 본 DRAFT = 14 artifact 의 post-creation integrity witness 를 §8 에 고정한다.

### 이 DRAFT 가 하지 않는 것 (user directive 의 forbidden axes + 보조 금지)

- **frozen 스크립트 `scripts/sol_s1_v3_shadow_run.py` 를 수정하지 않는다** (`frozen_script_mutation_by_this_draft=false`)
- **추가 `--run` 호출을 하지 않는다** (`additional_run_invocation_by_this_draft=false`)
- **`SOL_S1_V3_RUN_AUTHORIZED` 를 설정하지 않는다** (env var 계속 NOT SET)
- **`SOL_S1_V3_EXECUTION_MODE` 를 **실제로** 설정하지 않는다** (env var 계속 NOT SET — 단순 proposal 이지 실행 준비 아님)
- **baseline (64.3 / 35.7 / 70.9) 값을 수정하지 않는다**
- **chain C (baseline re-verification) 를 자동 개시하지 않는다** (`chain_c_auto_start_by_this_draft=false`)
- **부모 chain (SOL S-1 root-cause chain) 을 확장하지 않는다** (`parent_chain_extension_by_this_draft=false`)
- **chain A (corrective sub-chain) 를 재오픈하지 않는다** (`chain_a_reopen_by_this_draft=false`)
- **chain B SEAL-1 문서를 수정하지 않는다** (`chain_b_seal_mutation_by_this_draft=false`)
- **run GO 템플릿 파일 자체를 수정하지 않는다** — 본 DRAFT 는 템플릿 수정 **제안** 을 문서 내부에 기재할 뿐이며, 실제 `sol_s1_v3r1_run_go_receipt.md` 계열 파일의 재발행은 **별도 user GO + 별도 chain** 이 선행되어야 한다 (`run_go_template_actual_edit_by_this_draft=false`)
- **governance protocol 문서의 실제 수정도 하지 않는다** — proposal 만 작성
- **count contract 2종 (28/20) 을 변경하지 않는다**
- **13 개 prior artifact 중 본 DRAFT 외 아무것도 수정하지 않는다**
- **auto_advance 를 허용하지 않는다** (forbidden 유지)
- **strategy 소스 (`strategies/*.py`) / production 코드 를 수정하지 않는다**
- **본 DRAFT 의 자동 SEAL 전환을 하지 않는다** (SEAL 은 별도 user GO 필요)
- **전략(SMC+WaveTrend) 자체의 성패를 선언하지 않는다**
- **chain B 의 root-cause finding 을 뒤집거나 약화시키지 않는다** — 본 DRAFT 는 해당 finding 을 starting premise 로만 사용
- **`execution_mode={realtime_shadow|historical_replay}` 중 어느 값을 선택할지 미리 고정하지 않는다** — proposal 은 두 값 모두를 legal domain 으로 명시하며, 선택은 별도 run GO 에서 이뤄져야 한다

---

## §1 Chain Context

| chain | status | 본 DRAFT 와의 관계 |
|---|---|---|
| SOL S-1 root-cause chain (parent) | NOT CLOSED | 본 DRAFT 는 parent chain 을 **확장하지 않음** |
| corrective sub-chain (chain A, sibling) | **CLOSED / FAIL (CORRECTIVE_RED_STOP) / NO_V4_UNLOCK** (SEAL-1, step 11) | 본 DRAFT 는 chain A 를 **재오픈하지 않음**. chain A FAIL 판정은 `execution_mode=ambiguous` 와 독립적으로 유효 |
| chain B — execution_mode root-cause (sibling) | **SEALED** (SEAL-1, chain_b_step_2) — root-cause finding `governance_gap` BINDING ACTIVE | 본 DRAFT 는 chain B 를 **starting premise 로 상속** 한다. chain B finding 을 수정하거나 뒤집지 않으며, 해당 finding 을 해결하기 위한 remediation 설계를 진행한다 |
| **governance remediation proposal chain (this chain)** | **DRAFT (grp_chain_step_1, this document)** | opening DRAFT. 문서 레이어 proposal only — 실제 template edit 이나 execution 재개는 이뤄지지 않음 |
| chain C (baseline re-verification) | SEPARATE_CHAIN_NOT_OPENED | 본 DRAFT 는 **자동 개시하지 않음** (user directive 명시 금지) |
| run GO 재발행 chain (future) | NOT_OPENED | 본 DRAFT 완료 (및 별도 SEAL) 후에만 별도 user GO 로 개시 가능 |

**상속 명제:** 본 DRAFT 의 모든 proposal 은 chain B SEAL-1 §5 BINDING NOTE 의 다음 명제를 전제로 한다:
> "V-3R1 impl_start_go (step 4) 가 코드 수정 scope 에 `execution_mode` 필드 추가를 허용했지만, 같은 GO 와 이후 scope_lock_go / run_go 중 어느 것도 `SOL_S1_V3_EXECUTION_MODE` 환경 변수 설정을 run 사전조건으로 명시하지 않았다."

이 명제는 governance layer 의 결함이며, code layer 는 정상이다. 따라서 remediation 은 **governance layer 에서만** 이뤄져야 한다.

---

## §2 Authority Chain — 13 prior hash-pinned artifacts (read-only)

| # | Artifact | sha256 | State (pre-grp-chain) |
|---|---|---|---|
| 1 | docs/operations/evidence/sol_s1_v3_design.md | `b01ee65577a792d02bacff993cde006d95cccc2d214f922d1a9be85b5adad174` | SEALED |
| 2 | docs/operations/evidence/sol_s1_v3r1_go_receipt.md | `61e0070978bed68414f6a68c33fd7aff880a6639466cf52609100fe0a3454fae` | SEALED |
| 3 | docs/operations/evidence/sol_s1_v3r1_scope_lock_go.md | `8f5c0674289a64c64d16ab12ee5dd090a738bd7aee03e6e24084ac7b749c8bee` | SEALED |
| 4 | docs/operations/evidence/sol_s1_v3r1_impl_start_go.md | `e8961ae90348bf81cb5b4932636bc37dd368efdadb952cb0017c89eb590f5965` | SEALED |
| 5 | docs/operations/evidence/sol_s1_v3r1_impl_completion_receipt.md | `a799f485f53213b732c0409966d346b239a7c009723b5e2da183ac58496c16f9` | SEALED |
| 6 | docs/operations/evidence/sol_s1_v3r1_run_go_review_report.md | `c5b7b58d9d0023d2e73c6100b36d370116654c61544e92cbe34ae9fe807c2515` | DRAFT (permanent review) |
| 7 | docs/operations/evidence/sol_s1_v3r1_run_go_receipt.md | `b34947962aced58095fbaa7d2420c4218f31b9a098a0b689366c2e88e3ce3f38` | SEALED (SEAL-1) |
| 8 | scripts/sol_s1_v3_shadow_run.py | `94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` | FROZEN (read target only — not modified) |
| 9 | docs/operations/evidence/sol_s1_v3_shadow_log.json | `34473335e1c890b63c99a080feec7b680810d32ae0757f00fc4bc7c6c46dc886` | run output (immutable) |
| 10 | docs/operations/evidence/sol_s1_v3_completion_receipt.md | `2d458eb6f466ad3a6bf3233a03012d828542f9bcd8c2339ff3f37485cf04c3f4` | run output (immutable) |
| 11 | docs/operations/evidence/sol_s1_v3r1_run_completion_receipt.md | `8f07d4eb3b5508a2ae02dc8e2d7f4566257608ea79d7acc3f085d00ce7ffb0f6` | SEALED (step 9 SEAL-1, FAIL locked) |
| 12 | docs/operations/evidence/sol_s1_v3r1_corrective_chain_closure_receipt.md | `a84713d31e4e124f77eaa0000edc21cf1ca42b9f48eaea9e088fe433ee4ebb41` | SEALED (step 11 SEAL-1, chain A CLOSED) |
| 13 | docs/operations/evidence/sol_s1_v3r1_chain_b_execution_mode_analysis_draft.md | `865336eaadd36037f951d8969ab27733d653dab393f72143be1b9ea1640b0ddc` | SEALED (chain_b_step_2 SEAL-1, governance_gap finding BINDING ACTIVE) |

**integrity_witness_pre_grp_chain:** 13/13 = UNCHANGED since chain B step 2 SEAL-1 (cross-verified immediately before DRAFT-1 creation).
**env:** `SOL_S1_V3_RUN_AUTHORIZED` = NOT SET, `SOL_S1_V3_EXECUTION_MODE` = NOT SET
**count_contract_2종:** 28 physical / 20 actual (unchanged since step 3)

---

## §3 Problem Statement (inherited from chain B SEAL-1)

### 3.1 Existing code surface (read-only citation, `scripts/sol_s1_v3_shadow_run.py`)

**line 217** (enum constant):
```python
EXECUTION_MODE_ENV_KEY: str = "SOL_S1_V3_EXECUTION_MODE"
```

**line 1752–1756** (main_async runtime read):
```python
declared_mode = os.environ.get(EXECUTION_MODE_ENV_KEY, "").strip()
if declared_mode:
    mode_source_for_build = EXECUTION_MODE_SOURCE_RUNNER
else:
    mode_source_for_build = EXECUTION_MODE_SOURCE_INFERRED
```

**line 734–769** (determine_execution_mode primary branch):
```python
if declared_value in (
    EXECUTION_MODE_REALTIME_SHADOW,
    EXECUTION_MODE_HISTORICAL_REPLAY,
):
    mode = declared_value
    source = declared_source
else:
    # No valid declared value → ambiguous.
    # The speed witness is intentionally IGNORED here.
    mode = EXECUTION_MODE_AMBIGUOUS
    source = EXECUTION_MODE_SOURCE_INFERRED
```

이 코드는 `declared_value` 없이 호출될 때 **설계된 대로** `ambiguous` 를 반환한다. 문제는 코드가 아니라, **governance 문서가 이 `declared_value` 를 어떻게 공급할지 protocol 을 명시하지 않았다** 는 점이다.

### 3.2 V-3R1 governance 문서 전수 grep 결과 (chain B SEAL-1 §5.2 인용)

- 12 V-3R1 governance 문서 (design, go_receipt, scope_lock_go, impl_start_go, impl_completion_receipt, run_go_review_report, run_go_receipt 등) 중 `SOL_S1_V3_EXECUTION_MODE` 키 이름 = **0 매치**
- run_go_review_report.md line 318 에 언급된 env var = **단 1 개** (`SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted`)
- 두 번째 env var protocol = **완전히 누락**

### 3.3 Legal layer 요약

| layer | 상태 |
|---|---|
| code layer | ✅ correct (validator 4-case 통과, 속도 단독 판정 방지 lock 됨) |
| governance layer | ❌ **gap**: `SOL_S1_V3_EXECUTION_MODE` protocol 미명시 |
| runner layer | ⚠️ governance 가 명시하지 않은 env var 를 독자 판단으로 설정할 권한 없음 — 올바른 행동 (하지만 governance 공백이 이를 유발) |

**Remediation 대상:** **governance layer 만**. code 수정 불필요.

---

## §4 Proposed Remediation — 4 Mandatory Slots

본 §4 는 user directive 가 명시한 4 개 slot 을 전부 포함한다. 각 slot 은 (a) 규칙 본문, (b) 적용 layer, (c) 위반 시 행동, (d) governance 문서 내 삽입 위치 제안 의 4-field 구조로 작성된다.

---

### 4.1 Slot 1 — **관측 규칙 (Observation Rule)**: execution_mode 선언 필수 조건

#### (a) 규칙 본문 (proposal)

> **RULE-OBS-1 (execution_mode declaration mandate):**
> 모든 V-3R1 (및 후속 V-N) run 은 `--run` 호출 **이전에** 반드시 다음 두 환경 변수가 모두 설정되어 있어야 한다:
> - `SOL_S1_V3_RUN_AUTHORIZED = v3_run_go_granted`
> - `SOL_S1_V3_EXECUTION_MODE ∈ {realtime_shadow, historical_replay}`
>
> 두 변수의 존재는 run GO 문서 SEAL-1 의 **정의된 사전조건** 으로 간주된다. 두 번째 변수의 값은 **declared value** 로 간주되며, 코드의 `determine_execution_mode` 함수가 `declared_value` 로 직접 수신한다.
>
> `SOL_S1_V3_EXECUTION_MODE` 의 값은 `{realtime_shadow, historical_replay}` 중 **정확히 하나** 여야 한다. 빈 문자열, 공백, 다른 값, `ambiguous` 는 **선언으로 인정되지 않는다**.

#### (b) 적용 layer

- **governance 문서 layer:** run GO 템플릿, run GO 재발행 receipt, pre-run checklist
- **관측 단계:** run GO SEAL 직후부터 `--run` 호출 시점까지
- **적용 대상:** V-3R1 계열 및 후속 모든 shadow / live run

#### (c) 위반 시 행동

- `SOL_S1_V3_EXECUTION_MODE` 가 설정되지 않은 채 `--run` 호출이 시도되면 → (§4.3 Slot 3 의 실행 제한 규칙 trigger) → run 금지
- `SOL_S1_V3_EXECUTION_MODE` 값이 `{realtime_shadow, historical_replay}` 외 값이면 → 코드가 `declare_value` tuple 멤버십 테스트에서 false → `determine_execution_mode` 의 `ambiguous` 경로 진입 → 이는 **governance 위반** 의 신호로 기록되어야 함 (현재 코드는 `ambiguous` 를 반환만 하지, 위반 signal 을 emit 하지 않음 — 이는 별도 code 수정 체인의 영역이며 본 proposal 범위 밖)

#### (d) 삽입 위치 제안 (문서 레이어)

| 대상 문서 | 삽입 위치 | 삽입 내용 |
|---|---|---|
| `sol_s1_v3r1_run_go_receipt.md` (또는 재발행본) | 기존 env var 섹션 바로 아래 | 위 규칙 본문 전문 + `declared value` 정의 |
| 새 문서 `sol_s1_v3_execution_mode_protocol.md` (권고) | 신규 작성 | slot 1~4 전체를 governance-level doctrine 으로 고정 |
| `sol_s1_v3r1_run_go_review_report.md` (review layer) | 기존 env var 선언 옆 | "두 번째 env var protocol" 섹션 추가 |

**본 DRAFT 는 위 삽입을 실제로 수행하지 않는다.** 삽입은 별도 chain + 별도 user GO 의 scope.

---

### 4.2 Slot 2 — **상태 전이 규칙 (State Transition Rule)**: 선언 누락 시 run GO 발행 불가

#### (a) 규칙 본문 (proposal)

> **RULE-STATE-2 (run GO issuance precondition):**
> V-3R1 (및 후속 V-N) governance chain 의 state machine 은 다음 전이를 금지한다:
>
> ```
> scope_lock_go (SEALED) ──► run_go_review_report (DRAFT) ──► run_go_receipt (SEAL-1)
>                                                                  ↑
>                                                          이 전이는 허용되지 않음
>                                                          IF run_go_receipt (또는 동등 문서) 가
>                                                          SOL_S1_V3_EXECUTION_MODE 의 명시적
>                                                          선언 protocol (Slot 1) 을 포함하지 않는 경우
> ```
>
> 즉, `run_go_receipt.md` (또는 후속 chain 의 동등 문서) 는 **Slot 1 의 관측 규칙을 본문에 인용/삽입한 상태** 에서만 SEAL 될 수 있다. Slot 1 이 누락된 run GO 는 **legally invalid** 로 간주되며, 해당 GO 로부터 발생한 run 은 retroactively `GOVERNANCE_PROTOCOL_VIOLATION` 으로 분류된다.

#### (b) 적용 layer

- **governance chain state machine layer:** DRAFT → SEALED 전이 점검 지점
- **review 단계:** `run_go_review_report` 에서 Slot 1 인용 여부 mandatory check
- **적용 대상:** 모든 신규 run GO 및 run GO 재발행

#### (c) 위반 시 행동

- SEAL 전 review 에서 Slot 1 인용 누락이 발견되면 → `REVIEW_BLOCKED_ON_SLOT_1_MISSING` → user 에게 명시적 revision 요청
- SEAL 후 소급 발견되면 → 해당 run GO 는 `GOVERNANCE_PROTOCOL_VIOLATION` tag 부여, 파생된 run 결과는 meta-layer `invalid_by_governance_gap` 표시

**참고:** step 8 run (V-3R1) 은 **이 규칙이 없었기 때문에** 발생한 것이며, 소급 invalidation 대상이 아니다 — chain A FAIL (CORRECTIVE_RED_STOP) 판정이 이미 별도 근거 (3-axis yellow violation) 로 확정되어 있고, chain B SEAL-1 에서 governance_gap finding 이 binding 되어 있으므로 이중 처벌이 되지 않는다. 본 규칙은 **미래 run GO 에만 적용** 된다.

#### (d) 삽입 위치 제안 (문서 레이어)

| 대상 문서 | 삽입 위치 | 삽입 내용 |
|---|---|---|
| `sol_s1_v3r1_run_go_review_report.md` template 부분 | 기존 review checklist | "Slot 1 인용 여부 mandatory check" 항목 추가 |
| 새 문서 `sol_s1_v3_governance_state_machine.md` (권고) | 신규 작성 | 위 state transition 규칙을 state machine diagram 으로 명문화 |

---

### 4.3 Slot 3 — **실행 제한 규칙 (Execution Limit Rule)**: dual env var mandatory

#### (a) 규칙 본문 (proposal)

> **RULE-EXEC-3 (dual env var mandate):**
> `python scripts/sol_s1_v3_shadow_run.py --run` (또는 후속 run script 의 equivalent) 의 **모든** 실행은 다음 두 환경 변수가 **동시에** 설정된 상태에서만 legally authorized 된다:
>
> 1. `SOL_S1_V3_RUN_AUTHORIZED = v3_run_go_granted`
> 2. `SOL_S1_V3_EXECUTION_MODE ∈ {realtime_shadow, historical_replay}`
>
> **두 변수 중 단 하나라도 누락** 되거나 무효 값이면, run 은 **실행 금지** 된다. 이는 `RULE-OBS-1` 의 declaration 요건 + `dual-lock run guard` (기존 `SOL_S1_V3_RUN_AUTHORIZED` 잠금 + CLI `--run` flag) 의 확장이다.
>
> 즉, 기존 dual-lock (CLI flag + `SOL_S1_V3_RUN_AUTHORIZED`) 는 **triple-lock (CLI flag + `SOL_S1_V3_RUN_AUTHORIZED` + `SOL_S1_V3_EXECUTION_MODE`)** 으로 확장된다.

#### (b) 적용 layer

- **runner pre-flight layer:** run 시작 직전 환경 검사 (protocol level)
- **governance 감사 layer:** 사후 receipt 검사에서 두 변수의 declared value 출처 witness 요구
- **적용 대상:** V-3R1 및 후속 V-N 모든 run

#### (c) 위반 시 행동

| 결함 상태 | 행동 |
|---|---|
| `SOL_S1_V3_RUN_AUTHORIZED` 누락 | run 금지 (기존 규칙, 불변) |
| `SOL_S1_V3_EXECUTION_MODE` 누락 | run 금지 (**신규 규칙**) |
| 두 변수 모두 누락 | run 금지 |
| `SOL_S1_V3_EXECUTION_MODE` 값이 `{realtime_shadow, historical_replay}` 외 | run 금지 (코드 레벨에서는 현재 ambiguous 반환; governance 는 이를 violation 으로 선언) |

**implementation note:** 실제 runner 에서의 pre-flight 검사 **코드 추가** 는 별도 code modification chain 의 scope 이다. 본 proposal 은 규칙을 **문서 layer 에서만** 고정한다. 코드 반영은 별도 user GO 가 선행되어야 한다.

#### (d) 삽입 위치 제안 (문서 레이어)

| 대상 문서 | 삽입 위치 | 삽입 내용 |
|---|---|---|
| `sol_s1_v3r1_run_go_receipt.md` (재발행본) | dual-lock 규칙 섹션 | dual-lock → triple-lock 확장 명시 |
| `sol_s1_v3_design.md` (design layer) | execution guard 섹션 | triple-lock 규칙을 design constraint 로 고정 |
| 새 문서 `sol_s1_v3_execution_mode_protocol.md` (권고) | 신규 작성 | Slot 3 전문 |

---

### 4.4 Slot 4 — **헌법/거버넌스 제한 규칙 (Constitutional Rule)**: runner 독자 판단 금지

#### (a) 규칙 본문 (proposal)

> **RULE-CONSTITUTIONAL-4 (runner scope of authority):**
> runner (human operator 또는 automated agent) 는 **governance 문서가 명시적으로 지시하지 않은** 환경 변수 / CLI flag / config 값을 **독자 판단으로 설정할 권한이 없다**.
>
> 이는 특히 다음을 포함한다:
> - governance 가 명시하지 않은 `SOL_S1_V3_EXECUTION_MODE` 값을 runner 가 임의로 선택할 수 없다. 해당 값은 **run GO 문서 본문에서 명시적으로 선언** 되어야 하며, runner 는 **선언된 값만 그대로 환경에 설정** 할 수 있다.
> - governance 가 명시하지 않은 새 env var 를 runner 가 독자 도입할 수 없다.
> - governance 가 명시하지 않은 CLI flag 조합을 runner 가 독자 구성할 수 없다.
>
> 이 규칙의 **존재 이유**: chain B SEAL-1 의 governance_gap finding 은 **runner 의 비난 대상이 아니다**. runner 가 step 8 run 시점에 `SOL_S1_V3_EXECUTION_MODE` 를 설정하지 않은 것은, governance 가 해당 env var 를 명시하지 않았기 때문이며, runner 가 이를 "알아서" 설정했다면 **오히려 헌법 위반** 이었을 것이다. 본 규칙은 그러한 "알아서" 행동이 **미래에도 금지** 됨을 명문화한다.

#### (b) 적용 layer

- **governance 헌법 layer:** 전체 V-3R1 계열 및 후속 V-N 의 runner authority boundary
- **runner 역할 정의:** runner 는 "governance 명시 → 그대로 반영" 의 transparent relay 역할만 수행
- **적용 대상:** human operator + automated agent (claude-code 세션 포함)

#### (c) 위반 시 행동

| 상황 | 행동 |
|---|---|
| runner 가 governance 미명시 env var 를 독자 설정 | 해당 run 은 `CONSTITUTIONAL_VIOLATION` 으로 분류, 결과 소급 invalid |
| runner 가 governance 미명시 flag 를 독자 추가 | 동일 |
| runner 가 "효율 / 편의 / 추정" 을 근거로 값 선택 | 금지 — runner 는 추정 권한이 없음 |
| governance 가 모호할 경우 | runner 는 **멈추고** user clarification 을 요청해야 하며, 독자 판단으로 보완해서는 안 됨 |

**implementation note:** 이 규칙은 `auto_advance = forbidden` 원칙의 **runner-level 확장** 이다. `auto_advance` 는 governance chain 의 state 전이 차원이고, RULE-CONSTITUTIONAL-4 는 runner 의 value injection 차원이다. 두 규칙은 **상호 보완** 관계.

#### (d) 삽입 위치 제안 (문서 레이어)

| 대상 문서 | 삽입 위치 | 삽입 내용 |
|---|---|---|
| `sol_s1_v3_design.md` (design layer 최상단 governance 원칙) | governance 헌법 섹션 | Slot 4 전문 — runner authority boundary 정의 |
| 새 문서 `sol_s1_v3_governance_constitution.md` (권고) | 신규 작성 | 4 개 slot + `auto_advance = forbidden` + dual-lock doctrine 을 통합한 governance 헌법 |
| `CLAUDE.md` project-level (권고) | 기존 "CR-046 Current State" 근처 | runner authority boundary 를 project-wide 원칙으로 promote |

---

## §4.5 4-Slot 상호 관계 (integrity witness)

| slot | 역할 | 관계 |
|---|---|---|
| 1 관측 규칙 | declaration mandate | **전제** — Slot 2/3/4 의 근거 |
| 2 상태 전이 규칙 | issuance guard | Slot 1 의 **검증 게이트** |
| 3 실행 제한 규칙 | execution guard | Slot 1 의 **운영 게이트** |
| 4 헌법 규칙 | authority boundary | Slot 1/2/3 의 **의미론적 근거** (왜 runner 가 독자 설정할 수 없는지) |

4 개 slot 은 **상호 독립적이지 않으며**, 전부 같이 가야 한다. Slot 1 만 있고 Slot 2 가 없으면 런타임에 강제되지 않는다. Slot 1+2 만 있고 Slot 4 가 없으면 runner 가 "알아서" 설정하는 loophole 이 남는다. 4 개 slot 전부가 함께 **governance_gap** 을 닫는다.

---

## §5 Proposed Template Diffs (document-layer only, NOT EXECUTED)

본 §5 는 run GO 템플릿 및 governance protocol 문서에 **삽입될 수 있는** 변경사항을 inline 으로 기술한다. **실제 파일 수정은 본 DRAFT 에서 수행되지 않는다.**

### 5.1 Proposed diff A — `sol_s1_v3r1_run_go_receipt.md` (재발행본)

**위치:** 기존 env var 선언 섹션

**현재 (chain B SEAL-1 §5.2 에 인용된 run_go_review_report.md line 318):**
```
- env var : SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted
- env var set timing : run GO 문서가 SEALED 된 직후에만
```

**제안 변경 (proposed, not applied):**
```
- env var (1/2) : SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted
- env var (2/2) : SOL_S1_V3_EXECUTION_MODE=<declared_value>
  - legal domain : {realtime_shadow, historical_replay}
  - declared by : this run GO document body (explicit declaration required)
  - declared value for this run GO : <to be filled by user at SEAL time>
- env var set timing : run GO 문서가 SEALED 된 직후에만, 두 변수를 동시에
- triple-lock precondition :
  1) CLI flag `--run` 존재
  2) SOL_S1_V3_RUN_AUTHORIZED=v3_run_go_granted 설정
  3) SOL_S1_V3_EXECUTION_MODE ∈ {realtime_shadow, historical_replay} 설정
  위 3 조건 중 하나라도 누락 시 run 금지 (RULE-EXEC-3)
```

### 5.2 Proposed diff B — 새 문서 `sol_s1_v3_execution_mode_protocol.md` (신규, 권고)

**상태:** 권고 (본 DRAFT 는 생성하지 않음)

**골격 (proposed skeleton):**
```
# SOL S-1 V-3 Execution Mode Protocol (PROPOSED)
## §1 Applicability
## §2 RULE-OBS-1 (observation rule)      ← Slot 1 전문
## §3 RULE-STATE-2 (state transition)     ← Slot 2 전문
## §4 RULE-EXEC-3 (execution limit)       ← Slot 3 전문
## §5 RULE-CONSTITUTIONAL-4 (runner)      ← Slot 4 전문
## §6 Integration with existing dual-lock doctrine
## §7 Audit trail requirements
## §8 Effective date & retroactivity (미래 run 만; step 8 run 은 소급 면제)
```

### 5.3 Proposed diff C — `sol_s1_v3_design.md` 헌법 섹션 (권고)

**위치:** design layer 최상단 governance 원칙 섹션

**제안 추가:**
```
### runner authority boundary (RULE-CONSTITUTIONAL-4)
runner (human operator 또는 automated agent) 는 governance 문서가
명시적으로 지시하지 않은 환경 변수 / CLI flag / config 값을 독자 판단으로
설정할 권한이 없다. [Slot 4 전문 인용]
```

### 5.4 본 DRAFT 가 수행하는 것 vs 수행하지 않는 것

| 항목 | 본 DRAFT 에서 수행? |
|---|---|
| proposed diff 를 **문서 내부에 inline 기재** | **YES** (§5.1, §5.2, §5.3) |
| 실제 `sol_s1_v3r1_run_go_receipt.md` 파일 수정 | **NO** (chain B SEAL-1 이후 sealed, 재발행은 별도 chain) |
| 신규 문서 `sol_s1_v3_execution_mode_protocol.md` 파일 생성 | **NO** (권고만, 별도 user GO 필요) |
| `sol_s1_v3_design.md` 수정 | **NO** (SEALED 문서, 재작성은 별도 chain) |
| `CLAUDE.md` 수정 | **NO** (project-level 변경은 별도 GO 필요) |

---

## §6 Forbidden Axes (this DRAFT does NOT do any of these)

| # | 금지 항목 | 상태 (post this DRAFT) |
|---|---|---|
| 1 | frozen 스크립트 (`sol_s1_v3_shadow_run.py`) 수정 | NOT PERFORMED (sha256 그대로) |
| 2 | 추가 `--run` 호출 | NOT PERFORMED |
| 3 | `SOL_S1_V3_RUN_AUTHORIZED` 설정 | NOT PERFORMED (env var NOT SET) |
| 4 | `SOL_S1_V3_EXECUTION_MODE` **실제** 설정 | NOT PERFORMED (env var NOT SET — proposal only) |
| 5 | baseline (64.3 / 35.7 / 70.9) 값 수정 | NOT PERFORMED |
| 6 | chain C (baseline re-verification) 자동 개시 | NOT PERFORMED (`SEPARATE_CHAIN_NOT_OPENED` 유지) |
| 7 | 부모 chain (SOL S-1 root-cause chain) 확장 | NOT PERFORMED |
| 8 | corrective sub-chain (chain A) 재오픈 | NOT PERFORMED (SEAL-1 binding ACTIVE 유지) |
| 9 | chain B SEAL-1 문서 수정 | NOT PERFORMED (sha256 `865336ea…0ddc` 그대로) |
| 10 | chain B 의 root-cause finding (governance_gap) 뒤집기 | NOT PERFORMED (finding 은 전제로 상속) |
| 11 | step 9 SEAL-1 run_completion_receipt 의 FAIL 판정 수정 | NOT PERFORMED (locked inherit) |
| 12 | chain A step 11 SEAL-1 closure triplet 수정 | NOT PERFORMED |
| 13 | run GO 템플릿 **실제** 파일 수정 | NOT PERFORMED (§5 는 inline proposal 만, actual edit 아님) |
| 14 | 신규 `sol_s1_v3_execution_mode_protocol.md` 파일 실제 생성 | NOT PERFORMED (권고만) |
| 15 | `sol_s1_v3_design.md` 수정 | NOT PERFORMED |
| 16 | `CLAUDE.md` 수정 | NOT PERFORMED |
| 17 | count contract 2종 (28/20) 변경 | NOT PERFORMED |
| 18 | strategy 소스 / production 코드 수정 | NOT PERFORMED |
| 19 | auto_advance 활성화 | NOT PERFORMED (forbidden 유지) |
| 20 | 본 DRAFT 의 자동 SEAL 전환 | NOT PERFORMED (SEAL 은 별도 user GO 필요) |
| 21 | 전략 성패 선언 | NOT PERFORMED (chain scope 밖) |
| 22 | `execution_mode` 의 두 legal value 중 하나를 미리 고정 | NOT PERFORMED (proposal 은 두 값 모두를 domain 으로 유지) |
| 23 | 12 prior artifact (chain B SEAL-1 포함 13) 중 아무것이나 수정 | NOT PERFORMED |

---

## §7 Count Contract 2종 Invariance Witness

| 지표 | 값 | 원 고정 시점 | grp_chain_step_1 시점 |
|---|---|---|---|
| physical count | 28 | step 3 (scope_lock_go.md) | 28 (unchanged) |
| actual count | 20 | step 3 (scope_lock_go.md) | 20 (unchanged) |

step 3 → grp_chain_step_1 동안 **mutation 0 건**. 본 DRAFT 는 이 값을 참조도 하지 않으며 수정도 하지 않는다.

---

## §8 DRAFT Integrity Self-Declaration

- document_state: DRAFT
- governance_wrapper_format: grp_chain_opening_proposal_v1
- grp_chain_step_1_complete: true
- grp_chain_seal_status: NOT_YET_SEALED (awaiting explicit user SEAL GO)
- analysis_mode: document_layer_design_only
- files_read_during_analysis: (none new — 전부 chain B SEAL-1 에서 이미 read 됨)
- files_modified_during_draft: 1 (본 DRAFT 파일 생성만)
- frozen_script_sha256: `94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` (unchanged, not touched)
- prior_13_artifacts_status: UNCHANGED (cross-verified pre-draft; will be re-verified post-draft)
- env_SOL_S1_V3_RUN_AUTHORIZED: NOT SET
- env_SOL_S1_V3_EXECUTION_MODE: NOT SET
- baseline_values_referenced: 64.3 / 35.7 / 70.9 (read-only citation, no mutation)
- chain_a_closure_triplet: UNTOUCHED (CLOSED / FAIL / NO_V4_UNLOCK)
- chain_b_seal_1_binding: UNTOUCHED (governance_gap finding BINDING ACTIVE)
- parent_chain_status: NOT CLOSED BY THIS DRAFT
- chain_c_status: SEPARATE_CHAIN_NOT_OPENED
- run_go_reissue_chain_status: NOT_OPENED
- count_contract_2종: 28 / 20 (unchanged since step 3)
- draft_1_post_creation_sha256: *(reported externally in the grp_chain opening report — self-referential hash embedding intentionally avoided)*

---

## §9 Global State Declaration (post grp_chain_step_1 DRAFT creation)

```
GLOBAL STATE                                      = STANDBY
V-3R1 RUN STATE                                   = EXECUTED_ONCE (frozen)
V-3R1 RUN PASS/FAIL JUDGMENT                      = FAIL (CORRECTIVE_RED_STOP) [locked]
V-3R1 CORRECTIVE SUB-CHAIN (chain A)              = CLOSED / FAIL / NO_V4_UNLOCK (step 11 SEAL-1, binding ACTIVE)
CHAIN B (execution_mode root-cause)               = SEALED (chain_b_step_2 SEAL-1, binding ACTIVE)
CHAIN B ROOT-CAUSE FINDING                        = governance_gap [BINDING ACTIVE, inherited as premise]
GOVERNANCE REMEDIATION PROPOSAL CHAIN — step 1    = DRAFT (grp_chain_step_1, this document, NOT_YET_SEALED)
CHAIN C (baseline reverification)                 = SEPARATE_CHAIN_NOT_OPENED
RUN GO REISSUE CHAIN (future)                     = NOT_OPENED
PARENT CHAIN (SOL S-1 root-cause chain)           = NOT CLOSED, NOT EXTENDED BY THIS DRAFT
V-4 UNLOCK                                        = NOT AUTHORIZED
ATTEMPT_2                                         = NOT AUTHORIZED
ADDITIONAL_RUN_INVOCATION                         = NOT AUTHORIZED
SOL_S1_V3_RUN_AUTHORIZED                          = NOT SET
SOL_S1_V3_EXECUTION_MODE                          = NOT SET
EXECUTION_RESUMPTION_AUTHORITY                    = NOT GRANTED BY THIS DRAFT
CODE_MUTATION_AUTHORITY                           = NOT GRANTED BY THIS DRAFT
ACTUAL_RUN_GO_TEMPLATE_EDIT_AUTHORITY             = NOT GRANTED BY THIS DRAFT
NEW_PROTOCOL_FILE_CREATION_AUTHORITY              = NOT GRANTED BY THIS DRAFT
DESIGN_MD_EDIT_AUTHORITY                          = NOT GRANTED BY THIS DRAFT
CLAUDE_MD_EDIT_AUTHORITY                          = NOT GRANTED BY THIS DRAFT
count_contract_2종                                = 28 / 20 (unchanged since step 3)
auto_advance                                      = forbidden
next_legal_action                                 = user decision (SEAL this DRAFT, revise, or maintain STANDBY)
```

---

## §10 Next Legal Actions (reference only — user decision required)

본 DRAFT 이후 합법적인 다음 행동 후보:

| 후보 | 설명 | 필요 사전조건 |
|---|---|---|
| a | 본 grp_chain DRAFT 의 검수 및 SEAL | user SEAL GO |
| b | 본 grp_chain DRAFT 의 내용 수정 요청 | user revision instruction |
| c | grp_chain SEAL 후 별도 chain — 실제 run GO 템플릿 재발행 | 별도 user GO + 새로운 run GO 재발행 체인 전체 |
| d | grp_chain SEAL 후 별도 chain — 신규 `sol_s1_v3_execution_mode_protocol.md` 파일 생성 | 별도 user GO |
| e | grp_chain SEAL 후 별도 chain — `sol_s1_v3_design.md` 헌법 섹션 보강 | 별도 user GO |
| f | grp_chain SEAL 후 별도 chain — `CLAUDE.md` project-level 보강 | 별도 user GO |
| g | chain C (baseline re-verification) 개시 | 별도 user GO (chain B 및 grp_chain 결과와 독립 가능) |
| h | STANDBY 유지 | 지시 없음 시 기본 |

본 DRAFT 는 a~h 중 **어떤 것도 권고하거나 자동 개시하지 않는다**.

---

## §11 Revision Log

- **DRAFT-1** (2026-04-11, grp_chain_step_1) — initial governance remediation proposal DRAFT created per user step 14 directive. 4 mandatory slots (observation / state transition / execution limit / constitutional) fully specified in §4. Proposed template diffs enumerated in §5 at inline-description level only (no actual file modifications). 0 mutation on 13 prior artifacts. 0 mutation on frozen script. 0 additional run invocations. 0 env var changes (both NOT SET). chain A SEAL-1 closure triplet untouched. chain B SEAL-1 binding untouched. chain C NOT opened. parent chain NOT extended. run GO re-issuance chain NOT opened. `sol_s1_v3_design.md` NOT modified. `CLAUDE.md` NOT modified. No new protocol file created. count_contract_2종 unchanged at 28/20. auto_advance remains forbidden. DRAFT-1 post-creation sha256 is reported externally in the grp_chain opening report (self-referential hash embedding intentionally avoided).
