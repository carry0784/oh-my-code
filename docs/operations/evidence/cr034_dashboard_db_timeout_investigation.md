# CR-034 Phase A — Dashboard DB Timeout 원인 격리 조사

Effective: 2026-03-31
Status: **SEALED** (Phase A+B 완료, 2026-03-31)
Author: B (Implementer)
Reviewer: A (Designer)
Scope: Dashboard PostgreSQL datetime timeout 원인 격리

---

## (1) 해석 및 요약

### 근본 원인: timezone-aware datetime을 TIMESTAMP WITHOUT TIME ZONE 컬럼에 전달

**오류 메시지 (로그 실증):**
```
asyncpg.exceptions.DataError: invalid input for query argument $1:
datetime.datetime(2026, 3, 30, 8, 33, 46, 623648, tzinfo=datetime.timezone.utc)
(can't subtract offset-naive and offset-aware datetimes)

[SQL: SELECT signals.status, count(signals.id) AS count_1
 FROM signals
 WHERE signals.created_at >= $1::TIMESTAMP WITHOUT TIME ZONE
 GROUP BY signals.status]
```

**핵심:** `asyncpg`는 PostgreSQL의 `TIMESTAMP WITHOUT TIME ZONE` 컬럼에 timezone-aware datetime(`tzinfo=utc`)을 바인딩하면 **DataError를 발생**시킨다. SQLAlchemy가 이를 잡지 못하고 전파.

---

## (2) 장점 / 단점

### 장점 (원인 격리 완료)
- 오류 원인이 단일 패턴으로 수렴: `datetime.now(timezone.utc)` vs `DateTime` (naive) 불일치
- 수정점이 명확하고 최소침습 가능
- DB 스키마/Alembic 변경 없이 해결 가능

### 단점 (현재 상태)
- 이 오류가 `_get_signal_summary()`에서 발생하면 v2 endpoint 전체가 지연/실패
- ops-status 내 `_compute_integrity_panel()`과 `_compute_trading_safety_panel()`도 동일 패턴 보유
- 연쇄적으로 System Healthy, Trading Auth, Safety 판정이 모두 오염됨

---

## (3) 이유 / 근거

### 3.1 최초 예외 지점

| # | 함수 | 파일:라인 | 쿼리 | 오류 |
|---|------|-----------|------|------|
| **E-1** | `_get_signal_summary()` | dashboard.py:945-948 | `Signal.created_at >= cutoff` | **실증됨 (로그)** |
| E-2 | `_get_recent_events()` | dashboard.py:850-854 | `Signal.created_at >= cutoff_24h` | 동일 패턴 (try/except pass로 숨김) |
| E-3 | `_compute_integrity_panel()` | dashboard.py:3013-3031 | `Position.updated_at` 차이 계산 | `.replace(tzinfo=utc)` 방어 있음 (**안전**) |
| E-4 | `_compute_trading_safety_panel()` | dashboard.py:3081 | `Order.created_at >= recent_cutoff` | `datetime.utcnow()` 사용 (**naive — 정상**) |
| E-5 | `_get_venue_freshness()` | dashboard.py:988-994 | `Position.updated_at` 차이 계산 | naive - aware 충돌 가능 |

### 3.2 근본 원인 메커니즘

```
ORM 모델 정의 (signal.py:40):
  created_at = mapped_column(DateTime)    ← TIMESTAMP WITHOUT TIME ZONE

DB 컬럼 타입:
  signals.created_at  →  TIMESTAMP WITHOUT TIME ZONE (naive)

쿼리 파라미터 생성 (dashboard.py:934-935):
  now = datetime.now(timezone.utc)        ← timezone-AWARE
  cutoff = now - timedelta(hours=24)      ← timezone-AWARE

asyncpg 바인딩:
  $1 = datetime(2026, 3, 30, ..., tzinfo=utc)  ← AWARE
  target column = TIMESTAMP WITHOUT TIME ZONE    ← NAIVE

결과: asyncpg DataError (aware datetime을 naive 컬럼에 바인딩 불가)
```

