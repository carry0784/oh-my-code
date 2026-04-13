# SOL S-1 V-3 Design Addendum — Runner Authority Boundary (DRAFT)

**document_state:** DRAFT
**document_type:** design_addendum
**addendum_target:** `docs/operations/evidence/sol_s1_v3_design.md` (SEALED, **NOT modified by this addendum**)
**chain:** `grp_chain_impl_1_document_reissuance_chain`
**issued_at:** 2026-04-11
**issuer:** `grp_chain_impl_1_document_reissuance_chain_step_2_2026_04_11`
**authority_source:** `sol_s1_v3r1_governance_remediation_proposal_draft.md` §4.4, §5.3 (SEALED externally, sha256 `06e0303beeac27058d23bd351988e31b9cdedca17bc2bf9cbd1b9b1da3b13a9c`)
**review_status:** NOT_YET_REVIEWED
**seal_status:** NOT_YET_SEALED

**scope_of_this_document:** `sol_s1_v3_design.md` 의 governance 원칙 섹션에 **추가 기술** 될 runner authority boundary (RULE-CONSTITUTIONAL-4) 를 별도 addendum 문서로 발행한다. 원본 design.md 는 **SEALED 상태로 불변** 유지되며, 본 addendum 은 companion 문서로 병렬 배치된다.

---

## §0 Scope Lock

```
ISSUANCE_OF_THIS_DOCUMENT_GRANTS_EXECUTION        = false
ORIGINAL_DESIGN_MD_MUTATION_IN_THIS_ISSUANCE      = false
ENV_VAR_SET_BY_THIS_ISSUANCE                      = false
CLI_FLAG_RUN_TRIGGERED_BY_THIS_ISSUANCE           = false
ACTUAL_RUN_STARTED_BY_THIS_ISSUANCE               = false
SEALED_DOCUMENT_MUTATION_IN_THIS_ISSUANCE         = false
TARGET_SCRIPT_MUTATION_IN_THIS_ISSUANCE           = false
V4_UNLOCK_BASIS_ALLOWED                           = false
CODE_PATH_BEHAVIOR_CHANGED_BY_THIS_ISSUANCE       = false
AUTO_ADVANCE                                      = forbidden
DOCUMENT_STATE_SET_BY_THIS_FILE                   = DRAFT
```

본 addendum 은 **문서 층 선언** 이며, 원본 design.md 의 내용이나 무결성에 어떤 영향도 주지 않는다. 원본 design.md 의 sha256 은 본 발행으로 인해 변경되지 않는다.

---

## §1 Addendum Context

### 1.1 Why this addendum instead of modifying design.md directly

| 조건 | 값 |
|------|-----|
| `sol_s1_v3_design.md` 현재 상태 | SEALED |
| SEALED 문서 수정 권한 (IMPL-1 체인 범위) | NOT GRANTED |
| 23 Forbidden Axes (grp_chain §6) 중 #15 "sol_s1_v3_design.md 수정" | NOT PERFORMED (금지) |
| 결론 | 원본 수정 대신 addendum 문서로 병렬 발행 |

### 1.2 Addendum 의 법적 지위

- 본 addendum 은 원본 design.md 의 **companion document** 이다.
- 원본 design.md 와 본 addendum 은 함께 읽혀야 한다.
- 원본 design.md 에 명시된 설계 결정과 본 addendum 이 충돌할 경우: **원본 design.md 가 우선** (SEALED), 본 addendum 은 governance 층 보강으로만 해석한다.
- 단, Slot 4 (RULE-CONSTITUTIONAL-4) 는 원본 design.md 에 **부재** 하므로 충돌 가능성은 없다. 본 addendum 은 공백 보강이다.

### 1.3 원본 design.md 와의 교차 참조

| 원본 위치 | 관련 섹션 | 본 addendum 관련 |
|----------|----------|-----------------|
| 원본 governance 원칙 섹션 (최상단) | design 계층의 헌법 원칙 | 본 addendum §2 가 Slot 4 를 추가 |
| 원본 execution guard 섹션 | dual-lock 원칙 | `sol_s1_v3_execution_mode_protocol.md` §4 와 연계하여 triple-lock 확장 (본 addendum 범위 외) |
| 원본 runner 역할 기술 | runner 작업 흐름 | 본 addendum §3 이 authority boundary 추가 |

---

## §2 Runner Authority Boundary — RULE-CONSTITUTIONAL-4 (Slot 4 전문)

