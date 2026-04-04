# TEST-ORDERDEP-001 — Full-Suite Order-Dependent Failure

**등록일**: 2026-04-03
**분류**: Test Isolation Defect (운영 런타임 영향 없음)
**심각도**: LOW (격리 실행 시 전체 PASS)

---

## 1. 현상

전체 test suite (`pytest tests/`) 실행 시, 특정 테스트 순서 조합에서 간헐적 실패 발생.
격리 실행 (`pytest tests/test_ops_visibility.py tests/test_c15_notification_sender.py` 등) 시 **전부 PASS**.

## 2. 근본 원인

**settings MagicMock contamination.**

일부 테스트가 `app.core.config.settings` 객체를 `MagicMock`으로 교체한 후,
테스트 종료 시 원래 값으로 복원하지 않음.
이후 실행되는 테스트에서 `settings.exchange_mode`가 `MagicMock` 객체로 남아 있어:

- `assert settings.exchange_mode == "DATA_ONLY"` → FAIL (MagicMock ≠ "DATA_ONLY")
- JSON serialization 실패 (`TypeError: Object of type MagicMock is not JSON serializable`)

## 3. 영향 범위

| 영향 | 해당 여부 |
|------|-----------|
| 운영 런타임 | **없음** (settings mock은 테스트에서만 사용) |
| 격리 실행 테스트 | **영향 없음** (개별 파일 실행 시 PASS) |
| CI 전체 suite | **간헐 실패** (순서 의존) |
| 운영 기준선 | **영향 없음** |

## 4. 영향받는 테스트

| 테스트 | 실패 조건 |
|--------|-----------|
| `test_ops_visibility.py::test_status_includes_exchange_mode` | settings.exchange_mode가 MagicMock |
| `test_ops_visibility.py::test_bl_exmode01_config_default` | settings.exchange_mode가 MagicMock |
| `test_ops_restart_hygiene.py::TestHourlyCheckExchangeMode::test_hourly_check_exchange_mode_observation` | settings.exchange_mode가 MagicMock |

## 5. 해결 방향

1. settings를 mock하는 테스트에서 `monkeypatch` 또는 `pytest fixture`를 사용하여 자동 복원 보장
2. 또는 `conftest.py`에서 `settings` isolation fixture 추가
3. 또는 문제 테스트를 `pytest-forked`로 격리 실행

## 6. 현재 상태

**OPEN — 운영 긴급도 없음.**

격리 실행 시 전체 PASS이므로, 운영 기준선에는 영향 없음.
CI 안정화 시 수정 예정.

---

**TEST-ORDERDEP-001 등록 완료.**
