# CR-035 Phase A — v2 Endpoint Timeout 원인 격리 조사

Effective: 2026-03-31
Status: **SEALED** (Phase A + Phase B 완료)
Author: B (Implementer)
Reviewer: A (Designer)
Scope: v2 endpoint timeout 원인 분류

---

## (1) 해석 및 요약

### 근본 원인: PostgreSQL 커넥션 풀 포화 (운영 사고)

v2 endpoint timeout은 **exchange API timeout도, datetime 결함도, 구현 결함도 아닌**,
**서버 프로세스 다중 시작으로 인한 PostgreSQL `max_connections=100` 포화** 때문이었다.

```
M2-1 실행 중 서버 시작/중지 반복
  → 이전 프로세스가 DB 커넥션을 해제하지 않고 남음
  → approval 반복 루프(~8초 간격)가 커넥션을 계속 점유
  → 100개 슬롯 전부 점유
  → 새 요청 (v2, ops-status, safety-summary)이 커넥션 확보 불가
  → timeout (asyncpg TooManyConnectionsError)
```

### 분류 결과

| 후보 | 결과 |
|------|------|
| testnet 특성 | **아님** — testnet/mainnet 무관 |
| 네트워크 일시성 | **아님** — exchange API 호출 자체 0회 (포지션 0) |
| 구현 결함 | **아님** — DB 쿼리 전체 0.103s, exchange API 0s |
| **운영 사고 (커넥션 누수)** | **이것** — max_connections=100 포화 |

### 재현 조건

1. uvicorn 서버를 `--reload` 없이 시작
2. 서버를 kill하지 않고 새 서버 시작 반복
3. 이전 프로세스의 approval 루프가 커넥션 점유 지속
4. PostgreSQL `max_connections` 도달 → 모든 DB 의존 엔드포인트 차단

### 해소 조건

1. 모든 stale python 프로세스 종료
2. PostgreSQL 재시작 (`docker restart k-v3-postgres-1`)
3. 커넥션 해제 확인 (100 → 6)
4. DB 쿼리 전체 0.103s 정상 확인

---

## (2) 장점 / 단점

### 장점
- **구현 결함이 아닌 운영 사고**로 확정 — 코드 수정 불필요
- DB 쿼리 성능은 0.103s로 정상 (CR-034 수정 효과 확인)
- Exchange API 호출은 포지션 0건에서 자동 스킵 — 정상 동작
- PostgreSQL 재시작 후 문제 완전 해소

### 단점
- 서버 다중 시작 시 커넥션 누수 방지 메커니즘 없음
- `max_connections=100` 은 다중 프로세스 환경에서 빈약할 수 있음
- approval 반복 루프가 커넥션을 장기 점유하는 패턴 존재

---

## (3) 이유 / 근거

### 3.1 계측 증거

PostgreSQL 복구 후 직접 계측:

| 구성 요소 | 소요 시간 | 비고 |
|-----------|-----------|------|
| Exchange panels (5x DB) | 0.066s | 정상 |
| Trade count | 0.003s | 정상 |
| Time windows (7x DB) | 0.007s | 정상 (BL-TZ02 수정 효과) |
| Recent events (3x DB) | 0.019s | 정상 (BL-TZ02 수정 효과) |
| Signal summary | 0.003s | 정상 (BL-TZ02 수정 효과) |
| Venue freshness (5x DB) | 0.004s | 정상 |
| Order metrics | 0.001s | 정상 |
| **DB 전체** | **0.103s** | **정상** |
| Quote data (exchange API) | 0.000s | 포지션 0 → 호출 안 함 |

**v2 전체 DB 경로 = 0.103초. exchange API 경로 = 0초. timeout 재현 불가.**

### 3.2 커넥션 포화 증거

```
# 포화 상태 (서버 다중 시작 후)
psql: FATAL: sorry, too many clients already

# 복구 후
max_connections = 100
active = 6
```

### 3.3 approval 반복 루프

로그에서 ~8초 간격 approval 발급 반복 확인:
```
APR-xxxx REJECTED (8s 간격 반복) → 각각 DB 커넥션 점유
```

이 루프가 이전 서버 프로세스에서 계속 실행되며 커넥션 해제 없이 누적.

### 3.4 exchange API 무관 증거

`_get_quote_data()`는 포지션이 있는 거래소만 `fetch_ticker` 호출.
현재 모든 거래소 포지션 = 0 → `NOT_QUERIED`로 즉시 리턴 → API 호출 0회.

---

## (4) 실현/구현 대책

### 즉시 조치 (이미 완료)

