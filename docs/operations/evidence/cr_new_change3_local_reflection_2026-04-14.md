# CR-NEW v3.1 Change-3 Local Reflection Evidence

**Doc ID**: cr_new_change3_local_reflection_2026-04-14
**Doc Path (repo-relative)**: docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md
**Created At**: 2026-04-14
**Signed By**: operator (A)
**approval_basis_doc**: CR-NEW v3.1
**approval_verdict**: APPROVED_A (Y1 rescope)
**Ledger Class**: VRL (Validation Result Ledger, 영구보존)

---

## 1. Premise Failure Summary

Original PR-B design attempted to commit `ops_state.json` Change-3 reflection as a repo-tracked PR. This premise failed a trackedness preflight:

- `.gitignore:136-137`:
  ```
  # Runtime state (environment-specific, not committed)
  /ops_state.json
  ```
- `git ls-files --error-unmatch ops_state.json` → *"did not match any file(s) known to git"*

Therefore `ops_state.json`은 gitignored runtime state이며 repo artifact가 아니다. CR-NEW v3.1 오염 P3 창·carryover 금지의 거버넌스 SSOT는 이미 다음 receipt에 봉인되어 있다:

`docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md` (sealed via PR #100 squash, parent commit `fc4a91c`).

---

## 2. Rescope Decision (Y1)

| 항목 | 판정 |
|---|---|
| 원래 전제: "ops_state.json → repo PR" | **CANCELLED** (premise failure) |
| 대체 전제: "local reflection + tracked evidence receipt" | **ADOPTED (Y1)** |
| `.gitignore` 정책 변경 | **NOT DONE** (L3+ out of scope) |
| 신규 ledger 파일 체계 신설 | **NOT DONE** (out of scope) |
| 로컬 `ops_state.json` 편집 | **PRESERVED** (되돌리지 않음) |
| 브랜치명 정정 | `cr-new/ops-state-change-3` → `cr-new/change3-local-reflection-evidence` |

---

## 3. Local Reflection Applied

로컬 `ops_state.json`에 세 가지 타겟 편집이 적용되었다.

### 3.1 `prohibitions` 항목 추가
- 추가: `"CRNEW_CARRYOVER_FORBIDDEN"`
- 위치: `prohibitions` 배열 말미
- 개수: 7 → 8

### 3.2 `contaminated_windows` 배열 신규 도입

```json
"contaminated_windows": [
  {
    "window_id": "P3_CONTAMINATED_PRESEAL_2026-04-14",
    "status": "SEALED_CONTAMINATED",
    "sealed_at": "2026-04-14T18:47Z",
    "seal_basis_receipt": "docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md",
    "recovery_cr": "CR-NEW v3.1",
    "source_squash_sha": "fba493e6f1d69c5f3135e6248296c08597a14442",
    "carryover_ban": {
      "reset_initial_state": true,
      "exclude_from_baseline_thresholds": true,
      "exclude_from_cumulative_stats": true,
      "exclude_from_evidence_stats": true
    },
    "allowed_meta_records": ["seal_receipt", "linkage_records"]
  }
]
```

### 3.3 `last_updated` 갱신
- 이전: `"2026-04-14T11:46Z"`
- 반영 후: `"2026-04-14T18:57Z"`
- `updated_by`: `"A+AI"` (유지)

---

## 4. Verification

| 검증 항목 | 값 |
|---|---|
| Local file path | `ops_state.json` (repo root, gitignored) |
| Reflection applied at | 2026-04-14T18:54–18:57Z (UTC minute) |
| JSON syntactic validity | **PASS** (`python -c "import json; json.load(open('ops_state.json', encoding='utf-8'))"`) |
| prohibitions count | 7 → 8 |
| CRNEW_CARRYOVER_FORBIDDEN present | True |
| contaminated_windows count | 0 → 1 |
| contaminated_windows[0].window_id | `P3_CONTAMINATED_PRESEAL_2026-04-14` |
| last_updated | 2026-04-14T11:46Z → 2026-04-14T18:57Z |
| Post-edit SHA256 (local) | `59d9a5eedca7ae18ee75f80f22cf7047a573e0af558cb9ee1b1e46104a4640f9` |

---

## 5. SSOT Declaration

| 역할 | 파일 | 상태 |
|---|---|---|
| Governance SSOT (source of truth) | `docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md` | tracked, PR #100 sealed (`fc4a91c`) |
| Local runtime mirror | `ops_state.json` | untracked (gitignored), environment-specific |

두 파일이 불일치할 경우 **tracked receipt가 우선한다**.
`ops_state.json`은 operator runtime tooling을 위한 편의적 미러이며, 거버넌스 원본이 아니다.

---

## 6. Scope Constraints (명문화)

이번 receipt의 적용 범위는 **local operator runtime reflection의 증거화**에 한정된다. 다음 항목은 명시적으로 범위 외:

- **NOT DONE**: `.gitignore` 정책 변경 (ops_state.json은 계속 gitignored 유지)
- **NOT DONE**: 신규 ledger 파일 체계 신설 (예: `docs/operations/governance_ledger/*.json`)
- **NOT DONE**: `ops_state.json`의 repo artifact 승격
- **NOT DONE**: 새 14D P3 창 개시 (별도 PR로 분리)
- **NOT DONE**: CR-046 SOL Stage B `bar_count` 재설정 (별도 PR로 분리)
- **NOT DONE**: P1 Recovery Smoke / P2 Observation Integrity Smoke 실행 (merge 후 별도 절차)

---

## 7. Learning (교훈) — Trackedness Preflight

### 7.1 Trackedness Preflight (신규 운영 규칙 후보)

PR 설계 전 반드시 다음 3개를 선행 확인:

- `git ls-files --error-unmatch <path>` → tracked인지
- `git check-ignore -v <path>` → gitignored인지
- 대상이 local runtime artifact / external runtime artifact인지

이번 premise failure는 이 preflight 누락에서 발생했다.

### 7.2 Artifact 3-범주 분기 규칙

향후 change control 설계는 대상 파일을 다음 3범주로 분류:

| 범주 | 예시 | Change control 경로 |
|---|---|---|
| **tracked repo artifact** | `app/*.py`, `docs/operations/evidence/*.md` | PR 기반 change control |
| **gitignored runtime artifact** | `ops_state.json`, `celerybeat-schedule*` | local reflection + tracked evidence receipt |
| **external runtime artifact** | DB rows, Redis keys | 별도 operational procedure |

---

## 8. Follow-up (후속 작업)

이 receipt merge 이후 다음 순서로 진행한다:

1. **P1 Recovery Smoke** (bounded real write, `market_states` 1행, 수집기 복구 검증)
2. **P2 Observation Integrity Smoke** (no new write, 관찰 대상 task 자연 write만 해석)
3. 모두 PASS 시 **새 14D P3 창 개시** (별도 PR)
4. 새 창 baseline 확정 시 CR-046 SOL Stage B `bar_count: "0/24 (post-seal)"` 초기화 (별도 PR)

---

## 9. Signatures

- **Sealed**: 2026-04-14 operator (A)
- **Change Control**: CR-NEW v3.1
- **Ledger Class**: VRL (영구보존)
- **Supersedes**: 없음 (신규)
- **Related Docs**:
  - `docs/operations/evidence/cr_new_p3_window_seal_2026-04-14.md` (SSOT, PR #100 sealed)
  - `ops_state.json` (local mirror, post-edit SHA256: `59d9a5eedca7ae18ee75f80f22cf7047a573e0af558cb9ee1b1e46104a4640f9`)