### 3.3 왜 일부 쿼리는 성공하는가

| 파일:라인 | 파라미터 생성 | 결과 |
|-----------|-------------|------|
| dashboard.py:934 `_get_signal_summary` | `datetime.now(timezone.utc)` — **aware** | **FAIL** |
| dashboard.py:829 `_get_recent_events` | `datetime.now(timezone.utc)` — **aware** | **FAIL** (숨김) |
| dashboard.py:3081 `_compute_trading_safety_panel` | `datetime.utcnow()` — **naive** | **PASS** |
| dashboard.py:3031 `_compute_integrity_panel` | `.replace(tzinfo=utc)` 후 python 연산만 | **PASS** |

**BL-TZ01 주석 (라인 3080)** 이 이미 이 문제를 인지하고 있었음:
```python
# BL-TZ01: Order.created_at is DateTime (naive, TIMESTAMP WITHOUT TIME ZONE).
recent_cutoff = datetime.utcnow() - timedelta(hours=24)
```

### 3.4 영향 범위 분석

#### 직접 실패하는 엔드포인트

| 엔드포인트 | 원인 함수 | 영향 |
|-----------|-----------|------|
| `/api/data/v2` | `_get_signal_summary()` (L945) | **전체 v2 응답 지연/실패** |
| `/api/data/v2` | `_get_recent_events()` (L850) | signal 부분 누락 (try/except pass) |

#### 간접 영향 (v2 실패로 인한 연쇄)

| Dashboard 표시 | 원인 경로 | 상태 |
|----------------|-----------|------|
| System Healthy: X | v2 응답 실패 → 프론트엔드 데이터 없음 | 오염 |
| Trading Auth: X | system_healthy=false 종속 | 오염 |
| freshness unknown | venue_freshness 쿼리는 성공하지만 v2 전체 실패 시 도달 불가 | 오염 |
| Safety 7/7 | ops-safety-summary 별도 엔드포인트지만 DB 세션 공유 시 지연 가능 | 간접 영향 |

#### ops-status 엔드포인트

| 함수 | 패턴 | 상태 |
|------|------|------|
| `_compute_global_status_bar()` | DB 쿼리 없음, app.state 참조 | **안전** |
| `_compute_integrity_panel()` | `Position.updated_at` + `.replace(tzinfo=utc)` | **안전** (방어 있음) |
| `_compute_trading_safety_panel()` | `datetime.utcnow()` (naive) | **안전** (BL-TZ01) |
| `_compute_incident_panel()` | DB 쿼리 없음, receipt_store 참조 | **안전** |

**결론: ops-status 자체는 안전할 수 있으나, asyncpg 세션 레벨 오류가 전파되면 같은 DB 커넥션을 공유하는 다른 쿼리도 영향받을 수 있음.**

### 3.5 왜 ops-status가 timeout되었나

M2-1 실행 중 관찰된 행동:
1. 서버 시작 직후 `ops-activation`은 성공 (DB 미사용)
2. `ops-status`는 timeout (DB 의존)
3. `ops-safety-summary`도 timeout

**가설:** asyncpg 커넥션 풀에서 `_get_signal_summary()`의 DataError가 세션을 오염시키거나, 반복 approval 루프(로그에서 8초마다 반복)가 커넥션을 점유하여 다른 쿼리가 대기열에 갇힘.

### 3.6 전체 불일치 파일 지도

`datetime.now(timezone.utc)` (aware)를 DB 쿼리 파라미터로 사용하는 위치:

| 파일:라인 | 함수 | 대상 컬럼 | 위험 |
|-----------|------|-----------|------|
| **dashboard.py:934** | `_get_signal_summary` | `Signal.created_at` (naive) | **HIGH — 실증** |
| **dashboard.py:849** | `_get_recent_events` | `Signal.created_at` (naive) | **HIGH — 동일 패턴** |
| dashboard.py:984 | `_get_venue_freshness` | `Position.updated_at` (naive) | **MEDIUM** — python 연산만 시 안전, DB 비교 시 위험 |
| dashboard.py:642 | `_get_time_window_stats` | 불확실 | 확인 필요 |

