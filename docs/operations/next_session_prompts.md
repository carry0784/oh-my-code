# Next Session Work Prompts (PR-A / PR-B)

**Created**: 2026-04-04
**Purpose**: Persist the finalized prompts for the next work session after Triage A5/A6-1/A6-2 closure (PR #25, #26, #27 all merged).
**Why this file exists**: The finalized PR-A/PR-B prompts were originally produced as in-conversation text only. This file persists them in the repository so they can be copied into a fresh Claude Code session.

---

## How to Use

1. Open a **new** Claude Code session (new terminal `claude` invocation, new IDE chat window, or new web/desktop conversation — not this context-heavy one).
2. Copy the "Short actionable" block for PR-A into the first message of that new session and run it to completion.
3. When PR-A is merged, start **another** new session and do the same for PR-B.
4. Do not run PR-A and PR-B in the same session.

---

## Session Starter (2-line instruction)

```
다음 작업은 PR-A (GitHub Actions Node 24 호환 업그레이드) 하나만 수행한다.
PR-A가 merge되기 전에는 PR-B를 시작하지 않는다.
```

Termination condition: PR-A가 main에 merge되고 3개 체크(lint/test/build) 모두 green이면 세션 종료.

---

## PR-A — GitHub Actions Node 24 호환 업그레이드

### Context

- GitHub가 Node 20 기반 JavaScript actions를 deprecate했다.
- 강제 Node 24 전환일: **2026-06-02**
- Node 20 런타임 완전 제거일: **2026-09-16**
- 현재 `.github/workflows/ci.yml`는 `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache@v4` 사용 → 전부 Node 20 기반.

### Short actionable (짧은 실전본)

```
목표: .github/workflows/ci.yml 의 actions 3개를 Node 24 호환 버전으로 고정 업그레이드한다.

변경:
- actions/checkout@v4      → actions/checkout@v5.0.0
- actions/setup-python@v5  → actions/setup-python@v6.0.0
- actions/cache@v4         → actions/cache@v5

범위:
- .github/workflows/ci.yml 한 파일만 수정
- ruff 버전(0.15.9)은 건드리지 않는다
- job 구조(lint/test/build)는 건드리지 않는다
- 캐시 키 prefix(linux-pip-*)는 건드리지 않는다

브랜치: ci/node24-upgrade
커밋 메시지: ci: upgrade actions to Node 24 compatible versions
PR 제목: ci: upgrade actions to Node 24 compatible versions

PR 본문에 포함할 항목:
1. Node 20 deprecation 타임라인 (2026-06-02 강제, 2026-09-16 제거)
2. 업그레이드한 3개 버전과 각 릴리스 노트 링크
3. 3개 체크(lint/test/build) 전부 green 확인 스크린샷 또는 로그

종료 조건:
- main 대상 PR 생성
- lint/test/build 3개 체크 모두 green
- squash merge 완료
- main에서 다음 push/PR에도 deprecation warning이 사라지는지 확인

롤백 계획:
- 만약 어떤 버전이 yanked 되거나 CI breakage를 유발하면 이전 버전(v4/v5/v4)으로 즉시 revert 하고 이슈에 원인 기록

주의:
- SHA pin은 이번 PR 범위에서 제외 (버전 태그 고정으로 충분)
- FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true 환경변수는 경고가 계속 나타나는 경우에만 fallback으로 추가
```

### Formal (정식본)

**배경**
GitHub Actions 플랫폼이 Node.js 20 런타임 기반 JavaScript actions를 deprecate 하고 Node.js 24로 전환하고 있다. 2026-06-02부로 모든 JavaScript actions가 Node 24에서 강제로 실행되며, 2026-09-16에는 Node 20 런타임이 완전히 제거된다. 현재 리포지토리의 `.github/workflows/ci.yml`는 `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache@v4`를 사용하는데 셋 다 Node 20 기반이므로, deprecation warning을 즉시 해소하고 2026-06-02 강제 전환 이전에 안정화해야 한다.

**범위**
- 단일 파일 수정: `.github/workflows/ci.yml`
- 3개 action을 명시적 버전으로 업그레이드:
  - `actions/checkout@v4` → `actions/checkout@v5.0.0`
  - `actions/setup-python@v5` → `actions/setup-python@v6.0.0`
  - `actions/cache@v4` → `actions/cache@v5`
- 건드리지 않는 것: ruff 버전 핀(0.15.9), job 구조, 캐시 키 prefix, timeout, permissions 블록

**업그레이드 전략 선택 이유**
- **명시 버전 고정** (v5.0.0 / v6.0.0 / v5): "시점 Marketplace 기준 최신 stable" 표현은 재현성이 떨어지므로 명확한 태그를 박는다.
- **SHA pin 제외**: 이번 PR은 Node 24 호환 확보가 목적이고, supply-chain hardening (SHA pin)은 별도 PR에서 다룬다.
- **FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true 조건부**: 위 3개 업그레이드만으로 warning이 사라지면 환경변수는 추가하지 않는다. 만약 다른 전이 의존 action이 warning을 발생시키면 그때만 해당 env를 fallback으로 추가한다.

**브랜치 / 커밋 / PR**
- 브랜치: `ci/node24-upgrade`
- 커밋 메시지: `ci: upgrade actions to Node 24 compatible versions`
- PR 제목: `ci: upgrade actions to Node 24 compatible versions`
- PR 본문 필수 항목:
  1. Node 20 deprecation 타임라인 (2026-06-02 / 2026-09-16)
  2. 업그레이드한 3개 버전과 각 릴리스 노트 링크
  3. 3개 체크(lint/test/build) 전부 green 확인

**검증**
1. PR push 직후 Actions 탭에서 lint/test/build 3개 job 독립 실행 확인
2. 각 job 로그에서 "Node.js 20 deprecated" 류 warning이 사라졌는지 확인
3. `ruff check .`, `ruff format --check .` 둘 다 0 exit
4. `pytest --cov=app --cov-report=term-missing -q` 로 test job green 유지
5. `pip install -e .` + `import kdexter` 로 build job green 유지
6. 3 체크 전부 green일 때 squash merge

**롤백 계획**
만약 v5.0.0 / v6.0.0 / v5 중 하나가 yanked 되거나 예기치 못한 CI breakage를 유발하면 즉시 해당 action만 이전 버전(v4 / v5 / v4)으로 revert 하고, PR 또는 이슈에 원인 및 재발 방지 계획을 기록한다.

**이번 PR에서 제외되는 것 (향후 작업)**
- actions 전부 SHA pin (별도 supply-chain PR)
- Python matrix 확장
- concurrency cancel policy
- coverage fail-under 기준선

**종료 조건**
- PR-A가 main에 merge됨
- main 브랜치의 다음 push/PR에서 deprecation warning 없음
- lint/test/build 3개 체크 green 유지

---

## PR-B — main Ruleset 강화

**사전 조건**: PR-A가 merge된 이후에만 시작한다.

### Short actionable (짧은 실전본)

```
목표: main 브랜치 Ruleset에 PR/리뷰/대화 해소 요구를 추가한다.

적용 대상: GitHub → Settings → Rules → Rulesets → main ruleset

활성화 항목:
1. Require a pull request before merging
   - Required approvals: 1
2. Require conversation resolution before merging
3. Require status checks to pass (기존 lint/test/build 유지)

승인 주체:
- write 또는 admin 권한을 가진 다른 계정 또는 협업자 1명의 승인이 필요하다
- GitHub 정책상 PR 작성자는 자신의 PR을 approve할 수 없다
- self-approval은 허용되지 않고 required approvals 카운트에 포함되지 않는다

BLOCK 조건:
- 단일 작업자 환경(협업자 없음)이라 다른 write/admin 승인 확보가 불가능하면,
  required approvals=1 적용을 보류하고 "승인자 확보 필요" 상태로 세션 종료한다.
- 이 경우에는 "Require conversation resolution" + "Require status checks" 만 먼저 적용한다.

검증:
- 설정 저장 후 임시 테스트 PR을 만들어 승인 없이 merge가 차단되는지 확인
- (BLOCK 조건이면) conversation 해소 없이 merge가 차단되는지만 확인
- 테스트 PR은 검증 후 close

주의:
- Ruleset bypass list에 본인 계정을 넣지 않는다
- force push는 이미 차단되어 있으면 추가 변경 없이 유지
```

### Formal (정식본)

**배경**
현재 main 브랜치 Ruleset은 status checks(lint/test/build)만 required로 설정되어 있어, PR 작성자가 리뷰 없이 스스로 merge할 수 있는 상태다. 변경 이력의 독립 검토와 미해결 코멘트 무시를 방지하기 위해 PR 경유 + 리뷰 승인 + conversation 해소 3가지 제약을 추가한다.

**GitHub 플랫폼 제약**
GitHub 공식 문서에 따르면:
1. PR 작성자는 자신의 PR에 대해 "Approve" 리뷰를 제출할 수 없다.
2. 작성자가 제출한 리뷰는 required approvals 카운트에 포함되지 않는다.
3. "Require review from Code Owners" 설정도 작성자 본인이 code owner여도 본인 승인으로는 만족되지 않는다.

따라서 `Required approvals: 1`을 활성화하려면 write 또는 admin 권한을 가진 **다른** 계정 또는 협업자가 최소 1명 존재해야 한다.

**적용 대상**
- GitHub → Settings → Rules → Rulesets → main ruleset (기존)
- 신규 ruleset을 만들지 않고 기존 ruleset에 항목 추가

**활성화 항목**
1. `Require a pull request before merging`
   - `Required approvals`: 1
   - `Dismiss stale pull request approvals when new commits are pushed`: ON
   - `Require approval of the most recent reviewable push`: ON
2. `Require conversation resolution before merging`: ON
3. `Require status checks to pass` (기존 유지)
   - Required checks: `lint`, `test`, `build`
   - `Require branches to be up to date before merging`: ON (선택)

**BLOCK 조건 (단일 작업자 환경)**
현재 리포지토리가 1인 작업자 환경이면 위 1번 항목의 `Required approvals: 1`을 만족시킬 수 있는 타인 계정이 존재하지 않는다. 이 경우:
- `Required approvals: 1`은 **적용 보류**
- 대신 "승인자 확보 필요" 상태로 세션을 종료
- 항목 2번(conversation resolution)과 3번(status checks)만 먼저 적용
- 협업자가 추가되면 별도 후속 세션에서 항목 1번을 추가 적용

이 BLOCK 조건을 무시하고 강제 적용하면 본인 PR을 merge할 수 없는 dead-lock에 빠진다.

**검증**
1. 설정 저장 직후 임시 테스트 브랜치 `ci/ruleset-verify-DELETEME`에서 사소한 변경(예: 주석 한 줄)으로 PR 생성
2. 승인 없이 merge 버튼이 회색/비활성인지 확인 (BLOCK 조건이면 이 단계 스킵)
3. 임의의 review comment를 추가하고 해소하지 않은 상태에서 merge가 차단되는지 확인
4. lint/test/build 3개 체크가 required로 붙는지 확인
5. 테스트 PR은 검증 완료 후 close, 브랜치 삭제

**Ruleset bypass 정책**
- 본인 계정을 bypass list에 절대 추가하지 않는다 (거버넌스 무력화 방지)
- emergency bypass가 필요하면 별도 세션에서 명시적 승인 후 임시로만 추가하고 작업 종료 시 제거

**이번 PR에서 제외되는 것 (향후 작업)**
- signed commit 요구
- linear history 강제
- CODEOWNERS 파일 도입
- 별도 브랜치 패턴(`release/*`, `hotfix/*`) ruleset

**종료 조건**
- 위 활성화 항목이 main ruleset에 저장됨
- 테스트 PR로 차단 동작 확인 완료
- (BLOCK 조건이 아닌 경우) Required approvals=1이 실제로 적용됨
- (BLOCK 조건인 경우) 항목 2/3번만 적용되고 항목 1번은 "승인자 확보 필요" 상태로 기록

---

## Execution Order

1. **PR-A 먼저** — 순수 파일 수정(ci.yml 1개)이라 safe-first.
2. **PR-A merge 확인 후 PR-B** — Ruleset 변경은 admin 권한 GUI 작업이라 별도 세션에서 집중 수행.
3. 두 세션 모두 완료 후에야 다음 단계(coverage fail-under, mypy, concurrency policy 등) 검토.

## Out of Scope (both PRs)

- `kdexter` + `app` 패키지 구조 통합 → 별도 설계 PR 필요
- Docker image build smoke
- Python 버전 matrix
- mypy strict 도입
- SHA-pin supply chain hardening
- CODEOWNERS 파일

---

## Source

These prompts are the finalized versions produced through expert-review iteration in the session that closed PR #25 / #26 / #27 on 2026-04-04. Key corrections applied during review:

- **PR-A**: Changed "latest stable tag" exploration language to explicit version fixing (`v5.0.0 / v6.0.0 / v5`). Made `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` a conditional fallback, not a default addition.
- **PR-B**: Removed invalid "self-approval" language (GitHub plat form disallows it). Added explicit BLOCK condition for single-operator environments. Added separate "GitHub 플랫폼 제약" section documenting the approval rules.
