# Controlled Restart Execution 검수본

## 1. 실행 개요

| 필드 | 값 |
|------|-----|
| execution_type | CONTROLLED_RESTART_EXECUTION |
| run_date | 2026-03-25 |
| run_timestamp | 2026-03-25T19:52:00+09:00 |
| system_phase | prod (frozen, live) |
| executor_activated | false |
| terminated_pid | 52624 |
| restart_command | `cd C:\Users\Admin\K-V3 && C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8000` |
| auto_repair_performed | **false** |
| evidence_id | RESTART-EXEC-2026-03-25-01 |

## 2. Pre-Restart Checklist 결과

| # | 항목 | 기대 | 확인 | 결과 |
|---|------|------|------|------|
| P-1 | PID 52624 유일한 Python | 1건 | PID 52624 1건, CommandLine=multiprocessing.spawn(parent_pid=17364) | **PASS** |
| P-2 | 포트 8000 소유 PID 17364 | LISTENING 17364 | TCP 127.0.0.1:8000 LISTENING 17364 | **PASS** |
| P-3 | Docker 인프라 기동 | postgres, redis, flower UP | k-v3-postgres-1 Up 32h, k-v3-redis-1 Up 32h, k-v3-flower-1 Up 32h | **PASS** |
| P-4 | APP_ENV=production | production | APP_ENV=production | **PASS** |
| P-5 | 코드 기준선 7eb9ad8 | 7eb9ad8 | `7eb9ad8 fix: Signal.metadata 예약어 충돌 해소...` | **PASS** |
| P-6 | Working directory | C:\Users\Admin\K-V3 | /c/Users/Admin/K-V3 | **PASS** |

**Pre-Restart: 6/6 PASS → 진행 승인**

## 3. 종료 수행 결과

| 항목 | 상세 |
|------|------|
| 종료 명령 | `taskkill /PID 52624 /F` |
| 종료 결과 | 성공 (프로세스 종료됨) |
| 포트 해제 확인 | `netstat -ano \| grep :8000` → PORT_8000_FREE (즉시 해제) |
| 잔존 프로세스 | 없음 |

## 4. 재기동 수행 결과

| 항목 | 상세 |
|------|------|
| 재기동 명령 | `cd C:\Users\Admin\K-V3 && C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8000` |
| 기동 확인 | 5초 후 /health → 200 |
| Master PID | **81064** (uvicorn reloader, `uvicorn app.main:app --reload --port 8000`) |
| Worker PID | **86524** (multiprocessing.spawn, parent_pid=81064) |
| 생성 시각 | 2026-03-25 오후 7:52:14 |
| 포트 바인딩 | TCP 127.0.0.1:8000 LISTENING PID 81064 |
| Lifespan 로그 | env=production, evidence_mode=SQLITE_PERSISTED, governance_gate_initialized=true, receipt_mode=FILE_PERSISTED |

**프로세스 구조 정상**: Master(81064) → Worker(86524), 부모-자식 관계 확인.

## 5. Post-Restart Verification 결과 표

### Z-02 핵심 항목 (원래 BLOCK → 재검증)

| # | 항목 | expected | observed | result | confidence | notes |
|---|------|----------|----------|--------|------------|-------|
| V-1 | /health → 200 | HTTP 200 | HTTP 200; body=`{"status":"healthy"}` | **PASS** | high | status_code=200; body_valid=true |
| V-2 | /status → 200, no CRITICAL | HTTP 200, no CRITICAL | HTTP 200; overall_status=unavailable; degraded_reasons=4 sources unavailable; no CRITICAL | **PASS** | high | status_code=200; critical_alert=none; sources unavailable은 runtime data source 미연결 상태 (정상 — 거래 루프 미가동 시 예상됨) |
| V-5 | /dashboard → 200 | HTTP 200 | HTTP 200 | **PASS** | high | status_code=200 |
| V-8 | crash/restart loop 없음 | master+worker stable | Master 81064 + Worker 86524 both alive; no crash trace in logs | **PASS** | high | crash_trace=none; restart_loop=false; master_alive=true; worker_alive=true |

**Z-02 핵심: 4/4 PASS**

### 보조 항목

| # | 항목 | expected | observed | result | confidence | notes |
|---|------|----------|----------|--------|------------|-------|
| V-3 | /ready → 200 | HTTP 200 | HTTP 503; governance_gate=true, evidence_store=false, security_context=false | **WARN** | high | status_code=503; governance_gate 초기화 완료이나 readiness probe가 _evidence_store/_security_ctx 접근 실패; 속성명 불일치 가능성 (코드 조사 필요, 이번 범위 외) |
| V-4 | /startup → 200 | HTTP 200 | HTTP 200; started=true; governance_initialized=true, state_slots_initialized=true | **PASS** | high | status_code=200; all_started=true |
| V-6 | /dashboard/api/ops-status → 200 | HTTP 200, JSON | HTTP 200; app_env=production, phase=prod, prod_lock=true, enforcement_state=UNKNOWN | **PASS** | high | status_code=200; ops-status 정상 반환; enforcement_state=UNKNOWN은 런타임 소스 미연결 시 예상 동작 |
| V-7 | /dashboard/api/data/v2 → 200 | HTTP 200 | HTTP 500; `positions.symbol_name does not exist` | **FAIL** | high | DB 연결 자체는 성공; 첫 쿼리(positions)에서 `symbol_name` 컬럼 미존재로 실패 → 이후 트랜잭션 전체 abort. 원인: Alembic 마이그레이션 미적용 (코드 ORM에 symbol_name 정의, DB 테이블에 미존재) |
| V-9 | DB 연결 정상 | asyncpg 연결 성공 | 연결 성공, 쿼리 실행 가능; but positions 테이블 스키마 불일치 (symbol_name 컬럼 누락) | **WARN** | high | db_connection=true; schema_mismatch=true; missing_column=positions.symbol_name; migration_required=true |
| V-10 | master+worker 프로세스 | 2개 프로세스 | Master 81064 + Worker 86524; parent-child 관계 정상 | **PASS** | high | process_count=2; master_alive=true; worker_alive=true; parent_child=valid |

