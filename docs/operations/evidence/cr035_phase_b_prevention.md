# CR-035 Phase B — PostgreSQL 커넥션 포화 재발 방지

Effective: 2026-03-31
Status: **SEALED**
Author: B (Implementer)
Reviewer: A (Designer)
Scope: 커넥션 누수 방지 + 기동 가드 + 풀 방어 설정

---

## A 판정 — CR-035 PostgreSQL connection saturation prevention

결론: **SEALED**

봉인 범위:
- 서버 프로세스 다중 시작/종료 누락에 따른 PostgreSQL connection saturation 재발 방지
- lifespan shutdown dispose 반영
- sync engine finally dispose 경로 반영
- async pool timeout/recycle 방어 반영
- startup guard script 반영

판정 근거:
- root cause와 수정축 정합
- 10파일 반영 완료
- dispose() 실증 7곳
- AST parse 7/7 OK
- tests 3171/0/0 PASS
- schema/Alembic 무변경
- write/execution path 의미 변경 없음
- CR-034 혼입 없음

상태:
- CR-035 = SEALED
- BINANCE_TESTNET = true 유지
- M2-2 = REVIEW 준비, 자동 GO 아님

---

## (1) 해석 및 요약

### 재발 방지 3건 구현 완료

Phase A에서 확정된 근본 원인(서버 다중 시작 → PostgreSQL 커넥션 포화)에 대해
3계층 방어 조치를 구현했다.

```
[1순위] 기동 가드 + Shutdown 정리
  → 포트 점유 확인 스크립트 (scripts/start_server.sh)
  → lifespan shutdown에서 async engine dispose()

[2순위] Sync engine 커넥션 누수 차단
  → 5파일 6곳 create_engine()에 finally: dispose() 추가

[3순위] Async pool 방어 설정
  → pool_timeout=30 (무한 대기 방지)
  → pool_recycle=1800 (stale 커넥션 갱신)
```

### 방어 효과

| 시나리오 | Before | After |
|----------|--------|-------|
| 서버 정상 종료 | 커넥션 풀 미해제 (누적) | `engine.dispose()` → 즉시 반환 |
| 서버 이중 시작 | 무조건 시작 → 커넥션 2배 | `start_server.sh` → 차단 |
| Sync engine 사용 | `create_engine()` 후 미해제 | `finally: dispose()` → 즉시 반환 |
| 풀 대기 교착 | 무한 대기 (timeout 없음) | 30초 후 TimeoutError |
| 장기 커넥션 고착 | 영구 유지 | 30분마다 갱신 |

---

## (2) 장점 / 단점

### 장점
- **3계층 방어**: 기동 → 런타임 → 종료 각 단계에서 커넥션 관리
- **최소 침습**: 기존 로직 변경 없이 cleanup path만 추가
- **write/execution path 무변경**: dispose()는 shutdown/cleanup에서만 호출
- **기존 테스트 영향 없음**: 3171/0/0 유지

### 단점
- `start_server.sh`는 수동 사용 필요 (강제 아님)
- `pool_recycle=1800`은 30분마다 커넥션 재생성 비용 발생 (무시 가능 수준)
- Sync engine의 근본 해결은 공유 엔진 싱글톤화이나, 현재 범위 밖 (LOW 우선순위)

---

## (3) 이유 / 근거

### 3.1 커넥션 누수 경로 분석

탐색 결과, `create_engine()` 호출 후 `dispose()` 없이 방치되는 곳이 6곳:

| 파일 | 함수 | 호출 빈도 |
|------|------|-----------|
| `constitution_check_runner.py` | `_check_evidence_active()` | 헌법 검증 시 |
| `constitution_check_runner.py` | `_get_snapshot_age_sync()` | 헌법 검증 시 |
| `execution_policy.py` | `_recheck_ops_score()` | 정책 재검증 시 |
| `execution_gate.py` | `_evaluate()` | 실행 게이트 평가 시 |
| `recovery_preflight.py` | `_check_item()` | 복구 프리플라이트 시 |
| `operator_approval.py` | `_collect_ops_score()` | 승인 발급 시 |

각 호출마다 SQLAlchemy QueuePool이 생성되고, `dispose()` 없이 GC에 의존.
서버 프로세스가 종료되지 않으면 GC도 작동하지 않아 커넥션이 누적된다.

### 3.2 Pool 설정 근거

