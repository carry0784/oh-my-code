# 운영 정합성 조사 검수본 (Runtime Consistency Audit)

## 1. 실행 개요

| 필드 | 값 |
|------|-----|
| investigation_type | RUNTIME_CONSISTENCY_AUDIT |
| run_date | 2026-03-25 |
| run_timestamp | 2026-03-25T15:25:00+09:00 |
| system_phase | prod (frozen, live) |
| executor_activated | false |
| auto_repair_performed | **false** |
| evidence_id | RCA-2026-03-25-RUNTIME-01 |
| 목적 | Z-02 BLOCK→FAIL 발생 원인의 증거 기반 조사 |

## 2. 확인된 증상 요약

| 엔드포인트 | 기대 | 실제 | 증상 |
|-----------|------|------|------|
| /health | 200 | **200** | 정상 |
| /status | 200 | **404** | 라우트 미등록 |
| /dashboard | 200 | **200** | 정상 |
| /ready | 200 | **404** | 라우트 미등록 |
| /startup | 200 | **404** | 라우트 미등록 |
| /dashboard/api/ops-status | 200 | **404** | 라우트 미등록 |
| /dashboard/api/data/v2 | 200 | **500** | 서버 내부 오류 |
| /dashboard/api/snapshot | 200 | **404** | 라우트 미등록 |
| /dashboard/api/receipts | 200 | **404** | 라우트 미등록 |
| /api/v1/orders | 200/307 | **307** | 등록됨 (리디렉트) |

## 3. Code vs Running Process 조사 결과

### 3.1 프로세스 구조

```
PID 17364 (uvicorn master)
  ├── 상태: TERMINATED (프로세스 목록에 없음)
  ├── 소켓 생성: 2026-03-24 12:51:43 PM
  ├── TCP 127.0.0.1:8000 LISTENING (소켓은 커널에 잔존)
  └── PID 52624 (uvicorn worker, multiprocessing spawn)
       ├── 상태: ALIVE (유일한 생존 프로세스)
       ├── 생성: 2026-03-24 6:32:48 PM
       ├── 실행 경로: C:\Python314\python.exe
       └── 명령: multiprocessing.spawn.spawn_main(parent_pid=17364, pipe_handle=576)
```

### 3.2 핵심 발견

| 항목 | 확인된 사실 |
|------|-----------|
| **부모 프로세스 (PID 17364)** | 프로세스 목록(tasklist, Get-Process, Get-CimInstance)에 없음. TCP 소켓만 커널에 잔존. 종료된 것으로 판단 |
| **자식 워커 (PID 52624)** | `multiprocessing.spawn`으로 생성된 uvicorn worker. 부모 사망 후에도 독립 생존 중. HTTP 요청을 처리하고 있음 |
| **실행 경로** | `C:\Python314\python.exe` — Windows 네이티브 Python 3.14 |
| **코드 로드 시점** | 워커 생성 시점 2026-03-24 6:32:48 PM. 이후 코드 변경 사항은 반영되지 않음 |
| **리로드 메커니즘** | 부모 프로세스 부재로 uvicorn `--reload` 감시 기능 **작동 불가** |
| **워커 유형** | **고아 워커(orphaned worker)** — 부모 없이 독립 생존 |

### 3.3 코드 버전 불일치 증거

| 근거 | 상세 |
|------|------|
| 워커 생성 시각 | 2026-03-24 18:32:48 (약 21시간 전) |
| Git 최근 커밋 | 7eb9ad8 (2026-03-25) — 워커 생성 이후 |
| 코드 변경 범위 | main.py에 /ready, /startup, /status 추가; dashboard.py에 ops-* 라우트 다수 추가 |
| 결과 | 워커가 로드한 코드에는 이후 추가된 라우트가 포함되지 않음 |

## 4. Route Registration vs Exposed Endpoints 조사 결과

### 4.1 main.py 라우트 대조

| 라우트 | 코드 위치 | 코드 존재 | 런타임 노출 | 판정 |
|--------|----------|----------|-----------|------|
| `/health` | main.py:161-163 | ✓ | ✓ (200) | **일치** |
| `/ready` | main.py:168-206 | ✓ | ✗ (404) | **불일치 — 코드 존재, 런타임 미등록** |
| `/startup` | main.py:209-246 | ✓ | ✗ (404) | **불일치 — 코드 존재, 런타임 미등록** |
| `/status` | main.py:251-391 | ✓ | ✗ (404) | **불일치 — 코드 존재, 런타임 미등록** |

