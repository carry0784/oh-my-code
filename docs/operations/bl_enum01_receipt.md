# BL-ENUM01 Receipt — OrderStatus PostgreSQL enum mismatch fix

## Status

RESOLVED

## Scope

`OrderStatus` Python/ORM/DB enum 불일치 국소 해소

## Problem

live smoke에서 `trading_safety_panel` 계산 시 `invalid input value for enum orderstatus: "REJECTED"` 오류 발생.

## Root Cause

SQLAlchemy `SQLEnum(OrderStatus)`가 기본적으로 Python enum의 `.name` (대문자 `REJECTED`)을 DB에 전달함.
PostgreSQL DB enum `orderstatus`에는 소문자 값(`rejected`)만 등록되어 있어 불일치 발생.

| Python `.name` | Python `.value` | DB enum |
|----------------|-----------------|---------|
| PENDING | pending | pending |
| SUBMITTED | submitted | submitted |
| FILLED | filled | filled |
| PARTIALLY_FILLED | partially_filled | partially_filled |
| CANCELLED | cancelled | cancelled |
| REJECTED | rejected | rejected |

값 자체는 동일하나, SQLAlchemy가 `.name`(대문자)을 보내는 것이 원인.

## Standard of Truth

DB enum = 소문자 = Python `.value`가 표준. SQLAlchemy에 `.value` 사용을 명시해야 한다.

## Fix Summary

`app/models/order.py`에서 `SQLEnum` 3개 컬럼에 `values_callable=lambda e: [x.value for x in e]` 추가.
이로써 SQLAlchemy가 `.value`(소문자)를 DB에 전달.

수정 대상 컬럼:
- `side`: `SQLEnum(OrderSide, values_callable=...)`
- `order_type`: `SQLEnum(OrderType, values_callable=...)`
- `status`: `SQLEnum(OrderStatus, values_callable=...)`

migration 불필요: DB enum 값 자체는 변경 없음. ORM 계층의 전달 방식만 보정.

## Constitutional Check

| 항목 | 확인 |
|------|------|
| fail-closed 유지 | 확인 |
| 기능 확장 없음 | 확인 |
| 범위 외 enum 오염 없음 | 확인 — Order 모델 3컬럼만 |
| 의미 왜곡 없음 | 확인 — 동일 값, 전달 방식만 보정 |
| 임시 우회 없음 | 확인 — 원인 직접 수정 |
| 오류 은폐 없음 | 확인 |

## Tests

- enum 쿼리 재현: REJECTED query PASS, CANCELLED query PASS
- 회귀 테스트: 243 passed
- live smoke: `ops_trading_safety_failed` 경고 미발생, panel 정상 응답

## Remaining Risk

없음. DB migration 불필요. 기존 데이터 호환성 유지.

## Final Decision

BL-ENUM01은 OrderStatus의 Python/ORM/DB enum 불일치를 국소 범위에서 해소하였고, runtime enum 오류를 제거하면서 의미 보존과 운영 안정성을 유지하였다.
