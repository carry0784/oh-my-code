# Continuous Progress Plan v1

**Created**: 2026-04-05
**Status**: ACTIVE
**Authority**: A (설계안 승인) + 구현자 (세션별 실행)
**Purpose**: blocked 거버넌스 체인에 세션이 붙잡히지 않도록, 막히지 않는 저위험 전진 트랙을 별도로 운영한다.
**Scope**: 본 문서 자체는 어떠한 코드/테스트/flag/activation/write 권한도 부여하지 않는다. Track B의 각 항목은 세션 진입 시 별도 판단된다.

---

## 1. Background — 왜 이 plan이 필요한가

CR-048 RI-2B-2b 거버넌스 체인은 `implementation_go_receipt` 서명(`d999aed`)까지 도달했고, 이후 모든 forward 분기는 external unlock을 요구한다:

| 분기 | 차단 사유 |
|---|---|
| B3' (EXECUTION_ENABLED flip) | A 명시 지시 대기 |
| B3'' (first CAS bounded write) | 신규 activation_go_receipt + dry_24h_clean |
| B2-2 (Ruleset Phase 2) | write/admin 협업자 1명 확보 필요 |
| CR-046 Phase 5a (SOL paper) | A scope 재지정 |

**문제**: "blocked 대기"는 리포지토리 품질/운영성 향상에 기여하지 않는다. 고위험 체인은 계속 대기하되, 그 기간 동안 저위험 병행 트랙으로 세션을 무중단 전진시킨다.

**해결**: Track A (승인 대기 체인, HOLD) ↔ Track B (무정지 실행 큐, ACTIVE)의 2-트랙 운영.

---

## 2. Core Principles (고정, 세션 간 불변)

| # | 원칙 | 설명 |
|:---:|---|---|
| P1 | **한 세션 한 작업** | 한 세션에서 Track B의 복수 항목을 동시 진행하지 않는다 |
| P2 | **blocked → 즉시 PASS + 세션 종료** | 큐 최상단이 blocked면 우회하지 않고 사유 1줄 기록 후 세션을 종료한다. 다음 항목으로 자동 이동 금지 |
| P3 | **한 PR 한 목적** | PR은 단일 목적 단위로 쪼갠다 |
| P4 | **receipt 체인 우회 금지** | 코드 실행 / activation / live write / flag 전환은 기존 receipt 규칙을 결코 우회하지 않는다 |
| P5 | **evidence 본문 보존** | 기존 evidence/package 본문은 A의 별도 명시 지시 없이 수정 금지 |
| P6 | **전진/정리 태그 명시** | 각 큐 항목은 전진형 / 정리형으로 태깅한다 |
| P7 | **승인 링크 무결성** | receipt / acceptance / implementation_go / activation_go 체인은 결코 스킵되지 않는다 |
| P8 | **완료 분기 재진입 금지** | 이미 완료된 분기는 재후보 제외 (memory + merge 히스토리 교차 확인) |

---

## 3. Track A — 승인 대기 체인 (HOLD · 본 plan에서 건드리지 않음)

> **본 plan은 Track A를 전진시키지 않는다.** Track A 진입은 본 plan이 종료/suspend된 후 또는 A의 별도 명시 지시가 있을 때만 가능하다.

| 분기 | 상태 | unlock 조건 |
|---|:---:|---|
| B2-2 (Ruleset Phase 2 approvals=1) | HOLD | write/admin 협업자 1명 확보 |
| B3' (shadow_write_service.py flag flip) | HOLD | A 명시 지시 "B3' GO" |
| B3'' (신규 activation_go_receipt + 첫 write) | HOLD | dry_24h_clean=true + 신규 `cr048_ri2b2b_activation_go_receipt.md` 서명 |
| 첫 CAS bounded write 실행 | HOLD | B3'' 완료 이후 |
| CR-046 Phase 5a (SOL paper rollout 실행) | HOLD | A의 새 scope 지정 |

---

## 4. Track B — 무정지 실행 큐 (ACTIVE · 본 plan의 주 실행 대상)

우선순위 순서대로 진행. 한 세션 = 한 항목 = 한 PR.