---

## (4) 실현/구현 대책

### 최소 수정안 후보

#### 수정안 A: 쿼리 파라미터를 naive로 통일 (권장)

```python
# BEFORE (dashboard.py:934-935)
now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=24)

# AFTER
cutoff = datetime.utcnow() - timedelta(hours=24)
```

**영향받는 위치: 2개 함수 (E-1, E-2)**

| 항목 | 평가 |
|------|------|
| 변경 파일 | 1개 (dashboard.py) |
| 변경 라인 | 최소 2~4줄 |
| 스키마 변경 | 없음 |
| Alembic 변경 | 없음 |
| 기존 BL-TZ01 패턴 준수 | 예 — 이미 3081에서 사용 중 |
| 위험도 | LOW — 기존 코드베이스 패턴과 동일 |

#### 수정안 B: DB 컬럼을 timezone-aware로 변경

```python
# signal.py
created_at = mapped_column(DateTime(timezone=True), ...)
```

| 항목 | 평가 |
|------|------|
| 변경 파일 | 4+ 모델 파일 + Alembic 마이그레이션 |
| 위험도 | HIGH — 기존 데이터 마이그레이션 필요, 광범위 영향 |
| A 지시 준수 | **불가** — schema 변경 금지, alembic 변경 금지 |

**수정안 A를 강력히 권장. 수정안 B는 A의 금지 사항에 위배.**

---

## (5) 실행방법

### Phase B 수정 대상 (A 승인 시)

```
파일: app/api/routes/dashboard.py

수정 1 — _get_signal_summary() (L934-935)
  BEFORE: now = datetime.now(timezone.utc)
          cutoff = now - timedelta(hours=24)
  AFTER:  cutoff = datetime.utcnow() - timedelta(hours=24)

수정 2 — _get_recent_events() (L829, 849)
  BEFORE: now = datetime.now(timezone.utc)
          cutoff_24h = now - timedelta(hours=24)
  AFTER:  cutoff_24h = datetime.utcnow() - timedelta(hours=24)

수정 3 — _get_venue_freshness() (L984, 994)
  점검 필요: now - last_updated 연산이 Python 레벨인지 DB 레벨인지 확인
  (현재 Python 레벨 — .total_seconds() — naive 반환값과 aware now 충돌 가능)
  BEFORE: now = datetime.now(timezone.utc)
          age = (now - last_updated).total_seconds()
  AFTER:  now = datetime.utcnow()
          age = (now - last_updated).total_seconds()

수정 4 (선택) — 기타 동일 패턴 일괄 점검
  dashboard.py 내 datetime.now(timezone.utc)가 DB 쿼리 파라미터로 사용되는 모든 위치
```

### 검증 계획

1. 서버 시작 후 `/dashboard/api/data/v2` 응답 확인
2. `/dashboard/api/ops-status` 응답 확인
3. `/dashboard/api/ops-safety-summary` 응답 확인
4. Safety 7/7, System Healthy, Trading Auth 상태 확인
5. 기존 테스트 전체 통과 확인 (`pytest tests/ -x -q`)

---

## (6) 더 좋은 아이디어

### 장기 권고: timezone 정책 통일

현재 코드베이스에 2가지 패턴이 혼재:
- `datetime.now(timezone.utc)` — aware (Python 권장)
- `datetime.utcnow()` — naive (asyncpg/PostgreSQL TIMESTAMP 호환)

장기적으로는 **DB 컬럼을 `TIMESTAMP WITH TIME ZONE`으로 통일**하는 것이 바람직하나,
이는 대규모 마이그레이션이므로 현재 CR-034 범위를 초과한다.

현재 최선: **DB 쿼리 파라미터에는 naive, Python 연산에는 aware** 원칙을 BL-TZ01로 문서화하고 수정.

