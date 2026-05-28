# 0006 — Minimum Safety Framework Revision: G4 Remote Visibility Gate 채택 (v1 → v2)

**Date**: 2026-04-16
**Author**: operator (directive) + claude-code (execution)
**Gate classification**: governance — directive-level
**Scope**: governance (framework)
**transition_class**: LOCAL_ONLY (본 changelog 자체)

## What

최소 안전장치를 **3-gate → 4-gate** 로 확장하여 **v2** 로 승격.

### v2 (2026-04-16 채택)

| Gate | 내용 | 게이트 유형 |
|---|---|---|
| **G1** | 파괴적 삭제 → 명시 승인 | 영구 금지 경로 |
| **G2** | 실배포 / 실거래 → 명시 승인 | 운영 전이 |
| **G3** | 비가역 변경 → 명시 승인 | 복원 불가 |
| **G4** | **원격 공개 / 가시성 전이 → 명시 승인** (신규) | 협업 / 해석 기준선 |

### v2 에서 새로 정식화된 조항

#### G4 정의

> 로컬 commit 은 autonomous 수행 가능하되, `git push`, PR 생성, fork 공개, 외부 복제 등으로 **협업자 / CI / review 표면 / 해석 기준선** 에 변화를 주는 전이는 **별도 명시 승인 대상**.

#### 판정 기준

다음 중 **하나 이상** 해당 시 G4 승인 필요:

- `git push` 로 remote branch 갱신 (feature branch 포함)
- GitHub PR / MR open / update
- fork / mirror 공개
- 외부 CI (GitHub Actions 등) 트리거로 이어지는 행위
- artifact 업로드 (Docker image, package registry, S3 등)

다음은 **G4 대상 아님** (여전히 autonomous):

- local commit (branch 이동 없이 HEAD 만 전진)
- local branch 생성 / 이동 / 삭제
- local stash / reset (local only)

#### G4 승인 요청 형식 (receipt 에 포함)

```yaml
push_approval_request:
  target_branch: <origin/xxx>
  commits: [SHA_list]
  file_count: N
  lines_delta: +X / -Y
  expected_visibility_delta:
    - <협업자 관점 변화 요약>
    - <CI 트리거 예상 여부>
    - <PR 가능성>
  transition_class: REMOTE_VISIBLE
  reversibility: <git push --delete / revert 가능 여부>
```

## Why

`local_commits_constitutional_review_2026-04-16.md` §7 에서 제안된 G4 는 다음 운영 현실에서 필요성 증명:

- `git push` 는 기술적으로 reversible 일 수 있어도 **협업 가시성, 해석 기준선, 검토 표면** 을 변경
- v1 의 3-gate (파괴삭제 / 실거래·실배포 / 비가역) 만으로는 "원격 공개" 가 애매한 중간 지대에 놓임
- 2026-04-16 local commits 4 건이 실제로 이 중간 지대에 위치 → 운영 규격화 필요

## 영향권 분류 (참조 모델, 본 changelog 에서 공개)

사용자 권고 (더 좋은 아이디어 1) 에 따라 **영향권(L1~L4) 기준** 도 병행 사용:

| 영향권 | 정의 | 해당 게이트 |
|---|---|---|
| **L1 Local Mutation** | local filesystem / git local state 만 변경 | autonomous |
| **L2 Remote Visibility** | remote branch 갱신, PR open | **G4** |
| **L3 Shared Branch / Review Surface** | main/develop branch 변경, review 요청 | **G4 + 프로젝트 PR 정책** |
| **L4 Live Execution** | production 운영 전이, 실거래 | **G1+G2+G3** 복합 |

v2 framework 는 G1~G4 를 위험 성격 기준으로 두고, L1~L4 는 영향권 기준 보조 분류로 사용.

## receipt transition_class 필드 도입 (더 좋은 아이디어 2 채택)

2026-04-16 이후 작성되는 **모든 receipt** 는 다음 필드 포함:

```yaml
transition_class: LOCAL_ONLY | REMOTE_VISIBLE | SHARED_REVIEW | LIVE_PATH
```

매 receipt 마다 G4 논점이 반복되는 것을 방지.

## evidence_index major reissue 임계치 (더 좋은 아이디어 3 채택)

다음 중 **하나라도** 충족 시 `evidence_index.md` major reissue 검토:

- 누적 delta ≥ 100 파일
- 총 파일 수 변화율 ≥ 20%
- original §1~§16 내부 카운트 불일치 section 3 개 이상

현재 상태 (2026-04-16): delta +138 / 변화율 +56.8% → **임계치 초과**.
다만 직전 append-only §17 로 즉시 봉합 완료되었으므로 reissue 우선순위는 낮음. 다음 major 검토 시점: 2026-05-01 또는 delta +200 중 먼저.

## Evidence

- `docs/operations/evidence/local_commits_constitutional_review_2026-04-16.md` §7 (G4 제안 근거)
- `docs/operations/changelog/0001_minimum-safety-framework-adoption_2026-04-16.md` (v1 원문)
- 사용자 analysis response (2026-04-16) — G4 채택 권고 + L1~L4 / transition_class / major reissue 임계치 도입 승인

## Reversibility

- 본 changelog 자체는 영구 이력 (append-only)
- G4 해제는 별도 framework revision changelog (예: 0009 revision back to v1) 로 가능
- v2 채택 이후 발행된 receipt 의 `transition_class` 필드는 유지

## 3-Gate 미저촉 검증 (v1 기준 / v2 도 동일)

| 게이트 | 저촉 |
|---|---|
| G1 파괴적 삭제 | ✗ |
| G2 실배포 / 실거래 | ✗ |
| G3 비가역 변경 | ✗ (framework 문서 추가) |
| G4 원격 공개 (new) | ✗ (본 changelog 는 local only 기록) |

## 이후 receipt 적용

- `0007_cr046-sol-bar-count-reset_2026-04-16.md` — transition_class: LOCAL_ONLY (gitignored runtime artifact)
- `0008_trackedness-preflight-rule-formalization_2026-04-16.md` — transition_class: LOCAL_ONLY (local commit, push 별개)
- `0009_remote-push-approval-request_2026-04-16.md` — transition_class: REMOTE_VISIBLE (G4 승인 요청 receipt, 사용자 조건부 승인 이미 확인됨)

## Status

- **Framework version**: v2 (2026-04-16 발효)
- **Supersedes**: v1 (2026-04-16 원문, `changelog/0001`)
- **Authority**: 사용자 명시 analysis response (2026-04-16)