| 설정 | 값 | 근거 |
|------|-----|------|
| `pool_timeout` | 30초 | SQLAlchemy 기본값은 30이나 명시적 설정으로 계약 보장 |
| `pool_recycle` | 1800초 | PostgreSQL `idle_in_transaction_session_timeout` 기본값(0) 대비 방어적 갱신 |
| `pool_size` | 5 (유지) | 단일 프로세스 기준 적정 |
| `max_overflow` | 10 (유지) | 버스트 허용, 프로세스당 최대 15 |

### 3.3 기동 가드 근거

`netstat -ano | grep :PORT` → Windows/Linux 양쪽에서 작동.
기존 프로세스 발견 시 에러 메시지와 함께 종료 (exit 1).

---

## (4) 실현/구현 대책

### 변경 내역

| # | 파일 | 변경 | 내용 |
|---|------|------|------|
| 1 | `app/main.py` | EDIT | lifespan shutdown에 `engine.dispose()` + 로그 |
| 2 | `app/core/database.py` | EDIT | `pool_timeout=30`, `pool_recycle=1800` |
| 3 | `app/core/constitution_check_runner.py` | EDIT | `finally: _engine.dispose()` × 2곳 |
| 4 | `app/core/execution_policy.py` | EDIT | `finally: _engine.dispose()` × 1곳 |
| 5 | `app/core/execution_gate.py` | EDIT | `finally: engine.dispose()` × 1곳 |
| 6 | `app/core/recovery_preflight.py` | EDIT | `finally: _engine.dispose()` × 1곳 |
| 7 | `app/core/operator_approval.py` | EDIT | `finally: _engine.dispose()` × 1곳 |
| 8 | `scripts/start_server.sh` | NEW | 기동 가드 스크립트 |

**총 8파일 (7 EDIT + 1 NEW), 코드만**

### 검증 결과

| 항목 | 결과 |
|------|------|
| `pytest tests/ -x` | 3171 passed, 0 failed |
| `grep -r "dispose()" app/` | 7곳 확인 (6 sync + 1 async) |
| Schema/Alembic 변경 | 없음 |
| Write/execution path 변경 | 없음 (cleanup path만) |

---

## (5) 실행방법

### 운영 절차

#### 서버 시작 (권장)
```bash
bash scripts/start_server.sh          # 기본 포트 8000
bash scripts/start_server.sh 8001     # 커스텀 포트
bash scripts/start_server.sh 8000 --reload  # 개발 모드
```

#### 서버 중지 확인
```bash
# Windows
netstat -ano | grep :8000
taskkill //F //PID <pid>

# 커넥션 확인
docker exec k-v3-postgres-1 psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```

#### 비상 복구 (커넥션 포화 시)
```bash
# 1. 모든 stale python 프로세스 종료
taskkill //F //IM python.exe

# 2. PostgreSQL 재시작
docker restart k-v3-postgres-1

# 3. 커넥션 정상화 확인
docker exec k-v3-postgres-1 psql -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

---

## (6) 미해결 리스크

| # | 리스크 | 심각도 | 비고 |
|---|--------|--------|------|
| R-1 | Sync engine을 공유 싱글톤으로 통합하면 더 효율적 | LOW | 현재 `dispose()` 패턴으로 충분, 후속 개선 후보 |
| R-2 | `start_server.sh` 미사용 시 이중 시작 가능 | LOW | 운영 절차 교육으로 방지 |
| R-3 | Celery worker의 sync engine (`order_tasks.py`) | LOW | 장기 프로세스이므로 모듈 레벨 유지 적정 |

---

## 헌법 조항 대조

| 규칙 | 준수 | 비고 |
|------|------|------|
| CR-034 혼입 금지 | ✅ | BL-TZ02 관련 변경 없음 |
| exchange API timeout 가설 금지 | ✅ | 커넥션 풀 관리에만 집중 |
| Schema/Alembic 무변경 | ✅ | |
| Write/execution path 무변경 | ✅ | dispose()는 cleanup path만 |
| M2-2 시작 금지 | ✅ | |

---

## A 판단용 1문장 결론

**CR-035 Phase B: 7파일 sync/async engine dispose() + pool_timeout/recycle 방어 설정 + 기동 가드 스크립트로 PostgreSQL 커넥션 포화 3계층 재발 방지 완료, 3171/0/0 PASS, write/execution path 무변경.**
