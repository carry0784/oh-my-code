# Baseline Hold 4단계 강화 계획 — 완료 증빙

**문서 ID:** BASELINE-HOLD-STRENGTHEN-001
**작성일:** 2026-04-03
**작성자:** System (A 지시에 의거)
**판정 권한:** A

---

## 1. 배경

Baseline Hold ACTIVE 상태에서 운영 안정성을 확인하고 강화하기 위해
A가 4단계 강화 계획을 지시함 (2026-04-03).

**전제 조건:**
- Baseline Hold = ACTIVE
- Gate = LOCKED
- 허용 범위: L0 (문서) ~ L1 (테스트) ~ L2 (관측 코드)
- L3-L4 (런타임/정책) = 차단

---

## 2. 4단계 강화 계획 결과

| 단계 | 내용 | 리스크 등급 | 결과 | A 판정 |
|------|------|-----------|------|--------|
| 1 | 기준선 점검 자동화 (`GET /baseline-check`) | L2 | 6항목 자동 측정, HOLD 판정 정상 | **ACCEPTED** |
| 2 | 재기동/복구 Drill (`test_restart_drill.py`) | L1 | 17 tests 전부 PASS | **ACCEPTED** |
| 3 | 변경 재진입 Gate (`GET /change-gate`, L0-L4 정책) | L2 | LOCKED 상태 정상 반환, 80/80 PASS | **ACCEPTED** |
| 4 | TEST-ORDERDEP-001 정리 | L1 | 오염원 5파일 봉합, 합동 75/75 PASS | **RESOLVED** |

---

## 3. 단계별 상세

### 3-1. 기준선 점검 자동화

**구현:** `app/api/routes/ops.py` — `GET /baseline-check`

**6항목 자동 측정:**

| # | 항목 | 기대값 | 자동 판정 |
|---|------|--------|-----------|
| 1 | operational_mode | BASELINE_HOLD | PASS/FAIL |
| 2 | exchange_mode | DATA_ONLY | PASS/FAIL |
| 3 | blocked_api_count | >= 3 | PASS/FAIL |
| 4 | disabled_beat_tasks | >= 3 | PASS/FAIL |
| 5 | forbidden_beat_tasks_absent | True | PASS/FAIL |
| 6 | startup_log_consistency | True | PASS/FAIL |

**결과:** 전 항목 PASS → `drift_status: "HOLD"` 반환 확인.

**관련 문서:**
- `docs/operations/baseline_hold_runbook.md`

### 3-2. 재기동/복구 Drill

**구현:** `tests/test_restart_drill.py` — 17 tests

**검증 범주:**

| 범주 | 테스트 수 | 내용 |
|------|----------|------|
| App restart API | 3 | `/baseline-check` HOLD, `/status` BASELINE_HOLD, `/governance-state` 정상 로딩 |
| Beat schedule recovery | 3 | 금지 3개 task 미등록, 활성 task 존재, dry_run=True |
| Celery fingerprint | 3 | `_startup_fingerprint` 호출 가능, 필수 카운트 포함 |
| ops_state.json 무결성 | 6 | 파일 존재, JSON 파싱, 필수 키, updated_by=A, 운영 모드, 기대값 |
| Startup log sequence | 2 | 문서 존재 확인 |

**결과:** 17/17 PASS.

### 3-3. 변경 재진입 Gate

**구현:** `app/api/routes/ops.py` — `GET /change-gate`

**L0-L4 리스크 분류:**

| 등급 | 허용 여부 (Hold 중) | 예시 경로 |
|------|-------------------|-----------|
| L0 | 허용 (자동) | `docs/` |
| L1 | 허용 (자동) | `tests/` |
| L2 | 허용 (검토 후) | `app/api/routes/ops.py` |
| L3 | **차단** (A 승인 필수) | `app/main.py`, `ops_state.json` |
| L4 | **차단** (Hold 해제 필요) | `exchanges/`, `app/core/config.py` |

**관련 문서:**
- `docs/operations/change_gate_policy.md`
- `docs/operations/change_scope_matrix.md`
- `docs/operations/change_reentry_checklist.md`
- `docs/operations/change_reentry_review_template.md`

**결과:** Gate=LOCKED 정상 반환, 경로별 리스크 분류 정상, 80/80 PASS (기존 테스트 포함).

### 3-4. TEST-ORDERDEP-001 정리

**원인:**
CR-043 Phase 6 테스트 5개 파일이 모듈 수준에서 `sys.modules`에 MagicMock 주입 후 미복원.
후속 테스트 파일 수집 시 `celery`, `sqlalchemy`, `app.core.config.settings` 등이 MagicMock 상태로 오염.

**오염원 파일 (5개):**
- `tests/test_correlation_analyzer.py`
- `tests/test_portfolio_constructor.py`
- `tests/test_portfolio_metrics.py`
- `tests/test_portfolio_optimizer.py`
- `tests/test_risk_budget_allocator.py`

