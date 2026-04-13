# SOL S-1 V-3 Execution Mode Protocol (DRAFT)

**document_state:** DRAFT
**document_type:** execution_mode_protocol
**chain:** `grp_chain_impl_1_document_reissuance_chain`
**issued_at:** 2026-04-11
**issuer:** `grp_chain_impl_1_document_reissuance_chain_step_1_2026_04_11`
**authority_source:** `sol_s1_v3r1_governance_remediation_proposal_draft.md` (SEALED externally, sha256 `06e0303beeac27058d23bd351988e31b9cdedca17bc2bf9cbd1b9b1da3b13a9c`)
**review_status:** NOT_YET_REVIEWED
**seal_status:** NOT_YET_SEALED (SEAL requires a separate user GO)

**scope_of_this_document:** document-layer codification of 4 mandatory slots (Slot 1/2/3/4) from grp_chain DRAFT-1 §4, integrated with dual-lock → triple-lock doctrine. 본 문서는 새 protocol 규칙을 **문서 층에서만** 고정한다. 코드 반영, env var 설정, CLI flag 조합 변경, run authorization, V-4 unlock 은 본 문서에 의해 승인되지 않는다.

---

## §0 Scope Lock

```
ISSUANCE_OF_THIS_DOCUMENT_GRANTS_EXECUTION        = false
ENV_VAR_SET_BY_THIS_ISSUANCE                      = false
CLI_FLAG_RUN_TRIGGERED_BY_THIS_ISSUANCE           = false
ACTUAL_RUN_STARTED_BY_THIS_ISSUANCE               = false
SEALED_DOCUMENT_MUTATION_IN_THIS_ISSUANCE         = false
TARGET_SCRIPT_MUTATION_IN_THIS_ISSUANCE           = false
V4_UNLOCK_BASIS_ALLOWED                           = false
ATTEMPT_2_AUTHORIZATION_IMPLIED                   = false
CODE_PATH_BEHAVIOR_CHANGED_BY_THIS_ISSUANCE       = false
TEST_SUITE_MUTATED_BY_THIS_ISSUANCE                = false
CHAIN_A_BINDING_RELEASED_BY_THIS_ISSUANCE         = false
PARENT_DEFER_RELEASED_BY_THIS_ISSUANCE            = false
AUTO_ADVANCE                                      = forbidden
DOCUMENT_STATE_SET_BY_THIS_FILE                   = DRAFT
```

본 문서는 **문서 층 protocol 선언** 이며, 어떤 runtime 동작도 직접 유발하지 않는다.

---

## §1 Applicability

| 항목 | 값 |
|------|-----|
| 적용 범위 | V-3R1 계열 및 후속 모든 V-N shadow/live run |
| 적용 layer | governance 문서, pre-run checklist, review report, runner pre-flight |
| 적용 대상 | human operator + automated agent (claude-code 세션 포함) |
| 소급 적용 | **금지**. 본 protocol 은 미래 run 에만 적용된다. step 8 run (V-3R1) 은 Chain B SEAL-1 의 `governance_gap` finding 으로 이미 별도 처리되어 있으며, 본 protocol 은 소급 invalidation 의 근거가 되지 않는다. |

### 1.1 Governance Origin

본 protocol 의 4 개 slot 은 전부 `sol_s1_v3r1_governance_remediation_proposal_draft.md` §4.1~§4.4 에서 원문 인용된다. 원문은 SEALED externally (sha256 `06e0303b…3a9c`) 이므로 본 문서는 **인용만** 하며, 원문 수정은 수행하지 않는다.

### 1.2 상호 의존성 선언 (§4.5 계승)

| slot | 역할 | 의존 관계 |
|------|------|----------|
| 1 RULE-OBS-1 | declaration mandate | **전제** — 2/3/4 의 근거 |
| 2 RULE-STATE-2 | issuance guard | 1 의 검증 게이트 |
| 3 RULE-EXEC-3 | execution guard | 1 의 운영 게이트 |
| 4 RULE-CONSTITUTIONAL-4 | authority boundary | 1/2/3 의 의미론적 근거 |

