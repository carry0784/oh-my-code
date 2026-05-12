# CI Advisory Triage Policy
## CI Advisory 실패 자동 분류 정책 v1.0

**Document Path:** `docs/operations/ci_advisory_triage_policy.md`
**Parent Authority:** `Operating Constitution v1.0`
**Status:** ACTIVE
**Scope:** docs-only PR에서 발생한 advisory-tier CI 실패의 분류·차단·통과 규칙
**Applies to:** PR review / CI triage
**Non-goals:** 코드 변경, CI 설정 변경, Python type debt 정리
**역참조:** `docs/operations/evidence/step6_typecheck_tier_criteria.md` (참조만, 본 정책은 해당 문서를 수정하지 않음)

---

## 제약 선언

- 본 문서는 상위 헌법의 구현 세부화 문서이다.
- 본 문서는 새 권한을 추가하지 않는다.
- 본 문서는 자동 실행 권한을 부여하지 않는다.
- 본 문서는 상위 헌법과 충돌해서는 안 된다.
- 본 정책은 **CI tier 정의 자체를 변경하지 않는다.** Tier 1 / Tier 2 정의는 `step6_typecheck_tier_criteria.md`에 위임된다.
- 본 정책은 **CI YAML / pyproject.toml / mypy 설정을 수정할 권한을 부여하지 않는다.**

---

## 1. 목적

PR이 docs-only이고 실패한 CI check가 advisory-tier(non-blocking)일 때, 그 실패가 **PR 변경 범위와 무관**하다는 것을 명시적·반복가능한 절차로 판정하기 위한 규칙을 정의한다.

판단을 운영자 직관이 아닌 **결정 매트릭스**로 옮겨, 다음을 방지한다:

- docs-only PR에서 무관한 type debt를 고치려다 scope expansion 발생
- advisory 실패를 blocking으로 오해해 PR 보류
- advisory 실패를 무비판적으로 무시해 학습 루프 단절

---

## 2. 적용 범위

본 정책은 다음 조건을 **모두** 만족하는 PR에만 적용된다.

| 조건 | 기준 |
|------|------|
| C1. PR 변경 파일 | `*.md`, `docs/**`, `*.txt`, `LICENSE*` 등 docs-only 한정 |
| C2. Python 변경 | `*.py` / `*.pyi` 변경 라인 수 = **0** |
| C3. CI 설정 변경 | `.github/workflows/**`, `pyproject.toml`, `mypy.ini` 등 = **0** |
| C4. 실패 check tier | 해당 check 이름에 `advisory` 포함 또는 `continue-on-error: true` |

C1~C4 중 하나라도 미충족이면 본 정책은 **미적용**되며, 운영자의 표준 PR 리뷰로 처리된다.

---

## 3. Advisory Failure Auto-Triage 결정 매트릭스

```
IF:
  PR.changed_files matches docs-only pattern (C1)
  AND PR.python_changes_LOC == 0 (C2)
  AND PR.ci_config_changes_LOC == 0 (C3)
  AND failed_check.name contains "advisory" OR check.continue_on_error == true (C4)

THEN:
  classify failure as ADVISORY_UNRELATED
  verdict = SKIP
  merge_eligibility = governed by BLOCKING checks only

ELSE:
  verdict = STANDARD_REVIEW
  defer to operator
```

### 3.1 분류 결과

| 분류 | 의미 | PR 영향 |
|------|------|---------|
| `ADVISORY_UNRELATED` | PR 변경과 무관한 advisory tier 실패 | **SKIP** — merge 차단 안 함 |
| `ADVISORY_RELATED` | PR 변경이 advisory 실패를 유발했을 가능성 있음 | **HOLD** — 운영자 판정 필요 |
| `STANDARD_REVIEW` | 본 정책 적용 범위 밖 | 표준 PR 리뷰 흐름 |

### 3.2 Blocking gate와의 관계

본 정책은 **advisory tier만 다룬다.** 어떤 blocking check (예: `typecheck (tier 1 — blocking)`, `lint`, `build`, `test`)도 실패하면 PR은 자동으로 **HOLD** 상태이며, 본 정책으로 SKIP할 수 없다.

```
merge_ready = ALL(blocking_checks == success) AND advisory_classification != ADVISORY_RELATED
```

---

## 4. 운영 절차

