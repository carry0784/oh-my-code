# PR Open Decision — L3 Shared Review Surface transition

**Doc ID**: pr_open_decision_2026-04-16
**Doc Path (repo-relative)**: docs/operations/evidence/pr_open_decision_2026-04-16.md
**Created At**: 2026-04-16
**Author**: claude-code (L3 transition 판정 receipt)
**Framework**: 최소 안전장치 v2 (`changelog/0006`)
**transition_class**: LOCAL_ONLY (본 receipt), PR open 자체는 SHARED_REVIEW 로 deferred
**Ledger Class**: OPERATIONAL (transition 판정 receipt)
**Authority Basis**: 사용자 analysis response 2026-04-16 — 2단계 "PR open 여부 별도 결정"
**Decision**: **A안 채택 (PR open 은 P3 종료 이후)**

---

## 1. Options (사용자 제시 원문)

| 안 | 내용 | 성격 |
|---|---|---|
| **A안** | 지금은 push 까지만 유지, PR 은 P3 종료 이후 | 보수적, 운영 깔끔 |
| **B안** | 지금 PR open 하되 "review surface only / no live implication" 로 제한 | 적극적, CI round-trip 감수 |

---

## 2. Selected: A안

### 2.1 근거

1. **P3 관측 진행 중** — 새 14D 창 (`P3_POSTSEAL_2026-04-15`) 종료 예정 `2026-04-28T21:24:18Z`. PR 을 지금 열면 관측 기간 내 review noise / context shift 위험
2. **CI round-trip 회피** — CI 가 PR open 시 처음 발동하며 `.github/workflows/ci.yml` 의 `typecheck-blocking` 이 실패할 가능성 존재 (기존 tier 1 scope, 본 세션 docs-heavy push 가 직접 영향은 낮으나 0% 아님). 실패 시 보정 commit → 리뷰 양 증가
3. **리뷰 부담 축소** — 본 push 는 9 commits / 25 files / ~+6,350 lines. 리뷰 패키지로 크다. P3 종료 후 `VAL-PDC-002` 결과를 포함해 단일 PR 로 엮는 것이 리뷰어 관점에서 효율적
4. **보수적 운영 선호** — 사용자 analysis response §5 2단계 명시 "현재로서는 **A안**이 더 보수적이고 운영적으로 깔끔"

### 2.2 수행 내용

- PR open **수행하지 않음**
- 별도 명령 없음 (gh pr create 실행 안 함)
- 본 receipt 로 결정 기록만 수행

---

## 3. L3 Shared Review Surface 전이 규칙 (아이디어 1 채택)

### 3.1 정의

L3 는 별도 **G5 게이트로 승격하지 않고**, framework v2 하위 **영향권 전이 규칙**으로 관리한다 (사용자 아이디어 1).

### 3.2 L3 전이 전제조건

PR open (= L3 전이) 을 수행하려면 다음 중 **하나 이상** 충족:

- **C1 시간 조건**: P3 창 종료 (`2026-04-28T21:24:18Z`) 이후
- **C2 품질 조건**: `typecheck-blocking` 등 main 대상 CI 가 local 검증으로 사전 녹색 예상
- **C3 명시 승인**: 사용자 직접 PR open 지시

### 3.3 L3 전이 금지 사항

- PR open 과 **merge** 는 별개 사건. merge 는 여전히 별도 승인 필요
- PR open = review 표면 공개일 뿐 실행 경로 변화 없음
- PR 내 review comment 수용 시에도 commit push 는 **G4 재적용** (본 receipt chain 재사용)

### 3.4 receipt transition_class 대응

| 단계 | transition_class |
|---|---|
| local commit | LOCAL_ONLY |
| git push | REMOTE_VISIBLE (G4) |
| **PR open** | **SHARED_REVIEW (L3)** |
| main merge | LIVE-adjacent (별도 승인) |
| production deploy | LIVE_PATH (G1+G2+G3 복합) |

---

## 4. 상태 유지 확인

- local HEAD: `a4bdbbb` (+ `0011` commit pending)
- origin HEAD: `a4bdbbb` (동기화 유지 예정, push 추가 필요)
- PR open: **없음**
- activation_gate: LOCKED (불변)
- production_authorized: FALSE (불변)

---

## 5. 4-Gate (v2) 미저촉

| Gate | 저촉 |
|---|---|
| G1 | ✗ |
| G2 | ✗ |
| G3 | ✗ |
| G4 | ✗ (본 결정은 PR 을 "열지 않는" 결정, 원격 가시성 추가 변경 없음) |

---

## 6. Follow-up

- P3 종료 (~2026-04-28) 후 PR open 재검토 별도 receipt
- VAL-PDC-002 결과와 묶어 단일 리뷰 패키지 구성 권장
- 그 전까지 feature branch 는 push-only 공개 상태 유지

---

## 7. Signatures

- **Decided**: 2026-04-16 claude-code (L3 transition 판정)
- **Framework**: 최소 안전장치 v2
- **Decision**: **A안** (PR open deferred until post-P3)
- **Next review**: 2026-04-28 이후 또는 사용자 명시 지시