**수정 방식 — 2계층 방어:**

| 계층 | 위치 | 동작 |
|------|------|------|
| 1차 방어 | 오염원 5개 파일 | import 직후 `sys.modules` 즉시 복원 + `settings` 원본 복원 |
| 2차 방어 | `tests/conftest.py` autouse fixture | 매 테스트 후 보호 모듈 10개 + settings 복원 |

**핵심 패턴 (각 오염원 파일):**
```python
# 수집 시: mock 주입 → 대상 서비스 import
_saved_modules = {}
_added_modules = set()
for _name in _STUB_MODULES:
    if _name in sys.modules:
        _saved_modules[_name] = sys.modules[_name]
    else:
        _added_modules.add(_name)
        sys.modules[_name] = MagicMock()

# ... target import ...

# 수집 직후: 즉시 복원
for _name, _orig in _saved_modules.items():
    sys.modules[_name] = _orig
for _name in _added_modules:
    sys.modules.pop(_name, None)
if _orig_settings is not None and "app.core.config" in sys.modules:
    sys.modules["app.core.config"].settings = _orig_settings
```

**검증 결과:**

| 테스트 | 결과 |
|--------|------|
| 합동 테스트 (오염원 5 + 피해자 2) | **75/75 PASS** |
| 전체 회귀 | **4442 passed, 2 failed** |
| 신규 실패 | **0건** |

---

## 4. 전체 회귀 결과

```
4442 passed, 2 failed (177.15s)
```

**기존 실패 2건 (본 수정과 무관):**

| 테스트 | 소속 | 원인 |
|--------|------|------|
| `test_binance_adapter_spot_mode` | CR-036 | Binance adapter `__init__` 소스에서 `defaultType: spot` 문자열 매칭 실패 |
| `test_alembic_env_imports_snapshot` | CR-043 | `alembic/env.py`에 `AssetSnapshot` import 미존재 |

**판정:** 두 건 모두 TEST-ORDERDEP-001 이전부터 존재한 기존 이슈. 본 수정으로 인한 신규 실패 = 0.

---

## 5. 현재 운영 상태

| 항목 | 값 |
|------|-----|
| Baseline Hold | **ACTIVE** |
| Gate | **LOCKED** |
| operational_mode | BASELINE_HOLD |
| exchange_mode | DATA_ONLY |
| 신규 실패 | 0 |
| 기존 실패 | 2건 (CR-036, CR-043) |
| TEST-ORDERDEP-001 | **RESOLVED** |
| ops_state.json open_issues 제거 | **A 편집 권한 대기** |

---

## 6. 수정 파일 목록

| 파일 | 변경 유형 | 리스크 등급 |
|------|----------|-----------|
| `tests/conftest.py` | autouse guard 추가 | L1 |
| `tests/test_correlation_analyzer.py` | 즉시 복원 블록 추가 | L1 |
| `tests/test_portfolio_constructor.py` | 즉시 복원 블록 추가 | L1 |
| `tests/test_portfolio_metrics.py` | 즉시 복원 블록 추가 | L1 |
| `tests/test_portfolio_optimizer.py` | 즉시 복원 블록 추가 | L1 |
| `tests/test_risk_budget_allocator.py` | 즉시 복원 블록 추가 | L1 |
| `app/api/routes/ops.py` | baseline-check, change-gate 엔드포인트 추가 | L2 |
| `app/main.py` | governance_state_loaded 로그 추가 | L2* |
| `workers/celery_app.py` | operational_mode fingerprint 추가 | L2* |
| `tests/test_ops_visibility.py` | 30 tests (15→30 확장) | L1 |
| `tests/test_restart_drill.py` | 17 tests 신규 | L1 |
| `docs/operations/baseline_hold_runbook.md` | 신규 | L0 |
| `docs/operations/change_gate_policy.md` | 신규 | L0 |
| `docs/operations/change_scope_matrix.md` | 신규 | L0 |
| `docs/operations/change_reentry_checklist.md` | 신규 | L0 |
| `docs/operations/change_reentry_review_template.md` | 신규 | L0 |

*L2 범위이나 관측/로깅 목적으로 A 사전 승인 하에 수행됨.

---

## 7. 후속 작업

| 순서 | 내용 | 상태 |
|------|------|------|
| 1 | 본 증빙 문서 작성 | ✅ 완료 |
| 2 | 기존 실패 2건 L1 수정 | 대기 |
| 3 | Baseline Hold 해제 조건 평가 | 대기 (2번 완료 후) |
| — | ops_state.json open_issues 제거 | A 편집 권한 대기 |
| — | CR-046 SOL Stage B 테스트넷 모니터링 | 관측 유지 |
