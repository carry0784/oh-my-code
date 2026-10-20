# B/E/G 잔여 항목 재판정표

**Doc ID**: beg_residual_reassessment_2026-04-16
**Doc Path (repo-relative)**: docs/operations/evidence/beg_residual_reassessment_2026-04-16.md
**Created At**: 2026-04-16
**Author**: claude-code (autonomous, 재정합 우선 모드)
**Ledger Class**: OPERATIONAL (재판정 receipt, VRL 아님)
**Related**:
- `docs/operations/changelog/0001_minimum-safety-framework-adoption_2026-04-16.md` (신 framework)
- `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` (Trackedness Preflight §7)
- `docs/operations/evidence/cr_new_p3_new_window_launch_2026-04-14.md` (NOT DONE 목록)
- `ops_state.json` line 64 (CR-046 SOL Stage B bar_count)

---

## 1. 목적

Turn 70~71 에서 pending 으로 올라온 8개 항목 중 **B / E / G** 3건은 실제 저장소 상태 대비 판정이 모호. 최소 안전장치 framework(2026-04-16) 하에서 각 항목을 **DONE / DEFERRED / NEEDS_ACTION / NOT_APPLICABLE / FORBIDDEN_NOW** 중 하나로 고정하고 다음 허용 액션을 명시한다.

---

## 2. 재판정 매트릭스

| 항목 | 현재 실제 상태 | 근거 파일/커밋 | 금지영역 충돌 | **판정** | 다음 허용 액션 |
|---|---|---|---|---|---|
| **B** lane_2 severity governance memo | repo grep `lane_2` → 0 hits / `severity_threshold` → 0 hits. artifact 미존재. CR-NEW v3.1 대화층 construct 에 한정 | 없음 (not instantiated) | 없음 | **NOT_APPLICABLE** | 신 framework 하에서는 대화층 construct 를 artifact 로 promotion 할 필요 없음. 필요 시 별도 CR 로 신규 발행. |
| **E** CR-046 SOL Stage B bar_count post-seal reset | `ops_state.json` line 64 `bar_count: "1/24"` (old P3 data, 2026-04-07 baseline). 새 P3 창은 2026-04-14 `1d0ad55` 로 이미 개시됨. 초기화 미수행 | `cr_new_change3_local_reflection_2026-04-14.md` §8 #4; `cr_new_p3_new_window_launch_2026-04-14.md` NOT DONE 목록; `ops_state.json:64` | 없음 (자율 framework 하에서 `ops_state.json` 은 gitignored runtime artifact, local reflection + tracked evidence receipt 경로) | **NEEDS_ACTION** | (1) local reflection receipt 작성; (2) `ops_state.json:64` bar_count 를 `"0/24 (post-seal)"` 로 편집; (3) `invalidated_runs` 에 pre-new-window 구분 기록; (4) `last_updated` 타임스탬프 갱신; (5) changelog 엔트리. 전부 **autonomous** 가능. |
| **G** Trackedness Preflight rule 공식 문서화 | 규칙 본문은 `cr_new_change3_local_reflection_2026-04-14.md` §7.1 에 **이미 정의**. 다만 공식 운영 규칙 docs (e.g., `docs/operations/operating_constitution.md` 편입 또는 `docs/operations/trackedness_preflight_rule.md` 신설) 로 promotion 미완 | `cr_new_change3_local_reflection_2026-04-14.md` §7; `cr_new_p3_new_window_launch_2026-04-14.md` "NOT DONE: Trackedness Preflight rule 공식 운영 규칙 등재 docs PR" | 없음 (docs-only, tracked repo artifact) | **NEEDS_ACTION** | (1) 신규 docs 파일 `docs/operations/trackedness_preflight_rule.md` 또는 기존 `operating_constitution.md` 편입 섹션 작성 (3 preflight check + 3 artifact categorization); (2) changelog 엔트리; (3) 기존 receipt chain cross-reference. 전부 **autonomous** 가능. |

---

## 3. 상세 재판정 근거

### 3.1 B (lane_2 severity threshold governance memo) — NOT_APPLICABLE

- repo 전역 `grep "lane_2"` 결과: **0 matches**
- repo 전역 `grep "severity_threshold"` 결과: **0 matches**
- 본 construct 는 Turn 65~72 대화 층위에서만 등장한 governance construct
- 신 framework (2026-04-16) 는 "template ≠ GO issuance" 제약을 해제했고, canonical GO verbatim 요구도 해제됨
- 즉 lane_2 memo 는 옛 거버넌스 체제에서 발생한 "승인 gate 통과 대기" 자체가 사라진 상태
- **결정**: artifact 로 promotion 하지 않음. 향후 실제 severity threshold 정책이 필요해지면 별도 CR 로 독립 발행

