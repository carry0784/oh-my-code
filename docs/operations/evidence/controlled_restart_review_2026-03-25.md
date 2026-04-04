# Controlled Restart Review 검수본

## 1. 실행 개요

| 필드 | 값 |
|------|-----|
| review_type | CONTROLLED_RESTART_REVIEW |
| run_date | 2026-03-25 |
| run_timestamp | 2026-03-25T15:40:00+09:00 |
| system_phase | prod (frozen, live) |
| executor_activated | false |
| confirmed_root_cause | orphaned uvicorn worker (PID 52624, parent PID 17364 terminated) |
| auto_repair_performed | **false** |
| evidence_id | RESTART-REVIEW-2026-03-25-01 |

## 2. Restart 필요성 검토

### 2.1 현 상태가 용인 가능한가?

| 평가 항목 | 판정 | 근거 |
|-----------|------|------|
| 헌법 준수 상태 | **불충분** | /status (C-04), /ready·/startup (C-03) 미동작 — 헌법 기반 관찰 체계 부분 무력화 |
| 운영 점검 체계 | **불충분** | Z-02 Daily Check 항목 #3(status), #4(ready/startup) 지속 FAIL — 점검 통과 불가 |
| 운영 대시보드 API | **불충분** | ops-status, ops-checks 등 전체 ops-* 엔드포인트 미등록 — Tab 3 운영 상태 조회 불가 |
| DB 엔드포인트 | **불충분** | /dashboard/api/data/v2 → 500 — 대시보드 데이터 조회 불가 |
| 코드↔런타임 정합성 | **불일치** | 고아 워커가 2026-03-24 18:32 기준 코드 서빙 — BL-TZ01, BL-ENUM01 수정 미반영 |

**결론**: 현 상태 지속은 **용인 불가**. 코드↔런타임 불일치로 관찰·점검·운영 체계가 부분 무력화되어 있음. Controlled restart가 필요.

### 2.2 restart 이외의 대안이 있는가?

| 대안 | 평가 | 비고 |
|------|------|------|
| 코드 수정으로 해결 | **불가** | 코드 수정 금지 (운영 규약). 또한 문제는 코드가 아닌 런타임 정합성 |
| uvicorn reload 신호 전송 | **불가** | master 프로세스 부재로 reload 메커니즘 무력화 |
| 워커에 직접 신호 전송 | **부적절** | 고아 워커의 코드 리로드 보장 불가, 예측 불가능한 동작 위험 |
| 현 상태 유지 | **부적절** | Z-02 FAIL 지속, 관찰 체계 부분 무력화 |

**결론**: Controlled restart가 현재 **유일하고 최선의 조치**.

## 3. 종료 대상 적정성 검토

### 3.1 프로세스 식별 증거

| 항목 | 확인된 값 | 확인 방법 | 신뢰도 |
|------|----------|----------|--------|
| 종료 대상 PID | **52624** | Get-CimInstance Win32_Process | high |
| 프로세스 이름 | python.exe | tasklist, CIM | high |
| 실행 경로 | C:\Python314\python.exe | CIM CommandLine | high |
| 부모 PID | 17364 (terminated) | CIM ParentProcessId | high |
| 생성 시각 | 2026-03-24 18:32:48 | CIM CreationDate | high |
| 역할 | uvicorn multiprocessing worker | CommandLine: `multiprocessing.spawn.spawn_main(parent_pid=17364)` | high |
| 포트 바인딩 | 127.0.0.1:8000 (부모 PID 17364 소켓 상속) | Get-NetTCPConnection | high |

### 3.2 유일한 Python 프로세스인가?

| 확인 | 결과 |
|------|------|
| 시스템 전체 Python 프로세스 수 | **1개** (PID 52624만 존재) |
| PID 52624의 자식 프로세스 | **없음** |
| PID 17364의 다른 자식 | **없음** (52624만 확인) |
| 다른 uvicorn/celery 프로세스 | **없음** (Windows 네이티브 기준; Celery는 Docker 미사용 또는 미기동) |

### 3.3 잘못된 프로세스 종료 위험

| 리스크 | 평가 | 근거 |
|--------|------|------|
| 다른 앱의 Python 종료 | **극히 낮음** | Python 프로세스가 PID 52624 단 1개. CommandLine이 multiprocessing worker로 명확 식별 |
| 종료 후 포트 해제 지연 | **낮음** | 부모 소켓(PID 17364)이 커널에 잔존할 수 있으나 TIME_WAIT 후 해제 예상 |
| Celery worker 혼동 | **없음** | Celery 프로세스 미확인; Docker Flower만 기동 중 |