> **RULE-CONSTITUTIONAL-4 (runner scope of authority):**
> runner (human operator 또는 automated agent) 는 **governance 문서가 명시적으로 지시하지 않은** 환경 변수 / CLI flag / config 값을 **독자 판단으로 설정할 권한이 없다**.
>
> 이는 특히 다음을 포함한다:
> - governance 가 명시하지 않은 `SOL_S1_V3_EXECUTION_MODE` 값을 runner 가 임의로 선택할 수 없다. 해당 값은 **run GO 문서 본문에서 명시적으로 선언** 되어야 하며, runner 는 **선언된 값만 그대로 환경에 설정** 할 수 있다.
> - governance 가 명시하지 않은 새 env var 를 runner 가 독자 도입할 수 없다.
> - governance 가 명시하지 않은 CLI flag 조합을 runner 가 독자 구성할 수 없다.
>
> 이 규칙의 **존재 이유**: Chain B SEAL-1 의 governance_gap finding 은 **runner 의 비난 대상이 아니다**. runner 가 step 8 run 시점에 `SOL_S1_V3_EXECUTION_MODE` 를 설정하지 않은 것은, governance 가 해당 env var 를 명시하지 않았기 때문이며, runner 가 이를 "알아서" 설정했다면 **오히려 헌법 위반** 이었을 것이다. 본 규칙은 그러한 "알아서" 행동이 **미래에도 금지** 됨을 명문화한다.

### 2.1 규칙 본문 출처

본 §2 의 규칙 본문은 grp_chain DRAFT-1 §4.4(a) 에서 원문 인용되었으며, 인용 과정에서 어떤 의미 변경도 없다. 원문 sha256 `06e0303b…3a9c` 이 본 addendum 의 binding 근거이다.

### 2.2 개념 위치

이 규칙은 design.md 의 **governance 원칙 섹션 최상단** 에 위치해야 할 원칙이었으나, 해당 섹션이 SEALED 상태에서 규칙이 누락된 것이 Chain B governance_gap 의 근본 원인이다. 본 addendum 은 그 공백을 문서 층에서 메운다.

---

## §3 Runner Role Definition — Transparent Relay Only

### 3.1 runner 의 허용 동작

| 동작 | 허용 여부 | 조건 |
|------|----------|------|
| governance 문서의 명시 env var 값을 환경에 그대로 설정 | YES | 값이 governance 문서에 literal 하게 선언되어 있어야 함 |
| governance 문서의 명시 CLI flag 를 그대로 호출 | YES | flag 가 governance 문서에 literal 하게 선언되어 있어야 함 |
| governance 문서의 명시 config 값을 그대로 적용 | YES | 동일 |
| governance 문서의 명시 없는 값을 "추정/편의/효율" 근거로 설정 | **NO** | 금지 |
| governance 문서 간 충돌 시 자체 해결 | **NO** | user clarification 요청 필요 |
| governance 문서의 애매 표현 (e.g. "적절한 값") 을 해석 | **NO** | user clarification 요청 필요 |

### 3.2 runner 의 명시적 non-duties

runner 는 다음 의무를 **지지 않는다**:
- governance 문서의 부재를 보충할 의무
- governance 문서의 누락된 정보를 추정할 의무
- 운영 편의를 위해 governance 문서를 해석/확장할 의무

오히려 runner 는 이러한 행동을 **금지** 당한다. runner 의 역할은 governance → runtime 의 **transparent relay** 이며, 가치 판단이나 value injection 은 user (거버넌스 권한자) 의 영역이다.

### 3.3 runner 가 모호에 직면할 때의 행동 프로토콜

1. 실행을 **즉시 중단** 한다.
2. user 에게 **명시적 clarification 요청** 을 보낸다.
3. clarification 이 도착하기 전까지 어떤 임시값도 설정하지 않는다.
4. clarification 이 도착한 후에는, 도착한 값을 그대로 relay 한다.
5. 이 전체 흐름을 audit trail 에 기록한다.

**"우선 돌려보고 안 되면 고치자"는 접근은 금지된다.**

---

## §4 Design Layer Consequences

### 4.1 design.md 의 "runner" 관련 기술에 대한 재해석 가이드

원본 design.md 에 "runner" 관련 기술이 있을 경우, 본 addendum 의 §2, §3 선언을 **후위 해석 원칙** 으로 적용한다:

- 원본 design.md 가 runner 의 **어떤 행동을 기술** 했을 때, 그 기술이 "governance 가 명시적으로 지시했을 경우에만 수행 가능" 이라는 단서와 함께 해석되어야 한다.
- 원본 design.md 가 runner 에게 **판단 여지** 를 남긴 것처럼 읽히는 부분이 있다면, 그 판단 여지는 본 addendum §2 에 의해 **0 으로 축소** 된다.
- 원본 design.md 의 어떤 섹션도 본 addendum 에 의해 **수정되지 않는다**. 재해석 가이드만 추가될 뿐이다.

### 4.2 design layer invariant (addendum 이후)

| invariant | 값 |
|-----------|-----|
| runner = transparent relay only | YES |
| runner value injection 권한 | 0 |
| governance 명시 없는 env/flag/config 설정 | forbidden |
| runner 의 "추정 기반 보충" 권한 | 0 |
| `auto_advance = forbidden` 과의 상호 보완 | 유지 |

### 4.3 코드 층 파급 범위

본 addendum 은 **문서 층 선언** 이다. 코드 층 (runner pre-flight guard 등) 구현은 IMPL-2 체인 범위 (별도 raw GO 필요). 본 addendum 은 코드 층에 어떤 변경도 유발하지 않는다.

---