| # | 항목 | 태그 | 대상 파일 | 차단 가능성 |
|:---:|---|:---:|---|:---:|
| B-1 | CI Phase 2 — coverage 기준선 수립 (측정+제안, 강제 X) | 전진형 | 신규 `docs/operations/ci_coverage_baseline.md` | 🟢 낮음 |
| B-2 | CI Phase 2 — concurrency cancel-in-progress | 전진형 | `.github/workflows/ci.yml` | 🟢 낮음 |
| B-3 | SHA pinning inventory 작성 (적용 X) | 정리형 | 신규 `docs/operations/sha_pinning_inventory.md` | 🟢 낮음 |
| B-4 | CODEOWNERS 준비 문서 (실제 파일 생성 X) | 정리형 | 신규 `docs/operations/codeowners_draft.md` | 🟢 낮음 |
| B-5 | CR-046 Phase 5a preflight 체크리스트 (실행 X) | 정리형 | 신규 `docs/operations/evidence/cr046_phase5a_preflight.md` | 🟢 낮음 |

> **정리형 항목도 본 plan의 명시 승인 하에 전진 허용**. Track B 리스트 자체가 A 승인된 "트리거 선언"이다.

### 4.1 Item B-1 명세 — CI coverage 기준선 수립

**목적**: 현재 main 기준 `pytest --cov=app` 측정치를 문서화하고 fail-under 후보값 제안. **이번 PR에서는 `--cov-fail-under` 실제 강제 적용 금지** (별도 세션에서).

**절차**:
1. main 체크아웃 + 최신 상태 확인
2. `pytest --cov=app --cov-report=term-missing -q` 로컬 실행 및 수치 기록
3. 현재 coverage + 후보 fail-under (예: 현재값 − 2% 안전 마진) 제안
4. 신규 문서 `docs/operations/ci_coverage_baseline.md` 생성 (측정값, 후보값, 근거, 다음 단계)
5. PR 생성 → CI 3 check green → squash merge

**파일 변경**: 신규 문서 1건 (ci.yml 미변경)

**PR 제목**: `docs: establish CI coverage baseline for Phase 2 fail-under proposal`

**종료 조건**: PR merge + 3 check green + 문서에 현재 수치/후보값 명시

**차단 트리거 (즉시 PASS + 세션 종료)**:
- 로컬 `pytest --cov` 실행 실패 (환경 문제)
- coverage 수치 측정 불가
- app 디렉터리 구조 변경으로 `--cov=app` 유효하지 않음

### 4.2 Item B-2 명세 — concurrency cancel policy

**목적**: 동일 ref의 중복 workflow run을 자동 취소하여 CI 자원 낭비 제거.

**절차**:
1. `.github/workflows/ci.yml` 최상단에 concurrency 블록 추가:
   ```yaml
   concurrency:
     group: ${{ github.workflow }}-${{ github.ref }}
     cancel-in-progress: true
   ```
2. PR 생성 → 3 check green 확인
3. (선택) 같은 PR에 2차 push를 유발하여 이전 run 자동 취소 관찰
4. squash merge

**파일 변경**: `.github/workflows/ci.yml` 1건 수정 (블록 추가)

**PR 제목**: `ci: add concurrency cancel-in-progress for ref-based dedup`

**종료 조건**: PR merge + 3 check green

**차단 트리거**: 현재 ci.yml이 이미 concurrency 블록 보유 시 PASS

### 4.3 Item B-3 명세 — SHA pinning inventory

**목적**: supply-chain hardening을 위한 action SHA pin 후보 목록 문서화. **실제 pin 적용은 금지**.

**절차**:
1. `.github/workflows/*.yml`에 사용되는 모든 action 열거
2. 각 action의 현재 tag 버전 + 해당 tag의 commit SHA 조회 (GitHub API 또는 공식 릴리스 페이지)
3. 신규 문서 `docs/operations/sha_pinning_inventory.md`에 표로 정리:
   - action 이름, 현재 tag, 대응 SHA, 릴리스 링크, 보안 고려사항
4. 실제 pin 적용은 **별도 세션/PR**로 분리 선언
5. PR merge

**파일 변경**: 신규 문서 1건 (workflow 미변경)

**PR 제목**: `docs: add SHA pinning inventory for CI actions`

**차단 트리거**: SHA 조회 도구 부재, GitHub API 접근 불가

### 4.4 Item B-4 명세 — CODEOWNERS 준비 문서

**목적**: B2-2 unblock 시점에 즉시 활성화할 수 있는 CODEOWNERS 초안을 미리 설계. **실제 `.github/CODEOWNERS` 파일은 생성 금지** (B2-2 trigger 조건).

**절차**:
1. 리포 구조 매핑 (`app/`, `workers/`, `strategies/`, `exchanges/`, `tests/`, `docs/operations/`, `.github/`)
2. 각 디렉터리 소유 역할 placeholder 정의 (실제 계정 X, 역할명만)
3. 신규 문서 `docs/operations/codeowners_draft.md` 생성 (근거 + 초안 + 활성화 조건)
4. 활성화는 B2-2 unblock 시 별도 PR로 명시적으로 분리
5. PR merge