**4 slots 은 원자적 단위로만 적용되며, partial implementation 은 loophole 을 만든다.**

---

## §2 RULE-OBS-1 (Observation Rule) — Slot 1 전문

> **RULE-OBS-1 (execution_mode declaration mandate):**
> 모든 V-3R1 (및 후속 V-N) run 은 `--run` 호출 **이전에** 반드시 다음 두 환경 변수가 모두 설정되어 있어야 한다:
> - `SOL_S1_V3_RUN_AUTHORIZED = v3_run_go_granted`
> - `SOL_S1_V3_EXECUTION_MODE ∈ {realtime_shadow, historical_replay}`
>
> 두 변수의 존재는 run GO 문서 SEAL-1 의 **정의된 사전조건** 으로 간주된다. 두 번째 변수의 값은 **declared value** 로 간주되며, 코드의 `determine_execution_mode` 함수가 `declared_value` 로 직접 수신한다.
>
> `SOL_S1_V3_EXECUTION_MODE` 의 값은 `{realtime_shadow, historical_replay}` 중 **정확히 하나** 여야 한다. 빈 문자열, 공백, 다른 값, `ambiguous` 는 **선언으로 인정되지 않는다**.

### 2.1 적용 layer

- governance 문서 layer: run GO 템플릿, run GO 재발행 receipt, pre-run checklist
- 관측 단계: run GO SEAL 직후부터 `--run` 호출 시점까지
- 적용 대상: V-3R1 계열 및 후속 모든 shadow / live run

### 2.2 위반 시 행동

| 결함 상태 | 행동 |
|---|---|
| `SOL_S1_V3_EXECUTION_MODE` 미설정 상태에서 `--run` 호출 | run 금지 (§4 Slot 3 trigger) |
| 값이 `{realtime_shadow, historical_replay}` 외 | run 금지 + governance 위반 기록 (현재 코드는 `ambiguous` 반환; governance layer 가 violation 선언) |
| 빈 문자열 / 공백 | 선언 미존재로 간주, run 금지 |

### 2.3 declared_value 정의

`SOL_S1_V3_EXECUTION_MODE` 의 값은 **run GO 문서 본문에서 명시 선언된 값** 을 그대로 복사한 것이어야 한다. 이는 Slot 4 의 runner authority boundary 와 직접 연결된다.

---

## §3 RULE-STATE-2 (State Transition Rule) — Slot 2 전문

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

### 3.1 적용 layer

- governance chain state machine layer: DRAFT → SEALED 전이 점검 지점
- review 단계: `run_go_review_report` 에서 Slot 1 인용 여부 mandatory check
- 적용 대상: 모든 신규 run GO 및 run GO 재발행

### 3.2 위반 시 행동

- SEAL 전 review 에서 Slot 1 인용 누락 발견 → `REVIEW_BLOCKED_ON_SLOT_1_MISSING` → user 에게 명시 revision 요청
- SEAL 후 소급 발견 → 해당 run GO 에 `GOVERNANCE_PROTOCOL_VIOLATION` tag 부여, 파생 run 결과는 meta-layer `invalid_by_governance_gap` 표시

### 3.3 step 8 run (V-3R1) 면제 선언

step 8 run (V-3R1) 은 본 규칙이 **존재하지 않았기 때문에** 발생했으며, 소급 invalidation 대상이 아니다. Chain A FAIL (CORRECTIVE_RED_STOP) 판정은 이미 3-axis yellow violation 을 근거로 독립 확정되어 있고, Chain B SEAL-1 에서 governance_gap finding 이 binding 되어 있으므로 이중 처벌이 되지 않는다.

---

## §4 RULE-EXEC-3 (Execution Limit Rule) — Slot 3 전문