## §5 Integration with `auto_advance = forbidden`

### 5.1 두 원칙의 관계

| 원칙 | 차원 | 보호 대상 |
|------|------|----------|
| `auto_advance = forbidden` | governance chain 의 state 전이 | chain 의 범위 오염 방지 |
| **RULE-CONSTITUTIONAL-4** | runner 의 value injection | runtime 행동의 임의 변경 방지 |

두 원칙은 **직교 (orthogonal) 관계** 이며, 한쪽만 있으면 다른 쪽의 loophole 이 열린다.

### 5.2 loophole 시나리오 (왜 둘 다 필요한가)

**시나리오 A:** `auto_advance = forbidden` 만 존재할 때
- governance chain 은 state 전이를 하지 않음.
- 그러나 runner 가 "편의상" 새 env var 를 설정.
- state 전이 없이 runtime 행동이 변경됨.
- governance chain 의 감시 범위 밖에서 의미 있는 변화 발생 → **loophole**.

**시나리오 B:** RULE-CONSTITUTIONAL-4 만 존재할 때
- runner 는 독자 판단을 하지 않음.
- 그러나 governance chain 이 **스스로** state 전이하여 새 규칙을 적용.
- runner 가 개입하지 않아도 행동이 변경됨.
- user 판단 없이 의미 있는 변화 발생 → **loophole**.

**시나리오 C:** 두 원칙이 함께 적용될 때
- governance chain 은 user 명시 GO 없이 state 전이 불가.
- runner 는 governance 명시 없이 값 주입 불가.
- 두 방향 모두 user 판단을 거쳐야만 runtime 행동 변경 가능.
- **loophole 없음**.

---

## §6 Audit Trail for Runner Authority Boundary

### 6.1 pre-run audit

| 항목 | 요구 증거 |
|------|----------|
| runner 가 설정한 모든 env var | governance 문서에서 literal 인용 가능해야 함 |
| runner 가 호출한 CLI flag 조합 | governance 문서에서 literal 인용 가능해야 함 |
| runner 가 참조한 config 값 | governance 문서에서 literal 인용 가능해야 함 |

### 6.2 violation detection

| 신호 | 해석 |
|------|------|
| governance 문서에 존재하지 않는 env var 설정됨 | `CONSTITUTIONAL_VIOLATION` |
| governance 문서에 존재하지 않는 flag 조합 호출됨 | `CONSTITUTIONAL_VIOLATION` |
| runner 가 clarification 요청 없이 모호 표현을 "해석" 함 | `CONSTITUTIONAL_VIOLATION` |

### 6.3 violation 의 소급 효과

- violation 이 확인된 run 의 결과는 **소급 invalid** 로 분류된다.
- 이는 Chain B SEAL-1 의 governance_gap 처리와 유사한 경로이나, 소급 면제 대상은 **오직 step 8 run 에만 한정** 된다.
- 본 addendum 발행 이후의 어떤 run 도 violation 시 소급 invalid 를 면할 수 없다.

---

## §7 Integrity Self-Declaration

- document_state: DRAFT
- document_type: design_addendum
- addendum_target: `sol_s1_v3_design.md`
- addendum_target_mutation: **false** (원본 불변)
- chain: `grp_chain_impl_1_document_reissuance_chain`
- authority_source_sha256: `06e0303beeac27058d23bd351988e31b9cdedca17bc2bf9cbd1b9b1da3b13a9c`
- frozen_script_sha256_at_issuance: `94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a` (unchanged, not touched)
- env_SOL_S1_V3_RUN_AUTHORIZED: NOT SET
- env_SOL_S1_V3_EXECUTION_MODE: NOT SET
- chain_a_closure_triplet: UNTOUCHED (CLOSED / FAIL / NO_V4_UNLOCK)
- chain_b_seal_1_binding: UNTOUCHED (governance_gap finding BINDING ACTIVE)
- parent_chain_status: ACTIVE-dormant (DEFER) — NOT CLOSED BY THIS ADDENDUM
- count_contract_2종: 28 / 20 (unchanged since step 3, not referenced for mutation)
- seal_status_of_this_document: NOT_YET_SEALED
- seal_basis: requires separate user SEAL GO

---

## §8 Global State Declaration

```
GLOBAL STATE                                      = STANDBY
GRP_CHAIN DRAFT-1                                 = SEALED (externally, 06e0303b…3a9c, UNCHANGED)
sol_s1_v3_design.md ORIGINAL                      = SEALED (UNCHANGED by this addendum)
IMPL-1 DOCUMENT REISSUANCE CHAIN                  = IN PROGRESS (this document is 2 of up to 4 artifacts)
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
auto_advance                                      = forbidden
```

---

## §9 Revision Log

| Rev | Timestamp | Actor | Change Scope |
|-----|-----------|-------|--------------|
| DRAFT-1 | 2026-04-11 | `grp_chain_impl_1_document_reissuance_chain_step_2_2026_04_11` | 최초 DRAFT 발행. §1~§8 작성. Slot 4 전문 인용. 원본 design.md 0 mutation. |