**파일 변경**: 신규 문서 1건 (`.github/CODEOWNERS` 파일은 생성 금지)

**PR 제목**: `docs: add CODEOWNERS draft for future B2-2 activation`

**차단 트리거**: 리포 구조 파악 불가 (매우 드물음)

### 4.5 Item B-5 명세 — CR-046 Phase 5a preflight 체크리스트

**목적**: SOL paper rollout 실제 시작 **전**에 필요한 체크리스트/관측 항목/abort 조건만 문서화. **실제 Phase 5a 실행 금지**.

**절차**:
1. `docs/operations/evidence/cr046_sol_paper_rollout_plan.md` 참조 (존재 시)
2. 시작 전 점검 항목 도출: 환경변수, latency guard, observability, rollback 경로
3. 관측 항목 정의: 집계 주기, 임계치, 수집 대상
4. abort 조건 명시: 어떤 수치가 어떤 값 초과 시 즉시 중단
5. 신규 문서 `docs/operations/evidence/cr046_phase5a_preflight.md` 생성
6. 실제 Phase 5a 시작은 A의 별도 명시 지시가 있을 때만
7. PR merge

**파일 변경**: 신규 문서 1건 (코드/flag 미변경)

**PR 제목**: `docs: add CR-046 Phase 5a preflight checklist (no execution)`

**차단 트리거**: `cr046_sol_paper_rollout_plan.md` 미존재 또는 접근 불가

---

## 5. Session Operating Rules

### 5.1 세션 시작 루틴

1. 본 문서의 Track B 큐를 **최상단부터** 스캔
2. 첫 번째 **unblocked** 항목을 선택
3. 해당 항목의 명세 섹션(§4.x)을 그대로 실행
4. 한 세션에서 두 항목을 **동시 진행 금지**

### 5.2 차단 감지 시 (P2 적용)

1. 차단 원인 1줄 기록 (예: `B-1 PASS: pytest cov plugin not installed in env`)
2. 다음 항목으로 **자동 이동하지 않음**
3. A에게 차단 원인 + 해제 방안 후보 보고 후 **세션 종료**
4. A 지시 하에 다음 세션에서 재시도 or 항목 skip or plan 조정

> **이유**: "blocked → 자동 다음 항목"은 P1(한 세션 한 작업) 위반. 차단 감지 = 세션 종료가 원칙이다.

### 5.3 세션 종료 조건

| 조건 | 처리 |
|---|---|
| 선택 항목이 PR merge까지 완료 | ✅ 정상 종료 → STANDBY |
| 선택 항목이 차단 감지 | ⚠️ 차단 보고 → STANDBY |
| CI fail 발생 | ⚠️ 원인 보고 → STANDBY (자동 재시도 금지) |
| A가 plan suspend/switch 지시 | 🔄 즉시 STANDBY |
| governance 위반 징후 | 🛑 EMERGENCY STOP |

### 5.4 보고 형식 (매 세션)

```
1. 해석 및 요약
2. 장점 / 단점
3. 이유 / 근거
4. 실현 / 구현 대책
5. 실행 결과
6. 다음 세션 후보
```

---

## 6. Out of Scope — 본 plan이 **절대** 다루지 않는 것

| 금지 항목 | 이유 |
|---|---|
| `EXECUTION_ENABLED: False → True` 전환 | B3' 별도 GO 필요 |
| `shadow_write_service.py` 비-테스트 수정 | B3' 별도 GO 필요 |
| `test_shadow_write_receipt.py` flag 검증 전환 | B3' 별도 GO 필요 |
| 첫 실제 CAS bounded write 실행 | B3'' + activation_go_receipt 필요 |
| `rollback_bounded_write()` 수동 실행 | 별도 A 지시 필요 |
| beat / schedule 활성화 | 별도 activation 필요 |
| `ALLOWED_TRANSITIONS` / `FORBIDDEN_TARGETS` 수정 | 절대 금지 (거버넌스 핵심) |
| Gate unlock | A 전용 |
| CR-046 Phase 5a **실제** 실행 | 별도 scope 지시 필요 (preflight 문서화만 허용) |
| Track A 분기 전진 | 본 plan 범위 외 |
| 기존 evidence / package 본문 수정 | P5 |
| `.github/CODEOWNERS` 실제 파일 생성 | B2-2 unblock 후에만 |

---

## 7. Graduation / Supersession