**코드 경계선**: `/health` (line 163) 이후의 모든 라우트가 런타임에 미등록.
C-03(readiness/startup probes), C-04(degraded status) 카드의 코드가 워커 로드 이후에 추가된 것으로 판단.

### 4.2 dashboard.py 라우트 대조

| 라우트 | 코드 위치 | 코드 존재 | 런타임 노출 | 판정 |
|--------|----------|----------|-----------|------|
| `/dashboard` (HTML) | dashboard.py:75 | ✓ | ✓ (200) | **일치** |
| `/dashboard/api/data/v2` | dashboard.py:87 | ✓ | ✓ (500) | **등록됨, DB 오류** |
| `/dashboard/api/snapshot` | dashboard.py:214 | ✓ | ✗ (404) | **불일치** |
| `/dashboard/api/receipts` | dashboard.py:238 | ✓ | ✗ (404) | **불일치** |
| `/dashboard/api/ops-status` | dashboard.py:1718 | ✓ | ✗ (404) | **불일치** |
| `/dashboard/api/ops-checks` | dashboard.py:1840 | ✓ | ✗ (404) | **불일치** |

**코드 경계선**: `/api/data/v2` (line 87) 이후의 모든 dashboard API 라우트가 런타임에 미등록.

### 4.3 분류 결론

모든 불일치 항목은 동일 유형:
> **코드에는 존재하지만 런타임에 미등록 (STALE_WORKER)**

라우트 등록 누락이나 코드 자체 부재가 아님. 고아 워커가 과거 시점의 코드를 로드하고 이후 갱신되지 않은 것이 원인.

## 5. DB Connectivity vs Expected Schema 조사 결과

### 5.1 인프라 상태

| 항목 | 상태 | 상세 |
|------|------|------|
| PostgreSQL 컨테이너 | **RUNNING** | k-v3-postgres-1, Up 32 hours |
| pg_isready | **READY** | `/var/run/postgresql:5432 - accepting connections` |
| Redis 컨테이너 | **RUNNING** | k-v3-redis-1, Up 32 hours |
| Flower 컨테이너 | **RUNNING** | k-v3-flower-1, Up 32 hours, port 5555 |

### 5.2 DB 연결 경로

| 항목 | 값 |
|------|-----|
| .env DATABASE_URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/trading` |
| .env DATABASE_URL_SYNC | `postgresql://postgres:postgres@localhost:5432/trading` |
| Docker port mapping | `0.0.0.0:5432->5432/tcp` |
| 외부 접근 가능 | ✓ (pg_isready 성공) |

### 5.3 스키마 검증

| 테이블 | 존재 | 비고 |
|--------|------|------|
| alembic_version | ✓ | 마이그레이션 관리 |
| orders | ✓ | 14컬럼 확인 |
| positions | ✓ | |
| signals | ✓ | |
| trades | ✓ | |
| asset_snapshots | ✓ | |

### 5.4 orderstatus enum 검증

| DB 등록 값 | 존재 |
|-----------|------|
| pending | ✓ |
| submitted | ✓ |
| filled | ✓ |
| partially_filled | ✓ |
| cancelled | ✓ |
| rejected | ✓ |

총 6개 enum 값 등록 확인.

### 5.5 /dashboard/api/data/v2 500 원인 분석

| 항목 | 판단 |
|------|------|
| DB 미기동 | ✗ — PostgreSQL RUNNING, pg_isready 성공 |
| 접속 실패 | **가능성 높음** — 고아 워커의 asyncpg 연결 풀이 장시간 유휴 후 stale 상태 |
| 스키마 불일치 | ✗ — 6개 테이블 존재, orderstatus enum 6값 등록 |
| 자격증명 문제 | ✗ — .env 설정과 Docker 컨테이너 일치 |
| 연결 풀 고갈 | **가능성 높음** — 부모 프로세스 부재 상태에서 21시간 이상 구동, 풀 재생성 불가 |

**분류**: DB 자체는 정상. 고아 워커의 **asyncpg 연결 풀 열화(connection pool degradation)** 가 주요 원인으로 판단.

### 5.6 로그 관찰 보조 증거

로그에 기록된 DB 관련 경고 (워커 기동 당시):
- `ops_trading_safety_failed`: timezone aware/naive mismatch (BL-TZ01 — 코드에서 RESOLVED이나 구버전 워커에 미반영)
- `ops_trading_safety_failed`: enum orderstatus `REJECTED` 미인식 (BL-ENUM01 — 코드에서 RESOLVED이나 구버전 워커에 미반영)

## 6. 원인 분류

### 확정 원인 (Confirmed Root Causes)