> **RULE-EXEC-3 (dual env var mandate):**
> `python scripts/sol_s1_v3_shadow_run.py --run` (또는 후속 run script 의 equivalent) 의 **모든** 실행은 다음 두 환경 변수가 **동시에** 설정된 상태에서만 legally authorized 된다:
>
> 1. `SOL_S1_V3_RUN_AUTHORIZED = v3_run_go_granted`
> 2. `SOL_S1_V3_EXECUTION_MODE ∈ {realtime_shadow, historical_replay}`
>
> **두 변수 중 단 하나라도 누락** 되거나 무효 값이면, run 은 **실행 금지** 된다. 이는 `RULE-OBS-1` 의 declaration 요건 + `dual-lock run guard` (기존 `SOL_S1_V3_RUN_AUTHORIZED` 잠금 + CLI `--run` flag) 의 확장이다.
>
> 즉, 기존 dual-lock (CLI flag + `SOL_S1_V3_RUN_AUTHORIZED`) 는 **triple-lock (CLI flag + `SOL_S1_V3_RUN_AUTHORIZED` + `SOL_S1_V3_EXECUTION_MODE`)** 으로 확장된다.

### 4.1 적용 layer

- runner pre-flight layer: run 시작 직전 환경 검사 (protocol level)
- governance 감사 layer: 사후 receipt 검사에서 두 변수의 declared value 출처 witness 요구
- 적용 대상: V-3R1 및 후속 V-N 모든 run

### 4.2 위반 시 행동 (상세 표)

| 결함 상태 | 행동 |
|---|---|
| `SOL_S1_V3_RUN_AUTHORIZED` 누락 | run 금지 (기존 규칙, 불변) |
| `SOL_S1_V3_EXECUTION_MODE` 누락 | run 금지 (**신규 규칙**) |
| 두 변수 모두 누락 | run 금지 |
| `SOL_S1_V3_EXECUTION_MODE` 값이 legal domain 외 | run 금지 (코드 레벨에서는 현재 `ambiguous` 반환; governance 는 violation 선언) |
| CLI `--run` flag 누락 | run 금지 (물리 lock 1) |
| `--run` + 두 env var 모두 존재 + 값 유효 | run legally authorized (단, 별도 run-GO SEAL 이 문서 층에서 사전 완료되어 있어야 함) |

### 4.3 Triple-Lock 구조

```
legal_run := CLI_FLAG_RUN
           ∧ env(SOL_S1_V3_RUN_AUTHORIZED) == "v3_run_go_granted"
           ∧ env(SOL_S1_V3_EXECUTION_MODE) ∈ {"realtime_shadow", "historical_replay"}
           ∧ run_go_receipt.document_state == "SEALED"
           ∧ run_go_receipt.body contains RULE-OBS-1 citation
```

### 4.4 implementation note (code-layer 경계 선언)

실제 runner 에서의 pre-flight 검사 **코드 추가** 는 본 protocol 에 의해 **승인되지 않는다**. 본 protocol 은 규칙을 **문서 층에서만** 고정한다. 코드 반영은 별도 user GO 가 선행되어야 하며, 해당 구현은 IMPL-2 체인의 scope 이다 (별도 raw GO 필요).

---

## §5 RULE-CONSTITUTIONAL-4 (Runner Authority Boundary) — Slot 4 전문

> **RULE-CONSTITUTIONAL-4 (runner scope of authority):**
> runner (human operator 또는 automated agent) 는 **governance 문서가 명시적으로 지시하지 않은** 환경 변수 / CLI flag / config 값을 **독자 판단으로 설정할 권한이 없다**.
>
> 이는 특히 다음을 포함한다:
> - governance 가 명시하지 않은 `SOL_S1_V3_EXECUTION_MODE` 값을 runner 가 임의로 선택할 수 없다. 해당 값은 **run GO 문서 본문에서 명시적으로 선언** 되어야 하며, runner 는 **선언된 값만 그대로 환경에 설정** 할 수 있다.
> - governance 가 명시하지 않은 새 env var 를 runner 가 독자 도입할 수 없다.
> - governance 가 명시하지 않은 CLI flag 조합을 runner 가 독자 구성할 수 없다.
>
> 이 규칙의 **존재 이유**: Chain B SEAL-1 의 governance_gap finding 은 **runner 의 비난 대상이 아니다**. runner 가 step 8 run 시점에 `SOL_S1_V3_EXECUTION_MODE` 를 설정하지 않은 것은, governance 가 해당 env var 를 명시하지 않았기 때문이며, runner 가 이를 "알아서" 설정했다면 **오히려 헌법 위반** 이었을 것이다. 본 규칙은 그러한 "알아서" 행동이 **미래에도 금지** 됨을 명문화한다.

