# 0004 — TRCC Health Check / PLRAL Streak 스크립트 커밋

**Date**: 2026-04-16
**Author**: claude-code (autonomous)
**Gate classification**: autonomous (new script files, no execution wiring)
**Scope**: code (scripts/)

## What

`scripts/` 하위의 두 CLI 도구를 트리에 편입:

| 파일 | 줄 수 | 용도 |
|---|---|---|
| `scripts/health_check.py` | 1,223 | TRCC (Temporary Runtime Confirmation Card) v3 — 수동 실행 전용 헬스 확인 CLI |
| `scripts/plral_streak_check.py` | 495 | PLRAL streak (연속 정상가동) 계산 |

## Why

- `k_v3_visualization_layer_governance.md` VC-01~04 및 DP-1~4 원칙을 따르는 관측 전용 도구
- 이미 `.claude/settings.local.json` 의 allowlist 에 `python scripts/health_check.py` / `python scripts/plral_streak_check.py` 가 등재되어 실사용 전제임
- 미커밋 상태로는 운영자 간 공유·재현 불가
- 스크립트 자체는 read-only SELECT/GET + append-only file write 만 수행 (VC-01 no execution authority)

## 헌법 준수 확인 (VC-01~04, DP-1~4)

`scripts/health_check.py` 상단 docstring 에 명시:

- **VC-01**: no execution authority (read-only + file append)
- **VC-02**: display / summarize / compare only
- **VC-03**: no transition authorization
- **VC-04**: fail closed on missing data
- **DP-1**: Card ↔ PLRAL 단방향 (Card never reads PLRAL)
- **DP-4**: PLRAL has no execution authority (append-only file writes)

거버넌스(Operator Rules A–B): 실행 빈도 상한 하루 1–3회, VRL 수동 기록 별도 절차.

## Scope 확인

- 자동 실행 경로 (cron / systemd / Celery beat) 등록 없음
- `__pycache__` 미포함 (gitignored)
- `workers/` Celery task에서 import 없음 (수동 CLI 만)

## Reversibility

- 새 파일 추가만 수행
- `git rm scripts/health_check.py scripts/plral_streak_check.py` 로 즉시 원복 가능
- 타 모듈에서 import 없음 (독립 CLI)

## 3-Gate 미저촉 검증

- ✗ 파괴적 삭제
- ✗ 실배포 / 실거래 (read-only)
- ✗ 비가역 변경 (append-only file writes로 제한됨, 새 파일 추가는 revert 가능)

## 2026-04-28 폐기 일정

`health_check.py` docstring 에 명시되어 있듯 P3 윈도우 종료 시점(2026-04-28) 이후 폐기 예정.
폐기 작업은 별도 changelog 로 기록.

