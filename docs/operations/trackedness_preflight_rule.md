# Trackedness Preflight Rule

**Document Type**: Operational Rule (governance)
**Issue Date**: 2026-04-16
**Version**: v1.0
**Status**: ACTIVE
**Authority**: 사용자 analysis response 2026-04-16 — 승인 ③ "G autonomous 집행: 예"
**Source**: `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` §7 (규칙 원문)
**Framework**: 최소 안전장치 v2 (`docs/operations/changelog/0006_framework-revision-g4-adoption_2026-04-16.md`)
**transition_class**: LOCAL_ONLY (본 문서 작성, PR 별도)
**Ledger Class**: OPERATIONAL_RULE (규칙 문서, VRL 아님)

---

## 0. 목적 (Purpose)

PR 설계 / 변경 착수 이전에 **대상 파일 / 경로의 tracked 여부** 를 선행 검증하여, 다음 오류를 예방한다:

- gitignored runtime artifact 를 PR 스코프에 포함시키는 premise failure
- tracked repo artifact 를 local reflection 만으로 처리하려는 scope leak
- external runtime artifact (DB rows, Redis keys 등) 를 git 기반 change control 로 오해

본 규칙의 원본 발생 배경은 `cr_new_change3_local_reflection_2026-04-14.md` §7 의 **premise failure 사례** 로, 동일 오류의 재발을 방지한다.

---

## 1. Rule Scope

### 1.1 What this rule IS

- 모든 **변경 설계 / PR 작성 / local reflection receipt 작성** 이전 선행 체크리스트
- claude-code autonomous 실행 / operator manual 실행 모두 적용
- 파일 / 디렉토리 / 경로 단위로 적용

### 1.2 What this rule is NOT

- code 구현 규칙 아님
- 테스트 규칙 아님
- 배포 규칙 아님
- 특정 CR / sealed chain 에 대한 특례 아님 (전역 적용)

---

## 2. Preflight 3 Checks (필수)

변경 대상으로 지정된 모든 경로에 대해 다음 3 check 를 **사전 수행**:

### Check 1 — Tracked 여부

```bash
git ls-files --error-unmatch <path>
```

- exit code 0: tracked repo artifact
- exit code 1: untracked 또는 gitignored

### Check 2 — gitignored 여부

```bash
git check-ignore -v <path>
```

- exit code 0 + 출력: gitignored (규칙과 함께 표시)
- exit code 1: gitignore 규칙 무매치

### Check 3 — Artifact category 분류

Check 1 / Check 2 결과 조합에 따라 아래 §3 범주 중 하나로 분류.

---

## 3. Artifact 3-범주 분기 규칙

| Check 1 | Check 2 | 범주 | 예시 | Change Control 경로 |
|---|---|---|---|---|
| tracked (0) | not-ignored (1) | **tracked repo artifact** | `app/*.py`, `docs/operations/evidence/*.md`, `docker-compose.yml`, `tests/*.py`, `strategies/ppf/*.py` | PR 기반 change control (branch → PR → review → merge) |
| not-tracked (1) | ignored (0) | **gitignored runtime artifact** | `ops_state.json`, `celerybeat-schedule*`, `logs/*.log`, `.env` | local reflection + tracked evidence receipt (PR 불필요, receipt 는 tracked) |
| (N/A) | (N/A) | **external runtime artifact** | DB rows (`market_states` 테이블), Redis keys, Celery broker state, filesystem outside repo | 별도 operational procedure (git 기반 change control 대상 아님) |

**중요**: 동일 변경에 다중 범주 파일이 섞여 있으면, 각 범주별로 분리 처리. 절대 혼합 PR 금지.

---

## 4. Log Fields (receipt / changelog 에 포함 필수)

Preflight 수행 시, 결과를 다음 형태로 receipt 또는 changelog 에 기록:

```yaml
trackedness_preflight:
  path: <target_path>
  ls_files_exit: 0|1
  check_ignore_exit: 0|1
  category: tracked_repo | gitignored_runtime | external_runtime
  change_control_path: PR | local_reflection | operational_procedure
  verified_at: <UTC_timestamp>
  verifier: claude-code | operator
```

여러 파일 동시 작업 시 리스트 구조 허용.

---

## 5. Prohibitions (금지 사항)

다음 패턴은 명시적으로 금지:

### 5.1 범주 혼합 PR 금지

tracked repo artifact + gitignored runtime artifact 를 같은 PR 에 포함 금지.
→ gitignored 대상은 local reflection + evidence receipt 로 분리.

### 5.2 gitignored → PR 우회 금지

`ops_state.json` 같은 gitignored artifact 를 PR 에 억지로 포함시키기 위해 `.gitignore` 편집 금지.
→ gitignore 편집은 별도 CR.