본 plan은 아래 조건 중 하나 발생 시 종료 또는 suspend 된다:

| 조건 | 효과 | 후속 |
|---|---|---|
| Track B 5개 항목 **전부 merge 완료** | **COMPLETE** | 새 plan v2 작성 필요 |
| A가 Track A 분기 진입 지시 (예: "B3' GO") | **SUSPEND** | Track A 세션 전담 → Track A 완료 후 resume 가능 |
| A가 다른 우선순위 지정 | **SUSPEND** | 새 plan으로 교체 |
| governance 위반 발생 | **EMERGENCY STOP** | 원인 보고 + 복구 계획 필요 |

---

## 8. Item 간 의존성 / 실행 순서

Track B 큐는 **엄격한 우선순위 순**이다. 순서 변경은 A 명시 지시 필요.

| # | 선행 조건 | 후행 영향 |
|:---:|---|---|
| B-1 | 없음 | 후속 항목 독립 실행 가능 |
| B-2 | B-1 merge 후 | — |
| B-3 | B-2 merge 후 | — |
| B-4 | B-3 merge 후 | B2-2 unblock 시 활성화 후보 |
| B-5 | B-4 merge 후 | CR-046 Phase 5a A 지시 시 활성화 후보 |

**예상 소요**: 한 항목 당 1세션 = 최대 5세션으로 Track B 완수.

---

## 9. 본 문서가 부여하는 것 / 부여하지 않는 것

### 부여하는 것 ✅
- 다음 세션에서 Track B **큐 최상단 unblocked 항목 1건** 실행 권한 (session-scoped)
- P2 (차단 감지 즉시 PASS + 세션 종료) 자동 적용 권한
- §5.4 세션 보고 형식 자동 적용 권한
- Track B 5개 항목에 대한 scope 사전 승인 (각 §4.x 명세 준수 조건 하에)

### 부여하지 않는 것 ❌
- Track A 분기 전진 권한 (전혀 없음)
- 큐 항목 **순서 변경** 권한 (A 지시 필요)
- 새 Track B 항목 **추가** 권한 (A 지시 필요)
- 여러 세션에 걸친 **누적 실행** 권한 (세션마다 재진입 판단)
- receipt / evidence 본문 수정 권한
- 코드 실행 / activation / live write 권한 (어떤 형태로든)

---

## 10. References

| 문서 | 역할 |
|---|---|
| `docs/operations/next_session_prompts.md` | PR-A/PR-B 원본 (이미 완료) |
| `docs/operations/evidence/cr048_ri2b2b_implementation_go_receipt.md` | d999aed 서명 완료 (SIGNED, 코드 변경 미착수) |
| `docs/operations/evidence/cr048_ri2b2b_scope_review_package.md` | v1.0 LOCK |
| `docs/operations/evidence/cr048_ri2b2b_scope_review_acceptance_receipt.md` | ACCEPT by A, 2026-04-05 |
| `docs/operations/evidence/receipt_naming_convention.md` | receipt 3-pattern 규약 |
| `docs/operations/evidence/cr048_ri2a2b_activation_manifest.md` | v1.1 SEALED, Activation BLOCKED |
| `CLAUDE.md` | CR-046 Phase 5a 우선순위 (Track A 잠정 분류) |

---

## 11. 본 plan 자체의 적용 규칙

- 본 문서는 **ACTIVE** 상태에서만 실행 권한을 부여한다.
- A가 본 plan을 suspend/complete 선언하면, 이후 세션은 본 문서를 근거로 사용할 수 없다.
- 본 문서 내용 수정은 A의 별도 명시 지시 하에서만 가능하다. 세션별 실행 결과는 별도 receipt/PR body에 기록한다.
- Track B 항목 중 정리형 항목(B-3, B-4, B-5)은 본 plan이 **트리거**가 되며, plan 외부에서는 여전히 "정리 태그 후보 = 기본 BLOCK" 규칙이 유효하다.

---

## Footer

```
Continuous Progress Plan v1
Status            : ACTIVE
Created           : 2026-04-05
Authority         : A (설계안 승인) + 구현자 (세션 실행)
Track A           : HOLD (governance waiting chain — DO NOT TOUCH)
Track B           : ACTIVE (5 items queued, strict priority order)
Session rule      : one item per session, blocked → PASS + session end
Execution grant   : Track B unblocked top item (next session, session-scoped)
Forbidden         : code exec / activation / live write / evidence body mod
Scope violation   : EMERGENCY STOP
Supersession      : A explicit instruction OR Track B complete
```