### 3.2 E (CR-046 SOL Stage B bar_count post-seal reset) — NEEDS_ACTION

현 `ops_state.json:64` 은 다음 상태:

```json
{"id": "CR-046 SOL Stage B", ..., "baseline_at": "2026-04-07T13:50:17Z", "bar_count": "1/24", ...
 "invalidated_runs": [{"run": "pre-hotfix", "bars": 5, "reason": "cross-task closed event loop contamination", ...}]}
```

문제점:
- `baseline_at: 2026-04-07` 은 **옛 P3 창** (2026-04-14 에 새 창으로 대체됨)
- `bar_count: "1/24"` 은 옛 관측값 (새 창 개시 이후 리셋 미반영)
- 새 P3 창은 `cr_new_p3_new_window_launch_2026-04-14.md` 에서 `P3_POSTSEAL_2026-04-15` 로 개시됨

Trackedness Preflight §7.2 분류상 `ops_state.json` = gitignored runtime artifact → change control 경로: **local reflection + tracked evidence receipt** (PR 불필요).

3-게이트 미저촉:
- 파괴적 삭제 ✗ (필드 값 갱신, 기존 invalidated_runs 는 보존)
- 실배포 / 실거래 ✗ (관측 tracker 필드, 거래 경로 아님)
- 비가역 변경 ✗ (revert = 이전 값으로 다시 편집)

→ **autonomous 가능**.

### 3.3 G (Trackedness Preflight rule 공식 문서화) — NEEDS_ACTION

이미 정의된 규칙 (cr_new_change3 §7.1):

1. **Preflight 3 checks**:
   - `git ls-files --error-unmatch <path>` → tracked 여부
   - `git check-ignore -v <path>` → gitignored 여부
   - local runtime artifact / external runtime artifact 분류

2. **Artifact 3-범주 분기** (§7.2):
   - tracked repo artifact → PR 기반 change control
   - gitignored runtime artifact → local reflection + tracked evidence receipt
   - external runtime artifact (DB rows, Redis keys) → 별도 operational procedure

공식 문서화 부족:
- receipt 본문 깊숙이 묻혀 있어 검색·인용이 불편
- `operating_constitution.md` 또는 신규 `trackedness_preflight_rule.md` 로 승격 필요

3-게이트 미저촉:
- 파괴적 삭제 ✗
- 실배포 / 실거래 ✗
- 비가역 변경 ✗ (tracked repo artifact, PR revert 가능)

→ **autonomous 가능**.

---

## 4. 집행 권고 (본 receipt 채택 후)

최소 안전장치 framework 하에서 autonomous 수행 허용:

### 4.1 E 실행 계획 (별도 changelog 엔트리 0007 예정)

1. `docs/operations/evidence/cr046_sol_stageb_post_seal_reset_2026-04-16.md` 작성 (local reflection receipt)
2. `ops_state.json` 편집:
   - `observation_tracks[0].baseline_at` → 새 창 baseline 시각 (p3_new_window_launch receipt 에서 확인)
   - `observation_tracks[0].bar_count` → `"0/24 (post-seal)"`
   - `observation_tracks[0].invalidated_runs` 에 pre-new-window 구분 append
   - `last_updated` 갱신
3. `docs/operations/changelog/0007_cr046-sol-bar-count-reset_2026-04-16.md` 기록

### 4.2 G 실행 계획 (별도 changelog 엔트리 0008 예정)

1. 신규 파일 `docs/operations/trackedness_preflight_rule.md` 작성 또는 `operating_constitution.md` §N 편입
2. 3 preflight check + 3 artifact category 서술
3. receipt chain cross-reference (cr_new_change3 §7)
4. `docs/operations/changelog/0008_trackedness-preflight-rule-formalization_2026-04-16.md` 기록

### 4.3 B 처리

추가 조치 없음. 본 receipt §3.1 결론으로 종결.

---

## 5. 판정 Confidence

| 항목 | Confidence | 잔여 불확실성 |
|---|---|---|
| B = NOT_APPLICABLE | HIGH | repo grep 0 hits 확실 |
| E = NEEDS_ACTION | HIGH | ops_state.json 실측 기반 |
| G = NEEDS_ACTION | HIGH | §7.1 정의 + NOT DONE 목록 명시 |

---

## 6. Signatures

- **Sealed**: 2026-04-16 claude-code (autonomous)
- **Framework**: 최소 안전장치 v1 (2026-04-16)
- **Precedent**: Turn 70~71 pending 8-item 분류 → 실 저장소 기반 재판정
- **Scope**: B/E/G 3 항목에 한정
- **Validity**: 본 receipt 채택 이후 해당 3 항목의 판정은 고정. 이후 상황 변경 시 별도 receipt 필요.