### 3.4 종료 전 추가 확인 필요 사항

| # | 확인 항목 | 이유 |
|---|----------|------|
| 1 | `tasklist /fi "imagename eq python.exe"` 재확인 | 종료 직전 PID 52624이 여전히 유일한 Python인지 최종 확인 |
| 2 | `netstat -ano \| grep :8000` 재확인 | 포트 8000 소유 PID가 변경되지 않았는지 확인 |
| 3 | 처리 중 요청 없는지 확인 | `curl http://localhost:8000/health` 응답 후 즉시 종료 (in-flight 요청 최소화) |

**판정**: 종료 대상 식별 **충분**. 오종료 위험 **극히 낮음**.

## 4. 재기동 기준 적정성 검토

### 4.1 코드 기준선

| 항목 | 값 | 근거 |
|------|-----|------|
| 현행 승인 기준선 | `7eb9ad8` (master HEAD) | git log 최신 커밋; governance-go-baseline |
| 기준선 명칭 | governance-go-baseline | dashboard.py docstring 기록 |
| 기준선 포함 범위 | /status, /ready, /startup, ops-* 라우트, BL-TZ01 수정, BL-ENUM01 수정 전체 | git diff 기반 |

### 4.2 실행 엔트리포인트

| 항목 | 권장 값 | 근거 |
|------|--------|------|
| 명령 | `uvicorn app.main:app --reload --port 8000` | CLAUDE.md Build & Run Commands |
| Python | `C:\Python314\python.exe` (3.14.3) | 현재 sys.executable; site-packages에 의존성 설치됨 |
| uvicorn 버전 | 0.40.0 | `C:/Python314/python.exe -c "import uvicorn; print(uvicorn.__version__)"` |
| Working directory | `C:\Users\Admin\K-V3` | 프로젝트 루트; .env 위치 |

### 4.3 환경 변수 / .env

| 항목 | 확인 상태 | 비고 |
|------|----------|------|
| .env 파일 존재 | ✓ | `C:\Users\Admin\K-V3\.env` |
| APP_ENV=production | ✓ | |
| GOVERNANCE_ENABLED=true | ✓ | |
| DATABASE_URL | ✓ | `postgresql+asyncpg://postgres:postgres@localhost:5432/trading` |
| EVIDENCE_DB_PATH | ✓ | `./data/prod_evidence.db` |
| LOG_FILE_PATH | ✓ | `./logs/prod.log` |
| DEBUG=false | ✓ | |

### 4.4 Python 환경 (sys.path)

| 경로 | 용도 |
|------|------|
| `C:\Python314` | 기본 Python 경로 |
| `C:\Users\Admin\K-V3\src` | kdexter 패키지 (site-packages에 등록) |
| `C:\Python314\Lib\site-packages` | 의존성 패키지 |

### 4.5 인프라 의존성

| 서비스 | 상태 | 포트 | 비고 |
|--------|------|------|------|
| PostgreSQL | **RUNNING** (Docker) | 5432 | k-v3-postgres-1, Up 32h |
| Redis | **RUNNING** (Docker) | 6379 | k-v3-redis-1, Up 32h |
| Flower | **RUNNING** (Docker) | 5555 | k-v3-flower-1, Up 32h |

### 4.6 재발 방지 확인 사항

| 항목 | 확인 방법 |
|------|----------|
| master 프로세스 생존 확인 | 재기동 후 `tasklist`에서 uvicorn master + worker 두 프로세스 모두 존재하는지 확인 |
| --reload 동작 확인 | 파일 변경 감지 로그가 출력되는지 확인 |
| 포트 충돌 방지 | 기존 소켓(PID 17364) 해제 확인 후 재기동 (TIME_WAIT 상태면 수 초 대기) |

**판정**: 재기동 기준 **명확**. 코드 기준선, 엔트리포인트, 환경, 인프라 모두 식별됨.

## 5. 재검증 범위 검토

### 5.1 필수 검증 항목