### 5.3 external runtime artifact 를 git 에 편입 금지

DB rows, Redis keys, broker state 등을 dump 파일로 만들어 git 에 포함 금지.
→ 별도 operational procedure.

### 5.4 Preflight 생략 금지

"명백히 tracked" / "명백히 runtime" 라는 주관적 판단으로 preflight 3 check 생략 금지.
→ 모든 경우에 3 check 수행, cost 매우 낮음.

---

## 6. Enforcement

### 6.1 Claude-code autonomous 실행

- 모든 변경 receipt / changelog 작성 시 §4 log fields 포함
- 범주 불일치 탐지 시 HALT 후 사용자 확인 요청
- 본 규칙 미준수는 receipt 무효 사유

### 6.2 Operator manual 실행

- PR description 또는 local reflection receipt 에 §4 log fields 포함 권장
- 자동화되지 않은 경우 manual check + 기록

### 6.3 CI 검증 (future work, 별도 CR)

- pre-commit hook 또는 CI step 으로 `git ls-files` / `git check-ignore` 를 자동 실행하여 preflight log 를 생성하는 방안 검토
- 본 문서 범위 외

---

## 7. 적용 예시

### 7.1 예시 A — tracked repo artifact

대상: `app/services/observation_chain_service.py`

```yaml
trackedness_preflight:
  path: app/services/observation_chain_service.py
  ls_files_exit: 0        # tracked
  check_ignore_exit: 1    # not ignored
  category: tracked_repo
  change_control_path: PR
  verified_at: 2026-04-16T12:00:00Z
  verifier: claude-code
```

→ branch 생성 → 수정 → PR open → review → merge

### 7.2 예시 B — gitignored runtime artifact

대상: `ops_state.json`

```yaml
trackedness_preflight:
  path: ops_state.json
  ls_files_exit: 1        # not tracked
  check_ignore_exit: 0    # ignored (rule: ops_state.json)
  category: gitignored_runtime
  change_control_path: local_reflection
  verified_at: 2026-04-16T12:00:00Z
  verifier: claude-code
```

→ local reflection receipt 작성 (`docs/operations/evidence/*.md`, tracked) → 직접 편집 → changelog

(본 rule 이 정의되기 전 실사례: `changelog/0007_cr046-sol-bar-count-reset_2026-04-16.md` 에서 동일 패턴 적용)

### 7.3 예시 C — external runtime artifact

대상: DB table `market_states` 의 row 삭제

```yaml
trackedness_preflight:
  path: <DB table market_states rows>
  ls_files_exit: N/A
  check_ignore_exit: N/A
  category: external_runtime
  change_control_path: operational_procedure
  verified_at: 2026-04-16T12:00:00Z
  verifier: operator
```

→ git PR 불가, DB operational procedure (`docs/operations/*.md` 에 정의된 절차) 준수.
→ 현재 프로젝트 context 에서는 G1 파괴적 삭제 게이트 해당 시 명시 승인 필수.

---

## 8. Version / Revision

- v1.0 (2026-04-16): 최초 공식화
- 규칙 원문 출처: `cr_new_change3_local_reflection_2026-04-14.md` §7.1 / §7.2
- 본 문서는 원문을 **운영 규칙으로 승격** 하되 해석·변형 없이 표로 재구성 + enforcement 절 추가

### Revision 정책

- 본 규칙의 core 3 category (§3) 는 **변경 금지** (변경 시 별도 CR)
- §4 log fields / §5 prohibitions / §6 enforcement 는 revision 가능 (별도 changelog 기록)
- 해석 보강 / 예시 추가 는 append-only 허용

---

## 9. Cross-References

- **원문 근거**: `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` §7
- **재판정 근거**: `docs/operations/evidence/beg_residual_reassessment_2026-04-16.md` §3.3 (G = NEEDS_ACTION)
- **적용 실사례**: `docs/operations/evidence/cr046_sol_stageb_post_seal_reset_2026-04-16.md` §2 (gitignored runtime artifact 분류)
- **상위 framework**: `docs/operations/changelog/0006_framework-revision-g4-adoption_2026-04-16.md` (최소 안전장치 v2)
- **기존 헌법 문서**: `docs/operations/operating_constitution.md` (본 rule 은 편입 아닌 별도 문서 — 승인 권고 "G 신규 문서화")

---

## 10. Signatures

- **Published**: 2026-04-16 claude-code (autonomous, 사용자 승인 ③)
- **Framework**: 최소 안전장치 v2
- **transition_class**: LOCAL_ONLY (본 문서 commit, push 별개 승인)
- **Ledger**: OPERATIONAL_RULE
- **Supersedes**: 없음 (신규 규칙, 기존 receipt §7 원문은 그대로 유지)