### 5.1 적용 layer

- governance 헌법 layer: 전체 V-3R1 계열 및 후속 V-N 의 runner authority boundary
- runner 역할 정의: runner 는 "governance 명시 → 그대로 반영" 의 transparent relay 역할만 수행
- 적용 대상: human operator + automated agent (claude-code 세션 포함)

### 5.2 위반 시 행동

| 상황 | 행동 |
|---|---|
| runner 가 governance 미명시 env var 를 독자 설정 | 해당 run 은 `CONSTITUTIONAL_VIOLATION` 으로 분류, 결과 소급 invalid |
| runner 가 governance 미명시 flag 를 독자 추가 | 동일 |
| runner 가 "효율 / 편의 / 추정" 근거로 값 선택 | 금지 — runner 는 추정 권한이 없음 |
| governance 가 모호할 경우 | runner 는 **멈추고** user clarification 을 요청해야 하며, 독자 판단으로 보완해서는 안 됨 |

### 5.3 auto_advance 와의 상호 보완 관계

`auto_advance = forbidden` 은 governance chain 의 **state 전이 차원** 이다. RULE-CONSTITUTIONAL-4 는 runner 의 **value injection 차원** 이다. 두 규칙은 **상호 보완** 관계이며, 한쪽만 있으면 loophole 이 발생한다:

- `auto_advance = forbidden` 만 있을 때: runner 가 governance 미명시 값을 독자 주입하여 state 전이 없이 runtime 행동을 변경할 수 있음.
- RULE-CONSTITUTIONAL-4 만 있을 때: governance chain 이 스스로 state 를 전이시켜 runner 개입 없이 행동이 바뀔 수 있음.

두 규칙이 함께 적용될 때만 runner-governance 경계가 완전히 닫힌다.

---

## §6 Integration with Existing Dual-Lock Doctrine

### 6.1 기존 dual-lock

| lock | 대상 | 기존 상태 |
|------|------|----------|
| Lock 1 | CLI flag `--run` | 이전부터 존재 |
| Lock 2 | env var `SOL_S1_V3_RUN_AUTHORIZED` | 이전부터 존재 |

### 6.2 triple-lock 확장

| lock | 대상 | 본 protocol 추가 | layer |
|------|------|-----------------|-------|
| Lock 1 | CLI flag `--run` | 불변 | 물리 (코드) |
| Lock 2 | env var `SOL_S1_V3_RUN_AUTHORIZED` | 불변 | 물리 (코드) |
| **Lock 3** | env var `SOL_S1_V3_EXECUTION_MODE` | **신규** | 물리 (코드) + 거버넌스 (문서 인용) 이중 |

### 6.3 전환 경계

- **문서 층:** 본 protocol 이 즉시 triple-lock 을 선언한다 (문서 내 규칙 존재).
- **코드 층:** 현재 `scripts/sol_s1_v3_shadow_run.py` 는 dual-lock 만 구현. triple-lock 의 Lock 3 code-layer 구현은 IMPL-2 체인 범위 (별도 raw GO).
- **간극 관리:** 문서 층 triple-lock 선언 ↔ 코드 층 dual-lock 실태 간의 간극은 **IMPL-2 완료 전까지 모든 run 발행을 차단** 하는 방식으로 안전 확보된다. 즉, 코드 층이 따라잡기 전까지는 run GO 발행 자체가 legally invalid 하다.

