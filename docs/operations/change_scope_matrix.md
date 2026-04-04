# Change Scope Matrix — 변경 범위별 위험도 매트릭스

**작성일**: 2026-04-03
**상태**: ACTIVE
**승인자**: A

---

## 1. 목적

변경 대상별로 위험도 등급, 영향 받는 기준선 항목, 필수 검증, 승인 요건을 사전에 정의한다.
변경 착수 전 이 표를 참조하여 등급을 판정한다.

---

## 2. 변경 대상 매트릭스

### 문서 계층 (L0)

| 변경 대상 | 등급 | Baseline 영향 | 승인 | 필수 검증 | 롤백 |
|----------|:----:|:------------:|:----:|----------|------|
| docs/ 하위 문서 | L0 | 없음 | 불필요 | 없음 | git revert |
| CLAUDE.md | L0 | 없음 | 불필요 | 없음 | git revert |
| ops_state.json 문서 참조 수정 | L0 | 없음 | 불필요 | 없음 | git revert |

### 테스트 계층 (L1)

| 변경 대상 | 등급 | Baseline 영향 | 승인 | 필수 검증 | 롤백 |
|----------|:----:|:------------:|:----:|----------|------|
| 신규 테스트 추가 | L1 | 없음 | 불필요 | 회귀 PASS | git revert |
| 기존 테스트 수정 | L1 | 없음 | 불필요 | 회귀 PASS | git revert |
| conftest.py 수정 | L1 | 없음 | 불필요 | 전체 회귀 PASS | git revert |
| TEST-ORDERDEP-001 수정 | L1 | 없음 | 불필요 | 격리+전체 실행 | git revert |

### 관측 계층 (L2)

| 변경 대상 | 등급 | Baseline 영향 | 승인 | 필수 검증 | 롤백 |
|----------|:----:|:------------:|:----:|----------|------|
| 읽기 전용 API 추가 | L2 | 없음 | 불필요 | baseline-check + 회귀 | git revert |
| /status 필드 추가 (기존 불변) | L2 | 없음 | 불필요 | baseline-check | git revert |
| 로그 출력 추가 | L2 | 없음 | 불필요 | startup log 검증 | git revert |
| 대시보드 읽기 기능 | L2 | 없음 | 불필요 | baseline-check | git revert |

### 런타임 계층 (L3)

| 변경 대상 | 등급 | Baseline 영향 항목 | 승인 | 필수 검증 | 롤백 |
|----------|:----:|:----------------:|:----:|----------|------|
| beat schedule 항목 추가 (active) | L3 | disabled_beat_tasks | A | baseline-check + restart drill | git revert + beat restart |
| ops_state.json 값 변경 | L3 | operational_mode | A만 편집 | baseline-check | A가 직접 원복 |
| lifespan 로직 변경 | L3 | startup logs | A | startup log + baseline-check | git revert |
| _startup_fingerprint 변경 | L3 | startup logs | A | fingerprint 검증 | git revert |
| stale guard 로직 변경 | L3 | forbidden tasks | A | restart drill + beat 검증 | git revert |

### 정책/실행 계층 (L4)

| 변경 대상 | 등급 | Baseline 영향 항목 | 승인 | 필수 검증 | 롤백 |
|----------|:----:|:----------------:|:----:|----------|------|
| exchange_mode 변경 | L4 | exchange_mode | Hold 해제 + A | 전면 재검증 | 설정 원복 + baseline-check |
| blocked API 해제 | L4 | blocked_api_count | Hold 해제 + A | 25 adapter test | guard 원복 |
| disabled task 재활성화 | L4 | disabled_beat_tasks | Hold 해제 + A | beat + Flower 검증 | schedule 원복 |
| _require_mode() guard 변경 | L4 | blocked_api_count | Hold 해제 + A | 25 adapter test | git revert |
| 금지 task schedule 등록 | L4 | forbidden tasks | Hold 해제 + A | Flower 감시 | schedule 원복 |
| 실주문 경로 활성화 | L4 | 전체 | Hold 해제 + A | 전면 재검증 | 전면 원복 |

---

## 3. Baseline 영향 항목 역참조표

| Baseline 항목 | 영향 가능 변경 | 최소 등급 |
|--------------|-------------|:--------:|
| `operational_mode` | ops_state.json 편집 | L3 |
| `exchange_mode` | config.py, exchange adapter | L4 |
| `blocked_api_count` | _API_MATRIX, _require_mode() | L4 |
| `disabled_beat_tasks` | _BEAT_TASKS, beat_schedule | L3~L4 |
| `forbidden_beat_tasks_absent` | beat_schedule | L4 |
| `startup_log_consistency` | lifespan, _startup_fingerprint | L3 |

---

## 4. 필수 검증 묶음 참조표

| 검증 묶음 | 내용 | 사용 시기 |
|----------|------|----------|
| **baseline-check** | `GET /api/v1/ops/baseline-check` 6/6 HOLD | L2 이상 모든 변경 |
| **회귀** | `pytest tests/test_ops_*.py tests/test_restart_drill.py` | L1 이상 모든 변경 |
| **restart drill** | `pytest tests/test_restart_drill.py` | L3 이상 |
| **25 adapter test** | 5 어댑터 × 5 guarded API 차단 검증 | L4 (guard 변경 시) |
| **Flower 감시** | 금지 3 task 미발송 확인 | L3 이상 (schedule 변경 시) |
| **전면 재검증** | baseline-check + 회귀 + restart drill + adapter test + Flower | L4 |

---

**Change Scope Matrix 작성 완료.**
