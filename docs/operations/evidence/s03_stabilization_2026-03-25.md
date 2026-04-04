# S-03 Stabilization Check 검수본

## 1. 실행 개요

| 필드 | 값 |
|------|-----|
| check_type | S03_STABILIZATION |
| run_date | 2026-03-25 |
| run_timestamp | 2026-03-25T20:00:00+09:00 |
| system_phase | prod (frozen, live) |
| executor_activated | false |
| auto_repair_performed | **false** |
| evidence_id | S03-2026-03-25-01 |

## 2. 현재 기준선 상태

| 항목 | 값 |
|------|-----|
| 코드 기준선 | 7eb9ad8 (governance-go-baseline) |
| 재기동 시각 | 2026-03-25 19:52:14 KST |
| 선행 조치 | Controlled Restart 완료 (RESTART-EXEC-2026-03-25-01) |
| orphaned worker 해소 | 확인 (PID 52624 종료, 신규 master+worker 정상) |
| Z-02 핵심 | 4/4 PASS |
| 잔여 이슈 | positions.symbol_name 마이그레이션 미적용, /ready probe 속성명 불일치 |

## 3. 런타임 상태 점검

| 항목 | expected | observed | result |
|------|----------|----------|--------|
| 서버 기동 | listening on :8000 | TCP 127.0.0.1:8000 LISTENING PID 81064 | **PASS** |
| Master 프로세스 | uvicorn master alive | PID 81064, `uvicorn app.main:app --reload --port 8000`, created 19:52:14 | **PASS** |
| Worker 프로세스 | worker alive, child of master | PID 86524, parent=81064, multiprocessing.spawn, created 19:52:14 | **PASS** |
| Crash loop | 없음 | PID 변경 없음 (재기동 후 동일 PID 유지), crash trace 없음 | **PASS** |
| Orphan process | 없음 | Python 프로세스 2개만 존재 (master+worker), 고아 없음 | **PASS** |
| Reload 반복 | 없음 | 로그에 reload 이벤트 없음, 단일 startup 시퀀스만 기록 | **PASS** |

**runtime_state: PASS** (6/6)

## 4. API 점검

### Core API

| 엔드포인트 | expected | observed | result |
|-----------|----------|----------|--------|
| /health | 200 | 200, `{"status":"healthy"}` | **PASS** |
| /status | 200, no CRITICAL | 200, overall_status=unavailable, liveness=ok, startup=complete; degraded_reasons: 4 sources unavailable (loop_monitor, work_state, trust_state, doctrine); **CRITICAL 없음** | **PASS** |
| /startup | 200 | 200, started=true, governance_initialized=true, state_slots_initialized=true | **PASS** |
| /dashboard | 200 | 200, HTML 정상 | **PASS** |

/status 보충: overall_status=unavailable은 거래 루프 미가동 시 예상 동작. 4개 runtime source(loop_monitor 등)는 거래 루프 연결 시 활성화됨. CRITICAL 수준 이슈 없음.

### Ops API

| 엔드포인트 | expected | observed | result |
|-----------|----------|----------|--------|
| /dashboard/api/ops-status | 200 | 200, JSON: app_env=production, phase=prod, prod_lock=true, trading_permission=false, status_word=UNVERIFIED | **PASS** |

ops-status 보충: status_word=UNVERIFIED, enforcement_state=UNKNOWN은 Enforcement 엔진 미연결 시 예상 동작. dual_lock: system_healthy=false, trading_authorized=false → E-01 비활성 상태와 일치.

### Data API

| 엔드포인트 | expected | observed | result |
|-----------|----------|----------|--------|
| /dashboard/api/data/v2 | 500 (FAIL 허용) | 500, `positions.symbol_name does not exist` | **WARN** (기지 이슈, 마이그레이션 미적용) |

**api_state: PASS** (Core 4/4 PASS, Ops 1/1 PASS, Data 1/1 WARN — 기지 이슈)

## 5. DB 상태 점검

| 항목 | expected | observed | result |
|------|----------|----------|--------|
| PostgreSQL 가동 | accepting connections | `/var/run/postgresql:5432 - accepting connections` | **PASS** |
| DB 연결 | 쿼리 실행 가능 | orders=0, signals=0, trades=0 (정상 조회) | **PASS** |
| Schema mismatch | 기록 | positions.symbol_name 컬럼 미존재 (ORM 정의↔DB 불일치) | **WARN** (기지 이슈) |
| Docker 컨테이너 | postgres, redis, flower UP | k-v3-postgres-1 Up 32h, k-v3-redis-1 Up 32h, k-v3-flower-1 Up 32h | **PASS** |

**db_state: WARN** (연결 정상, schema mismatch 존재 — 기지 이슈)

## 6. 로그 상태 점검

