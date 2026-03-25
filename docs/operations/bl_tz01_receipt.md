# BL-TZ01 Receipt — trading_safety_panel timezone mismatch fix

## Status

RESOLVED

## Scope

`_compute_trading_safety_panel()` 내 timezone aware/naive mismatch 국소 해소

## Problem

S-01 live smoke에서 `trading_safety_panel` 계산 시 PostgreSQL 쿼리 파라미터의 timezone aware/naive mismatch 경고가 관찰됨.

오류 메시지:
```
can't subtract offset-naive and offset-aware datetimes
```

## Root Cause

- `Order.created_at`: SQLAlchemy `DateTime` 컬럼 → PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` (naive)
- `recent_cutoff`: `datetime.now(timezone.utc) - timedelta(hours=24)` → timezone-aware
- asyncpg가 aware datetime을 naive 컬럼과 비교할 때 mismatch 발생

## Fix Summary

- `datetime.now(timezone.utc)` → `datetime.utcnow()` 로 변경하여 naive UTC cutoff 생성
- DB 컬럼 타입(naive)과 쿼리 파라미터 타입(naive)을 일치시킴
- 수정 위치: `app/api/routes/dashboard.py` 내 `_compute_trading_safety_panel()` 함수 1줄

## Constitutional Check

| 항목 | 확인 |
|------|------|
| fail-closed 성질 유지 | 확인 — try/except 구조 그대로 |
| 위험한 성공 경로 추가 없음 | 확인 |
| 범위 외 기능 추가 없음 | 확인 |
| unrelated panel 영향 없음 | 확인 — trading_safety_panel만 수정 |
| 시간 비교 의미 왜곡 없음 | 확인 — 동일 UTC 기준, 타입만 일치 |
| 경고 은폐 없음 | 확인 — 원인 수정 |

## Tests

- 회귀 테스트: 243 passed
- live smoke: timezone mismatch 오류 메시지 소멸 확인
- 수정 후 파라미터: naive datetime으로 정상 전달 확인

## Remaining Risk

- `OrderStatus.REJECTED` enum이 PostgreSQL DB enum과 불일치하는 별도 이슈 관찰됨. 이것은 timezone과 무관한 DB 스키마 이슈이며 BL-TZ01 범위 밖. 별도 backlog(BL-ENUM01)으로 분리 권장.

## Final Decision

BL-TZ01은 `trading_safety_panel`의 timezone aware/naive mismatch를 국소 범위에서 해소하였고, fail-closed 성질을 유지한 채 운영 관측 품질을 개선하였다.