| # | 검증 항목 | 기대 값 | 검증 방법 | Z-02 연관 |
|---|----------|--------|----------|----------|
| V-1 | /health → 200 | `{"status":"healthy"}` | `curl http://localhost:8000/health` | Z-02 #3 |
| V-2 | /status → 200, no CRITICAL | 200, `overall_status` 존재 | `curl http://localhost:8000/status` | Z-02 #4 |
| V-3 | /ready → 200 | `{"ready": true/false}` | `curl http://localhost:8000/ready` | 보조 |
| V-4 | /startup → 200 | `{"started": true/false}` | `curl http://localhost:8000/startup` | 보조 |
| V-5 | /dashboard → 200 | HTML, title="K-Dexter Operations Board" | `curl http://localhost:8000/dashboard` | Z-02 #5 |
| V-6 | /dashboard/api/ops-status → 200 | JSON 응답 | `curl http://localhost:8000/dashboard/api/ops-status` | ops 점검 |
| V-7 | /dashboard/api/data/v2 → 200 | JSON 데이터 (DB 연결 정상) | `curl http://localhost:8000/dashboard/api/data/v2` | DB 검증 |
| V-8 | crash/restart loop 없음 | 프로세스 안정, master+worker 생존 | `tasklist`, 로그 확인 | Z-02 #8 |
| V-9 | DB 연결 정상 | asyncpg 연결 풀 활성 | V-7 200 + 로그에 DB 오류 없음 | DB 검증 |
| V-10 | master+worker 프로세스 정상 | 두 프로세스 모두 tasklist에 존재 | `tasklist \| grep python` | 재발 방지 |

### 5.2 범위 충분성 평가

| 평가 항목 | 판정 |
|-----------|------|
| Z-02 BLOCK 4개 항목 전체 커버 | ✓ (V-1=health, V-2=status, V-5=dashboard, V-8=crash loop) |
| Z-02 FAIL 항목 커버 | ✓ (V-2=/status) |
| 추가 발견 엔드포인트 커버 | ✓ (V-3=ready, V-4=startup, V-6=ops-status, V-7=data/v2) |
| DB 연결 검증 커버 | ✓ (V-7 + V-9) |
| 프로세스 안정성 커버 | ✓ (V-8 + V-10) |

**판정**: 재검증 범위 **충분**. Z-02 전체 항목 + 추가 발견 항목 + DB + 프로세스 안정성 모두 포함.

## 6. 리스크 및 차단 조건

### 6.1 리스크 목록

| # | 리스크 | 심각도 | 발생 가능성 | 차단/완화 방법 |
|---|--------|--------|-----------|--------------|
| R-1 | 포트 8000 해제 지연 (기존 소켓 잔존) | MEDIUM | 중간 | PID 52624 종료 후 `netstat` 확인; TIME_WAIT면 수 초 대기 후 재확인; 해제 안 되면 `--port 8001` 임시 사용 후 복귀 |
| R-2 | 구버전 Python 환경/venv로 재기동 | LOW | 낮음 | 재기동 명령에 `C:\Python314\python.exe -m uvicorn` 명시; 재기동 후 /status 존재 확인으로 즉시 검증 |
| R-3 | 다른 working directory에서 기동 | LOW | 낮음 | 명시적 `cd C:\Users\Admin\K-V3` 후 기동; .env 로드 확인 |
| R-4 | DB 연결 풀 초기화 실패 | LOW | 낮음 | PostgreSQL RUNNING 확인 완료; 재기동 시 새 연결 풀 생성; V-7로 즉시 검증 |
| R-5 | 추가 고아 프로세스 잔존 | LOW | 극히 낮음 | 현재 Python 프로세스 1개만 존재 확인; 종료 후 `tasklist` 재확인 |
| R-6 | lifespan 초기화 실패 (governance gate) | MEDIUM | 낮음 | GOVERNANCE_ENABLED=true 확인; /ready 체크로 검증; 실패 시 로그에 FATAL 출력 예상 |

### 6.2 차단 조건 (Blocking Conditions)

아래 조건 중 하나라도 해당되면 재기동을 **진행하지 않는다**:

| # | 차단 조건 | 확인 방법 |
|---|----------|----------|
| B-1 | PID 52624 종료 후 포트 8000이 5분 이상 해제되지 않음 | `netstat -ano \| grep :8000` |
| B-2 | Docker 인프라(PostgreSQL, Redis)가 기동 중이 아님 | `docker ps` |
| B-3 | .env 파일이 누락되거나 APP_ENV≠production | `cat .env \| grep APP_ENV` |
| B-4 | `C:\Python314\python.exe`에 uvicorn/fastapi 미설치 | `python -c "import uvicorn, fastapi"` |
| B-5 | Git working directory가 dirty 상태이고 확인되지 않은 변경이 있음 | `git status` (현재 dirty지만 이미 인지된 변경) |

## 7. 금지 조항 확인

| 항목 | 확인 |
|------|------|
| 실제 프로세스 종료 | **미수행** |
| 실제 서버 재기동 | **미수행** |
| 코드 수정 | **미수행** |
| 설정 변경 | **미수행** |
| 자동 복구 | **미수행** |
| 기능 추가 | **미수행** |
| auto_repair_performed | **false** |