---

## 헌법 조항 대조 검수본

| 규칙 | 준수 | 비고 |
|------|------|------|
| Append-only evidence | ✅ | evidence 관련 변경 없음 |
| Read-only 원칙 | ✅ | dashboard 표시 로직만 수정 |
| Fail-closed | ✅ | 기존 fail-soft 패턴 유지 |
| Schema 변경 금지 | ✅ | 수정안 A는 쿼리 파라미터만 변경 |
| Alembic 변경 금지 | ✅ | 마이그레이션 없음 |
| Write path 불가침 | ✅ | 실행 경로 무관 |
| M2-1 결과 불가침 | ✅ | CR-033 봉인 유지 |

## 요구 조항

| 조항 | 상태 |
|------|------|
| 재현 조건 문서화 | ✅ 완료 — `datetime.now(timezone.utc)`를 naive 컬럼 쿼리에 사용 |
| 최초 예외 지점 특정 | ✅ 완료 — dashboard.py:945 `_get_signal_summary()` |
| 원인 후보 우선순위화 | ✅ 완료 — 단일 원인 수렴 (aware/naive 불일치) |
| 최소 수정점 1~2개 | ✅ 완료 — 수정안 A (3~4줄), 수정안 B (금지) |
| Phase B 착수 가능/불가 판정 | ✅ **착수 가능** |

## 반영/미반영

| 항목 | 반영 | 비고 |
|------|------|------|
| timeout 정확한 API 경로 | ✅ | `/api/data/v2` → `_get_signal_summary()` |
| 최초 예외 메시지 | ✅ | asyncpg DataError (로그 실증) |
| aware/naive mismatch | ✅ | 근본 원인 |
| DB column type mismatch | ✅ | `DateTime` = TIMESTAMP WITHOUT TIME ZONE |
| ORM ↔ serializer 변환 | ✅ | ORM 레벨 아닌 asyncpg 바인딩 레벨 |
| query timeout 자체 여부 | ✅ | timeout이 아닌 DataError → 연쇄 실패 |
| fallback 오염 경로 | ✅ | v2 전체 실패 → 프론트엔드 데이터 없음 |

## 금지 조항 확인

| 금지 사항 | 준수 |
|-----------|------|
| Schema 변경 | ✅ 금지 준수 |
| Alembic 변경 | ✅ 금지 준수 |
| 광범위 refactor | ✅ 금지 준수 |
| Live execution 변경 | ✅ 금지 준수 |
| M2-2 착수 | ✅ 금지 준수 |
| 추정만으로 fix 제출 | ✅ 금지 준수 — 로그 실증 기반 |

## 상태 전이 영향

| 상태 | 수정 전 | 수정 후 (예상) |
|------|---------|-------------|
| System Healthy | X (UNVERIFIED/DEGRADED) | 정상화 가능 (enforcement=NORMAL 시) |
| Trading Auth | X (system_healthy 종속) | system_healthy 정상화 시 해소 |
| Safety 7/7 | API timeout | 응답 가능 |
| freshness | unknown | fresh/stale 정상 표시 |

## 로그/Audit 영향

- `signal_summary_query_failed` 경고 제거됨
- evidence store 영향 없음
- receipt store 영향 없음

## 미해결 리스크

| # | 리스크 | 심각도 | 비고 |
|---|--------|--------|------|
| R-1 | `_get_venue_freshness()`의 Python-level aware-naive 연산 | LOW | DB 반환값이 naive, now가 aware — `total_seconds()` 오류 가능 |
| R-2 | `_get_time_window_stats()` 동일 패턴 가능성 | LOW | 확인 필요 |
| R-3 | `_get_quote_data()` L1054 동일 패턴 | LOW | exchange API 결과와의 연산 — DB 무관 |
| R-4 | 장기: aware/naive 혼재 지속 | LOW | BL-TZ01 문서화로 관리 |

## 다음 단계 권고