### 4.1 PR 작성자 책임

1. PR 본문 또는 첫 커밋 메시지에 변경 범위 명시 (예: "docs-only")
2. advisory 실패가 보이면 **즉시 코드 수정으로 대응하지 말 것.** 본 정책 §3 결정 매트릭스로 분류부터 수행
3. 분류 결과를 PR 코멘트 또는 커밋 메시지에 기록

### 4.2 리뷰어 책임

1. §2의 C1~C4 조건을 PR diff로 검증
2. 결정 매트릭스 결과를 확인
3. `ADVISORY_UNRELATED`로 분류되면 SKIP 사유를 PR 코멘트로 짧게 기록 (예: "tier-2 advisory failure, pre-existing typing debt, PR is docs-only")

### 4.3 운영자 책임

1. `ADVISORY_RELATED` 또는 `STANDARD_REVIEW`로 분류된 경우의 최종 판단
2. 분류 룰 자체의 개정 권한 보유
3. 누적된 advisory tier debt를 별도 cleanup PR로 분리·승인

---

## 5. 분리 원칙

본 정책은 **advisory tier 실패의 분류** 만 다룬다. 다음은 본 정책 범위 밖이다:

| 항목 | 처리 위치 |
|------|----------|
| advisory tier debt 자체 해소 (예: tier-2 mypy 오류 수정) | 별도 Python cleanup PR (운영상 통칭 "B-1") |
| advisory ↔ blocking 간 tier 승격 절차 | `step6_typecheck_tier_criteria.md` §Promotion Path |
| CR namespace 충돌로 인한 거버넌스 보류 | `evidence_namespace_policy.md` |
| 일반 변경 위험도 등급 (L0~L4) | `change_gate_policy.md` |

---

## 6. Audit 기록

본 정책에 따라 SKIP된 advisory 실패는 PR 코멘트 또는 머지 commit 본문에 다음 형식으로 1줄 기록한다:

```
ADVISORY_UNRELATED: <failed_check_name> (tier=<tier>, scope=docs-only, python_loc=0, ci_loc=0)
```

이 기록은 추후 advisory tier debt 정리 PR(B-1)에서 누적 사례 분석에 사용된다.

---

## 7. 적용 사례 (Reference)

### 7.1 PR #112 (CR-050 P0 governance)
- 변경: `docs/operations/evidence/cr050_*.md` 2개 신규 (markdown only)
- 실패한 check: `typecheck (tier 2 — advisory)`
- 분류: `ADVISORY_UNRELATED` (C1~C4 모두 충족)
- 결정: SKIP
- 결과: 4/4 blocking gate PASS 확인 후 merge (squash commit `c94e8d7`)

이 PR이 본 정책 §3 결정 매트릭스의 첫 실사례이다.

---

## 8. 향후 자동화 후보 (Non-binding)

본 정책은 사람 절차다. 다음은 자동화 후보로만 기록한다 (자동 실행 권한 부여 아님):

- GitHub Actions의 `paths-filter` + `continue-on-error` 조합으로 advisory tier를 자동 라벨링
- PR bot이 §3 매트릭스를 자동 계산하여 코멘트 작성
- advisory tier debt 누적 카운트를 ops dashboard 카드로 표시

자동화 도입은 본 정책의 §2~§5를 변경 없이 수행 가능해야 한다.

---

## 9. Cross-references

- `docs/operations/evidence/step6_typecheck_tier_criteria.md` — Tier 1/2 정의 (본 정책의 입력)
- `docs/operations/change_gate_policy.md` — L0~L4 변경 위험도 등급 (참조만, 본 정책은 미수정)
- `docs/operations/evidence_namespace_policy.md` — Bundle 1 동반 문서, 거버넌스 보류 규칙
- `docs/operations/evidence/cr050_external_artifact_trust_map.md` — 외부 자료 신뢰도 (병행 도입)
- `docs/operations/evidence/cr050_clean_room_injection_policy.md` — Clean-room 절차 (병행 도입)

---

## Status

```
Status: ACTIVE
Scope: operational policy
Authority: docs-only governance rule
Applies to: PR review / CI triage
Non-goals: code change, CI configuration change, Python type debt cleanup
Version: 1.0
Date: 2026-05-12
Authority Holder: Operator (운영자)
```