### 결과 요약

| 판정 | 항목 수 |
|------|--------|
| PASS | **7** (V-1, V-2, V-4, V-5, V-6, V-8, V-10) |
| WARN | **2** (V-3 /ready 503, V-9 schema mismatch) |
| FAIL | **1** (V-7 /dashboard/api/data/v2 500) |

## 6. 전체 판정

| 필드 | 값 |
|------|-----|
| overall_result | **PARTIALLY VERIFIED** |
| operational_continuity | **PARTIALLY VERIFIED** |

### 판정 근거

**해소된 항목 (orphaned worker 관련)**:
- ✅ /health → 200 (이전 PASS → 유지)
- ✅ /status → 200 (이전 FAIL/404 → **PASS로 승격**)
- ✅ /dashboard → 200 (이전 PASS → 유지)
- ✅ /dashboard/api/ops-status → 200 (이전 404 → **정상**)
- ✅ /startup → 200 (이전 404 → **정상**)
- ✅ crash/restart loop 없음 (이전 BLOCK → **PASS**)
- ✅ master+worker 프로세스 구조 정상

**미해소 항목 (orphaned worker와 무관, 별도 원인)**:
- ⚠️ /ready → 503: readiness probe 내부 속성 접근 실패 (governance_gate는 초기화됨)
- ❌ /dashboard/api/data/v2 → 500: `positions.symbol_name` 컬럼 미존재 (Alembic 마이그레이션 미적용)
- ⚠️ DB schema mismatch: ORM 모델에 `symbol_name` 정의, DB 테이블에 미존재

### V-7 FAIL 원인 분석

```
Root cause: positions.symbol_name 컬럼이 DB에 없음
  ├── ORM 정의: Position.symbol_name (코드에 존재)
  ├── DB 상태: positions 테이블 13컬럼 (symbol_name 미포함)
  ├── 마이그레이션 파일: alembic/versions/ 에 존재할 수 있으나 미적용
  └── 영향: /dashboard/api/data/v2 에서 positions 조회 시 첫 쿼리 실패 → 트랜잭션 abort → 이후 모든 쿼리 실패
```

**이 이슈는 orphaned worker 문제와 무관**. 구버전 서버에서도 동일하게 발생했을 DB 스키마 불일치.

## 7. 자동 복구/범위 확장 미수행 확인

| 항목 | 확인 |
|------|------|
| 코드 수정 | **미수행** |
| 설정 변경 | **미수행** |
| 자동 복구 | **미수행** |
| 기능 추가 | **미수행** |
| 범위 확장 | **미수행** (V-7 FAIL은 기록만, 수정 미시도) |
| 마이그레이션 실행 | **미수행** (코드 수정/DB 변경 금지) |
| auto_repair_performed | **false** |

## 8. operator_action_required

| 필드 | 값 |
|------|-----|
| operator_action_required | **s03_allowed** |

### 판정 설명

**Z-02 핵심 항목 4/4 PASS** — orphaned worker 원인의 런타임 불일치가 **완전 해소**됨:
- /health, /status, /dashboard, crash loop 모두 정상
- 코드↔런타임 정합성 회복
- master+worker 프로세스 구조 정상

**잔여 이슈 2건은 orphaned worker와 무관한 별도 건**:
1. `/ready` 503 — readiness probe 속성명 조사 필요 (코드 레벨, 별도 카드 대상)
2. `/dashboard/api/data/v2` 500 — `positions.symbol_name` 마이그레이션 필요 (별도 카드 대상)

### 후속 조치 권고

| 우선순위 | 항목 | 유형 |
|---------|------|------|
| 1 | `alembic upgrade head` 실행하여 positions.symbol_name 마이그레이션 적용 | 별도 카드(DB 마이그레이션) |
| 2 | /ready probe의 _evidence_store/_security_ctx 속성명 조사 | 별도 조사 |
| 3 | Z-02 Daily Check 재수행으로 전체 판정 갱신 | 운영 점검 |

## 9. Evidence 경로

| 항목 | 경로 |
|------|------|
| 본 검수본 | `docs/operations/evidence/controlled_restart_execution_2026-03-25.md` |
| Restart Review | `docs/operations/evidence/controlled_restart_review_2026-03-25.md` |
| Runtime Consistency Audit | `docs/operations/evidence/runtime_consistency_audit_2026-03-25.md` |
| Z-02 Runtime Verification | `docs/operations/evidence/z02_runtime_2026-03-25.md` |
| Z-02 Daily Check | `docs/operations/evidence/z02_daily_2026-03-25.md` |

---

**실행 완료 시각**: 2026-03-25T19:55:00+09:00
**실행 수행자**: Claude Code (automated)
**다음 단계**: Z-02 Daily Check 재수행 / positions.symbol_name 마이그레이션 카드 검토