---

## §7 Audit Trail Requirements

### 7.1 pre-run (run GO 발행 시점)

| 항목 | 요구 증거 |
|------|----------|
| Slot 1 citation in run GO body | run_go_receipt.md 본문에 RULE-OBS-1 원문 인용 포함 |
| Slot 3 citation in run GO body | run_go_receipt.md 본문에 RULE-EXEC-3 원문 인용 포함 |
| declared_value 선언 | run_go_receipt.md 본문에 `SOL_S1_V3_EXECUTION_MODE` 의 declared value 명시 |
| review checklist PASS | run_go_review_report.md 에 Slot 1/3 citation mandatory check PASS 기록 |
| SEAL precondition | DRAFT → SEAL 전이 전 review ACCEPT 필수 |

### 7.2 at-run (run 실행 시점)

| 항목 | 요구 증거 |
|------|----------|
| env var 2종 setting | `SOL_S1_V3_RUN_AUTHORIZED` + `SOL_S1_V3_EXECUTION_MODE` 둘 다 declared_value 와 일치 |
| CLI flag | `--run` 존재 |
| runner identity | set timing (SEAL 직후), set source (governance doc) 기록 |
| triple-lock 검증 결과 | pre-flight guard pass log |

### 7.3 post-run (run completion 시점)

| 항목 | 요구 증거 |
|------|----------|
| declared_value 출처 witness | run completion receipt 에 declared value + governance doc sha256 기록 |
| triple-lock audit | 세 lock 의 만족 상태 각각 기록 |
| runner authority boundary 준수 | runner 가 독자 값 주입 없음 witness |

### 7.4 audit failure → binding

| audit 단계 | 실패 시 결과 |
|-----------|------------|
| pre-run Slot 1/3 citation 누락 | DRAFT → SEAL 전이 차단 (§3) |
| at-run triple-lock 실패 | run 실행 차단 (§4) |
| post-run witness 누락 | run result `audit_incomplete` tag, 별도 보강 체인 필요 |
| runner authority violation | `CONSTITUTIONAL_VIOLATION` tag, 결과 소급 invalid (§5) |

---

## §8 Effective Date & Retroactivity

### 8.1 Effective Date

본 protocol 은 발행 시점 (`2026-04-11`) 부터 **문서 층에서** 유효하다. 단, 다음 두 가지는 별도 gate 이다:

| gate | 효력 시점 |
|------|----------|
| 문서 층 protocol 선언 | 2026-04-11 (본 발행) |
| 코드 층 triple-lock 구현 | IMPL-2 체인 완료 후 (별도 raw GO 필요) |
| 실제 run 적용 | run-GO 재발행 체인 완료 후 (IMPL/VAL/GOV 전 체인 CLOSED 필수) |

### 8.2 Retroactivity

| 대상 | 소급 적용? |
|------|-----------|
| step 8 run (V-3R1, 2026-04-10) | **NO** — Chain B SEAL-1 의 governance_gap finding 으로 이미 처리됨. 이중 처벌 금지. |
| 향후 모든 V-N run | **YES** — Slot 1/2/3/4 전체가 mandatory precondition |
| Chain A closure triplet (CLOSED/FAIL/NO_V4_UNLOCK) | **NO** — binding 불변 |
| Chain B SEAL-1 finding (governance_gap) | **NO** — finding 불변, 본 protocol 의 전제로 상속 |

### 8.3 retroactive 면제의 한계

본 protocol 의 소급 면제는 **오직 step 8 run 에만 한정** 된다. 본 protocol 발행 이후의 어떤 run 도 면제 대상이 아니다. 본 면제는 **법적 소급 불리 금지** (ex post facto) 원칙과 Chain B SEAL-1 의 binding 을 존중하기 위한 것이며, 미래 run 의 governance 느슨화 근거가 될 수 없다.

---

## §9 Integrity Self-Declaration

