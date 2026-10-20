# 0012 — PR decision (A안) + VAL-PDC-002 preflight + P3_END 자동전이 금지

**Date**: 2026-04-16
**Author**: claude-code (autonomous)
**Gate classification**: autonomous (4-gate 미저촉)
**Scope**: docs (3 새 파일)
**Framework**: v2 (`changelog/0006`)
**transition_class**: LOCAL_ONLY (commit, push 별도 — 필요 시 G4 재적용)

## What

3개 새 산출물 동시 추가:

### 1. `docs/operations/evidence/pr_open_decision_2026-04-16.md`
- L3 Shared Review Surface 전이 판정 receipt
- **A안 채택**: PR open 은 P3 종료 이후로 defer
- L3 는 G5 게이트로 승격하지 않고 framework v2 하위 영향권 전이 규칙으로 관리 (아이디어 1 채택)
- L3 전이 전제조건 C1~C3 명시 (시간 / 품질 / 명시 승인)

### 2. `docs/operations/val_pdc_002_preflight_inputs.md` v0.1
- Observation / Registry / Gate / Code / Docs / Forbidden preconditions 6 범주 체크리스트
- Output template DRAFT 포함 (판정 시 재사용)
- §4 P3_END 자동전이 금지 규칙 명문화 (아이디어 3 채택)
- Preflight 수행 시점 (지금 / P3 종료 1~2일 전 / 종료 시점 / 실행 후)

### 3. `docs/operations/evidence/ci_status_receipt_2026-04-16.md` (이미 생성, `changelog/0011` 에서 처리)

## Why

- 사용자 analysis response 2026-04-16 §5 2~3단계 + 6절 아이디어 1~3 전부 채택
- A안 근거: P3 관측 진행 / CI round-trip 회피 / 리뷰 부담 축소 / 보수적 운영
- PDC preflight 근거: `k_v3_residual_items_countermeasures.md` A-02 + REEVAL-PLAN-D001
- 자동전이 금지 근거: FT-06, FZ-07 + 아이디어 3

## Evidence

- CI 실측 (`changelog/0011`): feature branch push CI 발동 0건 → PR open 시에만 CI 발동 → A안 합리성 증명
- P3 새 창 identity: `cr_new_p3_new_window_launch_2026-04-14.md` §2.2
- bar_count 기준선: `cr046_sol_stageb_post_seal_reset_2026-04-16.md`

## 아이디어 수용 매핑

| 아이디어 | 채택 방식 |
|---|---|
| 1. PR Open 을 G5 로 안 올리고 L3 전이 규칙 | `pr_open_decision §3` |
| 2. CI 결과를 Constitution-linked Receipt 로 | `ci_status_receipt (changelog/0011)` Ledger Class |
| 3. P3_END 자동전이 금지 문구 | `val_pdc_002_preflight §4` |

## Reversibility

- 3 파일 추가 (편집 없음)
- `git rm` 으로 1 회 원복 가능
- P3_END 규칙은 기존 FT-06/FZ-07 보강이므로 제거해도 기존 안전장치 유지

## 4-Gate (v2) 미저촉

| Gate | 저촉 |
|---|---|
| G1 | ✗ |
| G2 | ✗ |
| G3 | ✗ |
| G4 | ✗ (local commit, push 시 재평가) |

## Follow-up

- P3 기간 중 autonomous 확장 금지 (사용자 단점 §3: 불필요한 문서 확장 억제)
- 2026-04-26~27: PDC preflight §2 재점검 예정
- 2026-04-28 이후: VAL-PDC-002 실행 여부 별도 판단
- H 보류 유지 (변함없음)