| 항목 | expected | observed | result |
|------|----------|----------|--------|
| Startup 로그 | 정상 시퀀스 | evidence_store=SQLITE_PERSISTED, governance_gate_initialized=true, receipt_store=FILE_PERSISTED | **PASS** |
| Error 로그 | 기지 이슈만 | `dashboard_exchange_query_failed` (positions.symbol_name) — 기지 이슈만 발생 | **WARN** |
| Crash trace | 없음 | 없음 | **PASS** |
| Reload 이벤트 | 없음 | 없음 (단일 startup만) | **PASS** |
| 예상치 못한 에러 | 없음 | 없음 | **PASS** |

**log_state: WARN** (기지 이슈 에러만 존재, 예상치 못한 에러 없음)

## 7. 설정 상태 점검

| 항목 | expected | observed | result |
|------|----------|----------|--------|
| APP_ENV | production | production | **PASS** |
| Phase | prod | ops-status: phase=prod | **PASS** |
| GOVERNANCE_ENABLED | true | true | **PASS** |
| EVIDENCE_DB_PATH | 설정됨 | ./data/prod_evidence.db | **PASS** |
| LOG_FILE_PATH | 설정됨 | ./logs/prod.log | **PASS** |
| executor_activated | false | trading_permission=false, dual_lock: trading_authorized=false | **PASS** |
| prod_lock | true | ops-status: prod_lock=true | **PASS** |

**config_state: PASS** (7/7)

## 8. 전체 판정

| 필드 | 값 |
|------|-----|
| overall_result | **WARNING** |
| operational_continuity | **PARTIALLY VERIFIED** |

### 계층별 판정

| 계층 | 판정 | 상세 |
|------|------|------|
| Runtime | **PASS** | master+worker 안정, crash/orphan/reload 없음 |
| Core API | **PASS** | health, status, startup, dashboard 모두 200 |
| Ops API | **PASS** | ops-status 200, 운영 데이터 정상 |
| Data API | **WARN** | data/v2 500 — 기지 이슈(positions.symbol_name) |
| DB | **WARN** | 연결 정상, schema mismatch 존재 |
| Logs | **WARN** | 기지 이슈 에러만, 예상치 못한 에러 없음 |
| Config | **PASS** | 전체 설정 정상, executor 비활성 유지 |

### 기지 이슈 (Known Issues)

| # | 이슈 | 원인 | 영향 | 카드 필요 |
|---|------|------|------|----------|
| KI-1 | /dashboard/api/data/v2 → 500 | positions.symbol_name 컬럼 미존재 (Alembic 마이그레이션 미적용) | data/v2 엔드포인트 사용 불가 | 별도 마이그레이션 카드 |
| KI-2 | /ready → 503 | readiness probe 내부 _evidence_store/_security_ctx 속성 접근 실패 | readiness probe 비정상 | 별도 조사 카드 |
| KI-3 | /status overall_status=unavailable | 거래 루프 미가동으로 runtime source 미연결 | 정상 동작 (거래 루프 미가동 시 예상) | 없음 |

## 9. S-03 진행 가능 여부

| 필드 | 값 |
|------|-----|
| operator_action_required | **s03_continue_allowed** |

### 판정 근거

| 기준 | 평가 | 근거 |
|------|------|------|
| 핵심 Runtime 안정 | ✅ **충족** | master+worker 정상, crash/orphan/reload 없음 |
| 핵심 API 정상 | ✅ **충족** | health, status, startup, dashboard, ops-status 모두 200 |
| Config 정상 | ✅ **충족** | APP_ENV=production, GOVERNANCE=true, executor=false, prod_lock=true |
| Z-02 핵심 유지 | ✅ **충족** | 재기동 후 4/4 PASS 상태 유지 |
| 기지 이슈 통제 | ✅ **통제 중** | KI-1(schema), KI-2(ready) 모두 식별·기록됨, 핵심 운영에 영향 없음 |
| FAIL 항목 | ⚠️ **있음** | data/v2 500 — 비핵심, 기지 이슈, 별도 카드 대상 |

**결론**: 핵심 운영 안정성 기준 충족. 기지 이슈는 식별·기록되어 있으며 핵심 운영 경로에 영향 없음. **S-03 진행 허용**.

### S-03 상태 고정 문장

> S-03 completed with WARNING; runtime/core/ops/config layers are stable, and known issues KI-1/KI-2 are tracked separately as non-blocking follow-ups.

### B-14 진입 조건

> B-14 entry is allowed because runtime stability and core control-plane integrity are verified despite non-blocking data/readiness follow-ups.

### 다음 카드 분리

| 카드 | 범위 | 유형 |
|------|------|------|
| **B-14** | Operator Safety / Preflight UX / Safe Control Surface | 기능 확장 |
| **KI-1 Follow-up** | data/v2 schema alignment (positions.symbol_name migration) | DB 마이그레이션 |
| **KI-2 Follow-up** | readiness probe alignment (_evidence_store/_security_ctx 속성) | 코드 조사/수정 |

---

**점검 완료 시각**: 2026-03-25T20:00:00+09:00
**점검 수행자**: Claude Code (automated, check-only)
**자동 복구 수행**: false
**코드/설정 수정**: false
**다음 단계**: B-14 착수 / KI-1·KI-2 별도 카드 발행
