# Evidence Namespace Policy
## CR 증거 네임스페이스 사전 점검 정책 v1.0

**Document Path:** `docs/operations/evidence_namespace_policy.md`
**Parent Authority:** `Operating Constitution v1.0`
**Status:** ACTIVE
**Scope:** 신규 CR / governance / policy 문서의 네임스페이스 충돌 방지 및 모호성 발생 시 보류 규칙
**Applies to:** evidence namespace pre-flight, PR pre-merge governance gate
**Non-goals:** 기존 CR 문서 재명명, CI 설정 변경, 코드 변경
**역참조:** `docs/operations/change_gate_policy.md` (참조만, 본 정책은 해당 문서를 수정하지 않음)

---

## 제약 선언

- 본 문서는 상위 헌법의 구현 세부화 문서이다.
- 본 문서는 새 권한을 추가하지 않는다.
- 본 문서는 자동 실행 권한을 부여하지 않는다.
- 본 문서는 상위 헌법과 충돌해서는 안 된다.
- 본 정책은 **기존 CR 문서를 재명명할 권한을 부여하지 않는다.** 이미 main에 편입된 CR 시리즈는 그대로 보존된다.
- 본 정책은 **신규 CR / governance 문서**의 PR 단계 사전 점검에만 적용된다.

---

## 1. 목적

신규로 작성되는 거버넌스·정책·증거 문서가 기존 CR 네임스페이스(`cr0XX_*`) 또는 거버넌스 카드 네임스페이스(`g##_*`, `c##_*`)와 충돌하지 않도록 **PR 작성 전 사전 점검**을 의무화한다.

판단을 작성자 직관이 아닌 **체크리스트 + 결정 매트릭스**로 옮겨, 다음을 방지한다:

- 이미 점유된 CR slot에 의미적으로 무관한 신규 문서가 끼어들어 evidence chain 오염
- 기존 CR series의 추적성·계보 약화
- CI는 green이지만 거버넌스적으로 부적합한 PR이 검토 없이 머지되는 상황

---

## 2. 적용 범위

본 정책은 PR이 다음 중 하나라도 해당하면 **반드시** 적용된다.

| 조건 | 기준 |
|------|------|
| N1. 신규 CR 문서 | `docs/operations/evidence/cr0XX_*.md` 신규 추가 |
| N2. 신규 거버넌스 카드 | `docs/g##_*.md` 또는 `docs/governance_*.md` 신규 추가 |
| N3. 신규 운영 정책 | `docs/operations/*_policy.md` 신규 추가 |
| N4. 신규 trust / boundary / injection 정책 | trust map, clean-room, namespace, charter 등의 신개념 도입 |

---

## 3. CR-Namespace Pre-flight Checklist

신규 문서 PR을 **열기 전** 다음 5단계를 통과해야 한다.

### Step 1 — Namespace Inventory
```
ls docs/operations/evidence/cr0XX_*.md | sed 's|.*/cr0||;s|_.*||' | sort -u
ls docs/g*_*.md docs/governance_*.md 2>/dev/null
ls docs/operations/*_policy.md 2>/dev/null
```
의도 prefix가 **이미 사용 중**인지 목록으로 확인한다.

### Step 2 — Scope Comparison
의도 prefix가 사용 중이라면 기존 series의 헤더(첫 line)를 읽어 **scope를 비교**한다.