1. **A가 Phase B 착수를 승인** — 수정안 A (naive 통일) 적용
2. **수정 후 서버 재시작 → 6개 검증 항목 실행**
3. **Dashboard health 정상화 확인 후 CR-034 봉인**
4. **M2-2 HOLD 해제 여부 재판정**

---

## A 판단용 1문장 결론

**Dashboard timeout의 근본 원인은 `datetime.now(timezone.utc)` (aware)를 `TIMESTAMP WITHOUT TIME ZONE` (naive) 컬럼 쿼리에 전달하는 것이며, BL-TZ02 패턴(`datetime.now(timezone.utc).replace(tzinfo=None)`)으로 DB 경계 계약을 복원하여 해결 완료.**

---

## Phase B 실행 결과 (2026-03-31)

### 수정 내역

| # | 함수 | 라인 | 수정 | BL-TZ02 태그 |
|---|------|------|------|-------------|
| E-1 | `_get_signal_summary()` | 934-936 | `now`/`cutoff` → `cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)` | Yes |
| E-2 | `_get_recent_events()` | 829-849 | `now` → `now_naive = datetime.now(timezone.utc).replace(tzinfo=None)` | Yes |
| E-3 | `_get_venue_freshness()` | 984 | `now` → `now_naive = datetime.now(timezone.utc).replace(tzinfo=None)` | Yes |
| E-4 | `_get_time_window_stats()` | 642 | `now` → `now_naive = datetime.now(timezone.utc).replace(tzinfo=None)` | Yes |

**수정 파일: 1개 (`dashboard.py`), 변경 라인: 8줄**
**방식: `datetime.utcnow()` 재도입 아님 — aware UTC 생성 후 DB 경계에서 `.replace(tzinfo=None)` 정규화**

### 검증 결과

| # | 항목 | 결과 |
|---|------|------|
| 1 | DB 쿼리 직접 테스트 (naive cutoff) | **PASS** |
| 2 | DB 쿼리 직접 테스트 (aware cutoff → DataError 재현) | **PASS** (정상 실패 확인) |
| 3 | `/dashboard/api/ops-status` HTTP 200 | **PASS** |
| 4 | `enforcement_state`: UNKNOWN → **NORMAL** | **PASS** — 오염 제거 |
| 5 | `status_word`: DEGRADED (stale data) | **PASS** — cold-start 정상 |
| 6 | `block_reason`: DB query failed → **None** | **PASS** — 오염 제거 |
| 7 | `/dashboard/api/ops-activation` 정상 응답 | **PASS** |
| 8 | `/dashboard/api/ops-safety-summary` 정상 응답 | **PASS** |
| 9 | 수정 후 로그에 DataError 0건 | **PASS** |
| 10 | 기존 테스트 전체 통과 | **PASS** — 3171/0/0 |

### 상태 전이

| 항목 | 수정 전 | 수정 후 |
|------|---------|---------|
| enforcement_state | UNKNOWN | **NORMAL** |
| status_word | UNVERIFIED/timeout | **DEGRADED** (stale data — cold-start) |
| system_healthy | X (timeout) | **False** (stale data 때문 — 정상 판정) |
| trading_authorized | X (종속) | **False** (system_healthy 종속 — 정상) |
| block_reason | "Order metrics unavailable (DB query failed)" | **None** |
| kill_switch | timeout | **False** |
| DataError 발생 | 반복 (매 요청) | **0건** |

### A 최종 봉인 판정 (2026-03-31)

**결론: SEALED**

봉인 범위:
- timezone-aware → TIMESTAMP WITHOUT TIME ZONE 경계 불일치 해소
- asyncpg DataError 제거
- enforcement UNKNOWN 오염 제거
- block_reason 오염 제거
- dashboard 핵심 판정 경로 복원

분리 추적 (CR-034 범위 밖):
- `system_healthy=False` — stale cold-start 기대 동작, 장애 아님
- v2 exchange API timeout — datetime 무관, 별도 CR-035로 분리 등록