- document_state: DRAFT
- document_type: execution_mode_protocol
- chain: `grp_chain_impl_1_document_reissuance_chain`
- authority_source_sha256: `06e0303beeac27058d23bd351988e31b9cdedca17bc2bf9cbd1b9b1da3b13a9c` (grp_chain DRAFT-1 SEALED externally)
- frozen_script_sha256_at_issuance: `94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` (unchanged, not touched)
- env_SOL_S1_V3_RUN_AUTHORIZED: NOT SET
- env_SOL_S1_V3_EXECUTION_MODE: NOT SET
- chain_a_closure_triplet: UNTOUCHED (CLOSED / FAIL / NO_V4_UNLOCK)
- chain_b_seal_1_binding: UNTOUCHED (governance_gap finding BINDING ACTIVE)
- parent_chain_status: ACTIVE-dormant (DEFER) — NOT CLOSED BY THIS DRAFT
- count_contract_2종: 28 / 20 (unchanged since step 3, not referenced for mutation)
- seal_status_of_this_document: NOT_YET_SEALED
- seal_basis: requires separate user SEAL GO
- next_legal_action_for_this_doc: review → ACCEPT → separate SEAL chain

---

## §10 Global State Declaration (post issuance)

```
GLOBAL STATE                                      = STANDBY
GRP_CHAIN DRAFT-1                                 = SEALED (externally, 06e0303b…3a9c, UNCHANGED)
IMPL-1 DOCUMENT REISSUANCE CHAIN                  = IN PROGRESS (this document is 1 of up to 4 artifacts)
IMPL-2 RUNNER SCRIPT FORK CHAIN                   = NOT OPENED
IMPL-3 TEST WRITING CHAIN                         = NOT OPENED
VAL-1 REGRESSION CHAIN                            = NOT OPENED
GOV-1~4 CHAINS                                    = NOT OPENED
RUN-GO REISSUANCE DECISION CHAIN                  = CLOSED (DEFERRED)
RUN-GO REISSUANCE CHAIN                           = NOT OPENED
PARENT CHAIN                                      = ACTIVE-dormant (DEFER)
CHAIN A / B / C                                   = closed / sealed / not-opened
V-4 UNLOCK                                        = NOT AUTHORIZED
SOL_S1_V3_RUN_AUTHORIZED                          = NOT SET
SOL_S1_V3_EXECUTION_MODE                          = NOT SET
CODE_MUTATION_AUTHORITY                           = NOT GRANTED
TEST_MUTATION_AUTHORITY                           = NOT GRANTED
EXISTING_FILE_MUTATION_AUTHORITY                  = NOT GRANTED
SEAL_CREATION_AUTHORITY                           = NOT GRANTED
auto_advance                                      = forbidden
```

---

## §11 Next Legal Actions (reference only)

| 후보 | 설명 | 필요 조건 |
|------|------|----------|
| a | 본 protocol DRAFT 의 검수 및 SEAL | 별도 user SEAL GO |
| b | 본 protocol DRAFT 의 내용 수정 요청 | 별도 user revision GO |
| c | IMPL-2 runner script fork 체인 개시 | 별도 user raw GO |
| d | IMPL-3 test writing 체인 개시 | 별도 user raw GO |
| e | VAL-1 regression 체인 개시 | IMPL-1/2/3 완료 후 별도 raw GO |
| f | GOV-1~4 거버넌스 판단 체인 개시 | 각각 별도 user raw GO (IMPL 과 병렬 가능) |
| g | STANDBY 유지 | 지시 없음 시 기본 |

본 DRAFT 는 a~g 중 **어떤 것도 자동 개시하지 않는다**.

---

## §12 Revision Log

| Rev | Timestamp | Actor | Change Scope |
|-----|-----------|-------|--------------|
| DRAFT-1 | 2026-04-11 | `grp_chain_impl_1_document_reissuance_chain_step_1_2026_04_11` | 최초 DRAFT 발행. §1~§11 작성. 4 slots 전문 인용. SEAL 없음. 기존 파일 0 mutation. |