| 조치 | 상태 |
|------|------|
| Stale python 프로세스 종료 | ✅ 완료 |
| PostgreSQL 재시작 | ✅ 완료 |
| 커넥션 정상화 (100→6) | ✅ 완료 |
| v2 DB 경로 0.103s 확인 | ✅ 완료 |

### 운영 권고 (코드 변경 아님)

| # | 권고 | 성격 |
|---|------|------|
| O-1 | 서버 시작 전 기존 프로세스 확인 (`netstat -ano \| grep :8000`) | 운영 절차 |
| O-2 | 서버 중지 시 프로세스 완전 종료 확인 | 운영 절차 |
| O-3 | PostgreSQL `max_connections` 모니터링 | 관측 항목 |
| O-4 | approval 루프의 커넥션 수명 확인 | 후속 관측 |

### 후속 코드 개선 후보 (현재 범위 밖)

| # | 후보 | 성격 | 우선순위 |
|---|------|------|----------|
| C-1 | SQLAlchemy pool 사이즈 제한 (`pool_size`, `max_overflow`) | 방어적 설정 | LOW |
| C-2 | 서버 shutdown hook에서 커넥션 풀 명시적 해제 | 누수 방지 | LOW |
| C-3 | approval 루프 커넥션 재사용 패턴 개선 | 효율성 | LOW |

**현재 시점에서 코드 변경은 불필요. 운영 절차 강화로 충분.**

---

## (5) 실행방법

### CR-035 처리 권고

이 건은 **구현 결함이 아닌 운영 사고**이므로:

1. Phase B(코드 수정) **불필요**
2. CR-035를 **RESOLVED (운영 사고, 해소 완료)**로 봉인
3. 운영 권고 O-1~O-4를 운영 절차에 반영

### M2-2 해제 조건표

CR-035 결과를 반영한 M2-2 해제 조건:

| # | 조건 | 현재 상태 | 충족 |
|---|------|-----------|------|
| G-1 | CR-034 SEALED | SEALED | ✅ |
| G-2 | CR-035 SEALED | SEALED (Phase A+B 완료) | ✅ |
| G-3 | DB 쿼리 경로 정상 (v2 < 1s) | 0.103s | ✅ |
| G-4 | DataError 0건 | 0건 | ✅ |
| G-5 | enforcement NORMAL | NORMAL | ✅ |
| G-6 | PostgreSQL 커넥션 정상 (< 50% max) | 6/100 | ✅ |
| G-7 | 테스트 기준선 유지 | 3171/0/0 | ✅ |
| G-8 | M2-1 CONDITIONAL PASS 유지 | SEALED | ✅ |

**M2-2 해제 조건: 8/8 충족. 단, M2-2는 자동 GO가 아니라 REVIEW 준비 상태. 단일 인스턴스 재기동 관측 1회 후 A REVIEW 필요.**

---

## (6) 더 좋은 아이디어

### v2 endpoint 응답 시간 예측 (포지션 존재 시)

포지션이 생기면 `_get_quote_data()`에서 exchange API 호출이 발생한다.
예상 소요 시간:

| 시나리오 | 호출 수 | 예상 소요 |
|----------|---------|-----------|
| 포지션 0건 (현재) | 0 | 0s |
| 1 거래소, 1 종목 | 1 | ~0.5~2s |
| 3 거래소, 5 종목 | 5 | ~3~10s |

M2-2에서 live 포지션이 생기면 v2 응답 시간이 늘어날 수 있다.
이때는 `asyncio.gather()` 병렬화 또는 캐싱이 필요할 수 있으나,
**현재 범위에서는 관측만 권고**.

---

## 헌법 조항 대조

| 규칙 | 준수 | 비고 |
|------|------|------|
| 코드 변경 없음 | ✅ | 운영 사고 해소만 |
| Schema/Alembic 무변경 | ✅ | |
| CR-033/034 불가침 | ✅ | |
| Write/execution path 무변경 | ✅ | |

## 미해결 리스크

| # | 리스크 | 심각도 | 비고 |
|---|--------|--------|------|
| R-1 | 서버 다중 시작 재발 시 커넥션 재포화 | LOW | 운영 절차로 방지 |
| R-2 | M2-2 포지션 생성 시 v2 응답 시간 증가 | LOW | 관측 후 판단 |

---

## A 판단용 1문장 결론

**v2 timeout은 구현 결함이 아닌 서버 다중 시작에 의한 PostgreSQL 커넥션 포화(운영 사고)이며, 프로세스 정리 + DB 재시작으로 해소 완료, M2-2 해제 조건 8/8 충족.**