## 8. 운영자 승인 전 체크리스트

### Pre-Restart Checklist (운영자가 재기동 실행 전 확인)

| # | 항목 | 확인 명령 | 기대 결과 |
|---|------|----------|----------|
| P-1 | PID 52624가 여전히 유일한 Python 프로세스 | `tasklist /fi "imagename eq python.exe"` | PID 52624 1건만 |
| P-2 | 포트 8000 소유가 PID 17364 | `netstat -ano \| grep :8000` | 17364 LISTENING |
| P-3 | Docker 인프라 기동 중 | `docker ps` | postgres, redis, flower UP |
| P-4 | .env 정상 | `cat .env \| grep APP_ENV` | production |
| P-5 | 코드 기준선 확인 | `git log --oneline -1` | 7eb9ad8 |
| P-6 | Working directory 확인 | `pwd` | C:\Users\Admin\K-V3 |

### Restart Execution Sequence (운영자 실행 순서)

```
# Step 1: 고아 워커 종료
taskkill /PID 52624 /F

# Step 2: 포트 해제 확인 (수 초 대기 가능)
netstat -ano | grep :8000
# 결과: 항목 없음 또는 TIME_WAIT만 → 진행
# 결과: LISTENING 잔존 → 30초 대기 후 재확인

# Step 3: 현행 코드 기준 재기동
cd C:\Users\Admin\K-V3
C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8000

# Step 4: 재검증 (별도 터미널)
# V-1~V-10 순차 확인
```

### Post-Restart Checklist (운영자가 재기동 후 확인)

| # | 항목 | 확인 명령 | 기대 결과 |
|---|------|----------|----------|
| V-1 | /health | `curl http://localhost:8000/health` | 200, `{"status":"healthy"}` |
| V-2 | /status | `curl http://localhost:8000/status` | 200, `overall_status` 필드 존재 |
| V-3 | /ready | `curl http://localhost:8000/ready` | 200 |
| V-4 | /startup | `curl http://localhost:8000/startup` | 200 |
| V-5 | /dashboard | `curl -o /dev/null -w "%{http_code}" http://localhost:8000/dashboard` | 200 |
| V-6 | /dashboard/api/ops-status | `curl http://localhost:8000/dashboard/api/ops-status` | 200, JSON |
| V-7 | /dashboard/api/data/v2 | `curl http://localhost:8000/dashboard/api/data/v2` | 200, JSON |
| V-8 | crash loop 없음 | `tasklist \| grep python` | master + worker 2건 |
| V-9 | DB 연결 | V-7 200 + 로그 오류 없음 | 정상 |
| V-10 | master+worker | `tasklist \| grep python` | 2개 프로세스 |

## 9. 권고 결론

| 필드 | 값 |
|------|-----|
| restart_review_result | **APPROVED** |
| blocking_risks | **없음** (모든 리스크에 완화 방법 존재) |
| required_pre_restart_checks | P-1 ~ P-6 (6개) |
| required_post_restart_verifications | V-1 ~ V-10 (10개) |
| operator_action_required | **controlled_restart_execution_allowed** |

### 판정 근거

| 기준 | 평가 | 상세 |
|------|------|------|
| 종료 대상 식별 충분성 | **충분** | PID, 이름, 경로, 부모관계, 생성시각, 역할 전부 확인. 유일한 Python 프로세스. 오종료 위험 극히 낮음 |
| 재기동 기준 명확성 | **명확** | 코드 기준선(7eb9ad8), 실행 경로(C:\Python314), 엔트리포인트(uvicorn app.main:app), 환경(.env), 인프라(Docker UP) 전부 확인 |
| 재검증 범위 충분성 | **충분** | Z-02 전 항목 + 추가 엔드포인트 + DB + 프로세스 안정성 = 10개 검증 항목 |
| 리스크 수용 가능성 | **수용 가능** | 6개 리스크 모두 LOW~MEDIUM, 전부 차단/완화 방법 존재 |

**최종 판정**: Controlled restart는 현재 최선의 조치이며, 종료 대상·재기동 기준·재검증 범위가 모두 충분히 명확하다. **운영자 승인 후 실행 가능**.

---

**검토 완료 시각**: 2026-03-25T15:40:00+09:00
**검토 수행자**: Claude Code (automated, review-only)
**실제 실행**: 없음 (review only)
**다음 단계**: 운영자 승인 → Pre-Restart Checklist → 재기동 실행 → Post-Restart Verification