### Step 3 — Relation Declaration
- **Child artifact**: 기존 CR의 직접 하위 문서 (예: `cr046_three_tier_judgment.md` 의 자식인 `cr046_sol_paper_rollout_plan.md`)
- **Independent governance**: 기존 CR과 의미적으로 무관한 새 거버넌스 범위 (예: PR #112의 외부 자료 신뢰도 정책)
- **Ambiguous**: 둘 중 하나로 단정 짓기 어려운 경우

### Step 4 — Pre-flight Decision

```
IF relation == Child:
  reuse_existing_namespace = ALLOWED
  PR title prefix = same CR
  evidence cross-ref includes parent CR

ELIF relation == Independent:
  reuse_existing_namespace = FORBIDDEN
  pick next free slot via inventory
  PR title prefix = new CR/G/policy ID

ELIF relation == Ambiguous:
  merge_state = GOVERNANCE_HOLD
  defer to operator until relation is declared
```

### Step 5 — PR Body Declaration
PR 본문에 다음 한 줄을 의무 기록:
```
namespace pre-flight: <ChosenPrefix> | relation=<Child|Independent> | inventory_checked=YES
```

---

## 4. GOVERNANCE_HOLD 상태어 정의

본 정책에서 도입하는 **로컬 상태어**.

| 상태 | 의미 | 해제 조건 |
|------|------|----------|
| `GOVERNANCE_HOLD` | CI가 green이라도 네임스페이스 관계 모호성으로 PR을 머지하지 않음 | 운영자가 §3 Step 3의 관계를 명시적으로 선언 |

**중요**: 본 상태어는 본 정책의 §3 Step 4 모호성 결과에만 사용된다. 다른 보류 사유(코드 영향, 보안, 일정)는 `change_gate_policy.md` L0~L4 등급 체계가 담당한다. 본 정책은 해당 문서를 수정하지 않으며 단방향 참조만 한다.

---

## 5. Relation 판정 가이드

작성자가 §3 Step 3에서 판정에 사용할 휴리스틱:

| 신호 | Child일 가능성 | Independent일 가능성 |
|------|----------------|-----------------------|
| 기존 CR의 plan 문서가 이 신규 문서를 forward-reference로 명시 | 높음 | 낮음 |
| 기존 CR의 work stream commit history가 동일 branch에서 이어짐 | 높음 | 낮음 |
| 의도된 신규 문서가 새 trust / boundary / injection / preset 개념 도입 | 낮음 | 높음 |
| 기존 CR의 marker (예: `BASELINE_SEALED`, `SEALED_PASS`) 이후 별도 거버넌스 토픽 | 낮음 | 높음 |
| 의미적으로는 무관하나 단순히 prefix가 비어 있어 보인다 | 낮음 | 높음 (→ next free slot) |

**원칙**: 신호가 모순될 때는 `Ambiguous`로 처리하고 GOVERNANCE_HOLD 진입.

---

## 6. 적용 사례 (Reference) — CR-048 → CR-050 Rename

본 정책의 직접적 동기가 된 실사례.

### 6.1 배경
- 2026-05-12 PR #112 작성 중, 외부 자료(Uprich Future Bot) 거버넌스 문서 2개를 `cr048_*` prefix로 commit (`3cf92e5`)
- 직후 inventory 검토에서 `cr048_*`이 이미 **77개 파일**의 L3 모델 / runtime integration / staged expansion work stream에 점유되어 있음을 발견

### 6.2 §3 Step 3 판정
- 신규 문서의 scope: 외부 자료 신뢰도 + clean-room injection (새 거버넌스 토픽)
- 기존 CR-048: L3 model / runtime / `ri1`-`ri2*` / `stage1`-`stage4` (별개 work stream)
- 관계: **Independent**

### 6.3 §3 Step 4 결정
- `reuse_existing_namespace = FORBIDDEN`
- next free slot inventory: CR-048 (77), CR-049 (2), CR-050 (0) → **CR-050 선택**
- rename commit: `aaf0372` (2026-05-12)

### 6.4 결과
- 머지 commit: `c94e8d7` (squash, 2026-05-12)
- evidence chain 오염 없이 신규 거버넌스 시리즈 안전 편입

이 사례는 본 정책 §3의 첫 실 적용 케이스로 보존된다. 향후 동일 패턴 발생 시 본 사례를 비교 기준으로 사용한다.

---

## 7. 분리 원칙

본 정책은 **네임스페이스 충돌 방지** 만 다룬다. 다음은 본 정책 범위 밖이다:

| 항목 | 처리 위치 |
|------|----------|
| CI advisory failure 분류 | `ci_advisory_triage_policy.md` |
| 일반 변경 위험도 등급 (L0~L4) | `change_gate_policy.md` |
| CR 내부 문서 패턴 (header / signature) | `docs/operations/evidence/cr046_three_tier_judgment.md` (기준 샘플) |
| Python / CI / 테스트 변경 승인 | 본 정책 범위 밖 |

---

## 8. Audit 기록

PR이 본 정책 §3을 통과한 경우 PR 본문에 §3 Step 5 형식의 한 줄이 기록되어 있어야 한다. 머지 후 audit 시 다음 grep으로 검증 가능:

```
grep -E "namespace pre-flight: cr0[0-9]+|g[0-9]+|.*_policy" <PR body or merge commit>
```

GOVERNANCE_HOLD에서 해제되어 머지된 PR은 commit message에 다음 한 줄 권장:
```
governance hold resolved: relation=<Child|Independent>, prefix=<ChosenPrefix>
```

---

## 9. 향후 자동화 후보 (Non-binding)

본 정책은 사람 절차다. 다음은 자동화 후보로만 기록한다 (자동 실행 권한 부여 아님):

- pre-commit hook 또는 GitHub Action으로 신규 `cr0XX_*` 파일의 prefix 점유 여부 검사
- PR bot이 §3 inventory를 자동 출력하여 작성자에게 체크리스트 제공
- §3 Step 5의 declaration line이 PR 본문에 없으면 라벨 부여 + 머지 차단

자동화 도입은 본 정책의 §2~§5를 변경 없이 수행 가능해야 한다.

---

## 10. Cross-references

- `docs/operations/ci_advisory_triage_policy.md` — Bundle 1 동반 문서, advisory CI 실패 분류 규칙
- `docs/operations/change_gate_policy.md` — L0~L4 변경 위험도 등급 (참조만, 본 정책은 미수정)
- `docs/operations/evidence/cr050_external_artifact_trust_map.md` — 외부 자료 신뢰도 (병행 도입; 본 정책의 첫 적용 사례에 해당)
- `docs/operations/evidence/cr050_clean_room_injection_policy.md` — Clean-room 절차 (병행 도입)
- `docs/operations/evidence/cr046_three_tier_judgment.md` — Evidence header / signature 표준 샘플

---

## Status

```
Status: ACTIVE
Scope: operational policy
Authority: docs-only governance rule
Applies to: evidence namespace pre-flight, PR pre-merge governance gate
Non-goals: rename existing CR docs, CI configuration change, code change
Version: 1.0
Date: 2026-05-12
Authority Holder: Operator (운영자)
```
