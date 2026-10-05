# Operations Changelog

> 새 최소 안전장치(2026-04-16) 체계 하의 **변경 로그 + 사유** 저장소.
> 안전장치 rule #2: "모든 주요 변경은 무엇을 왜 바꾸었는지 로그와 변경 사유를 남겨야 한다."

## 파일 명명 규칙

`NNNN_<short-slug>_<YYYY-MM-DD>.md`

- `NNNN`: 0001부터 순차 증가 (zero-padded)
- `<short-slug>`: kebab-case 짧은 요약
- `<YYYY-MM-DD>`: 변경 적용 날짜

## 각 엔트리 최소 포맷

```markdown
# NNNN — <title>

**Date**: YYYY-MM-DD
**Author**: operator | claude-code
**Gate classification**: autonomous | explicit-approval
**Scope**: code | docs | ops_state | infra | governance

## What
<변경한 내용>

## Why
<변경 사유 — 근본 원인 또는 목적>

## Evidence
- 관련 파일 / PR / 이슈 / 증적 링크

## Reversibility
- 자율: reversible (commit revert 등)
- 명시승인: irreversible or 3-gate touched
```

## 3-게이트 분류 (Gate classification)

변경 작업은 아래 3가지를 **터치하면** `explicit-approval` 필요:

1. 파괴적 삭제 (permanent deletion)
2. 실제 배포 / 실거래 (actual deployment / live trading)
3. 비가역 변경 (irreversible change)

그 외는 `autonomous`.

## 인덱스 정책

- 본 디렉터리 진입 즉시 최신 순으로 sorted
- 큰 재구성(rule #3 "재설계")은 반드시 본 changelog에 기록
- 기존 `docs/operations/evidence/` 와는 목적 분리:
  - `evidence/` = 거버넌스/검증 receipts (VRL 등 ledger class)
  - `changelog/` = 실행자(claude-code 또는 operator)의 작업 이력