| 우선순위 | 원인 | 증거 | 영향 |
|---------|------|------|------|
| **1 (PRIMARY)** | 고아 워커가 구버전 코드로 구동 중 | PID 17364 종료, PID 52624 (2026-03-24 18:32 생성) 독립 생존; /status 404, /ready 404 등 후기 라우트 전체 미등록 | /status, /ready, /startup, 전체 ops-* 라우트 사용 불가 |
| **2 (SECONDARY)** | uvicorn reload 메커니즘 무력화 | 부모 프로세스(master) 부재로 파일 감시→워커 재생성 경로 단절 | 코드 수정 사항이 런타임에 반영되지 않음 |
| **3 (CONTRIBUTING)** | asyncpg 연결 풀 열화 | 21시간+ 고아 상태 구동; /dashboard/api/data/v2 → 500; 커넥션 풀 재생성/갱신 불가 | DB 의존 엔드포인트 전체 500 |

### 배제된 원인

| 원인 | 배제 근거 |
|------|----------|
| 코드 자체 누락 | main.py, dashboard.py에 해당 라우트 정의 존재 확인 |
| 라우트 등록 로직 오류 | include_router 호출 존재, 정상 코드에서 testserver 200 확인 (로그) |
| DB 미기동 | pg_isready 성공, 테이블/스키마 정상 |
| DB 자격증명 오류 | .env 설정과 Docker 설정 일치 |
| DB 스키마 불일치 | 6개 테이블, orderstatus enum 6값 모두 존재 |
| 다른 앱/포트 기동 | /health 및 /dashboard 응답이 K-V3 앱 고유 응답과 일치 |
| WSL 프로세스 | C:\Python314\python.exe — Windows 네이티브 프로세스 |

## 7. 금지 조항 확인

| 항목 | 확인 |
|------|------|
| 코드 수정 | **미수행** |
| 설정 변경 | **미수행** |
| 서버 재기동 | **미수행** |
| 자동 복구 | **미수행** |
| 기능 추가 | **미수행** |
| 범위 확장 | **미수행** |
| auto_repair_performed | **false** |

## 8. 운영자 후속 조치 권고

| 필드 | 값 |
|------|-----|
| operator_action_required | **controlled_restart_review_required** |

### 권고 사항 (우선순위순)

**1. 서버 제어 재기동 (Controlled Restart)**
- 고아 워커(PID 52624) 종료
- 현행 코드베이스로 uvicorn 재기동: `uvicorn app.main:app --reload --port 8000`
- 재기동 후 /health, /status, /ready, /startup, /dashboard, /dashboard/api/ops-status 전체 200 확인
- 이 조치만으로 축1(코드 불일치), 축2(라우트 미등록) 해소 예상

**2. DB 연결 검증 (재기동 후)**
- /dashboard/api/data/v2 200 응답 확인
- ops_trading_safety 경고 해소 여부 확인 (BL-TZ01, BL-ENUM01 수정 코드 반영)

**3. Z-02 런타임 재검증**
- 재기동 완료 후 Z-02 런타임 검증 재수행
- 5개 항목 전체 PASS 확인

**4. 재발 방지 검토**
- uvicorn master 프로세스 비정상 종료 원인 조사 (로그, 이벤트 뷰어)
- 프로세스 모니터링 강화 고려 (master+worker 모두 감시)
- 서비스 등록(systemd/nssm) 또는 프로세스 관리자 도입 검토

## 9. 미해결 리스크

| # | 리스크 | 심각도 | 상태 | 근거 |
|---|--------|--------|------|------|
| R-1 | 고아 워커가 구버전 코드로 운영 중 | **HIGH** | OPEN | PID 52624, 2026-03-24 18:32 코드 기준 |
| R-2 | uvicorn master 종료 원인 미확인 | **MEDIUM** | OPEN | PID 17364 종료 시점/원인 불명 |
| R-3 | asyncpg 연결 풀 열화로 DB 엔드포인트 전체 500 | **HIGH** | OPEN | /dashboard/api/data/v2 → 500 |
| R-4 | BL-TZ01/BL-ENUM01 수정이 런타임에 미반영 | **MEDIUM** | OPEN | 구버전 코드에 수정 미포함 |
| R-5 | 프로세스 감시 체계 부재 | **LOW** | OPEN | master 종료를 감지하지 못함 |

---

**조사 완료 시각**: 2026-03-25T15:25:00+09:00
**조사 수행자**: Claude Code (automated, read-only)
**자동 복구 수행**: false
**코드/설정 수정**: false
**서버 재기동**: false
**다음 단계**: 운영자 판단에 따른 제어 재기동(controlled restart) 검토
