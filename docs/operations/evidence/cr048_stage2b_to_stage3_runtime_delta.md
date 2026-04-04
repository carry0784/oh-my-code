# CR-048 Stage 2B → Stage 3 Runtime Delta

**문서 ID:** GOV-L3-RUNTIME-DELTA-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Stage 2B L3 SEALED (4844/4844 PASS)

> Stage 2B에서 처음 허용된 runtime touch point와 Stage 3에서 추가로 열릴 지점을 분리 비교한다.

---

## 1. Stage 2B 허용 Runtime Touch (현재 봉인 상태)

| # | Touch Point | 파일 | 유형 | Fail-Closed |
|:-:|-------------|------|------|:-----------:|
| 1 | register_symbol() broker guard | asset_service.py L99-108 | Guard 삽입 | YES — 등록 거부 |
| 2 | transition_status() validator | asset_service.py L178-188 | 기존 교체 | YES — 전이 거부 |
| 3 | transition_status() audit | asset_service.py L199-216 | 추가 기록 | YES — 감사 실패 시 전이 유지 |
| 4 | process_expired_ttl() | asset_service.py L256-300 | 신규 메서드 | YES — 중단, CORE 유지 |
| 5 | _record_status_audit() | asset_service.py L222-252 | 신규 메서드 | N/A (append-only) |

**Stage 2B runtime 요약:** 5개 지점, 전부 fail-closed, read path 영향 1개 (list_core_symbols)

---

## 2. Stage 3 후보 Runtime Touch (미승인 — 심사 대상)

### 2A. 이미 구현 완료된 컴포넌트 (L3 FROZEN/EXISTING)

| 컴포넌트 | 파일 | 라인 | 상태 | Runtime Reach |
|----------|------|:----:|:----:|:-------------:|
| SymbolScreener (5-stage engine) | symbol_screener.py | 313 | **구현 완료** | **NO** — stateless 순수 로직, I/O 없음 |
| screen_and_update() | asset_service.py L347-409 | 63 | **FROZEN** | **YES** — SymbolScreener 호출 + DB flush |
| qualify_and_record() | asset_service.py L413-482 | 70 | **FROZEN** | **YES** — BacktestQualifier 호출 + DB flush |
| ScreeningInput/Output | symbol_screener.py | — | **구현 완료** | **NO** — dataclass |
| test_symbol_screener.py | tests/ | 710 | **구현 완료** | N/A — 테스트 |

**핵심 발견:** `symbol_screener.py`는 이미 구현 완료된 순수 계산 엔진. I/O 없음, DB 없음, 외부 호출 없음. Stage 3에서 이 파일을 "수정"할 필요가 있는지, 아니면 주변 인프라만 추가하면 되는지가 범위 결정의 핵심.

### 2B. Stage 3에서 신규 구현이 필요한 컴포넌트

| 컴포넌트 | 파일 | 상태 | Runtime Reach | 위험 |
|----------|------|:----:|:-------------:|:----:|
| SectorRotator | sector_rotator.py | **미구현** | YES — regime 기반 섹터 가중치 | HIGH |
| DataProvider | data_provider.py | **미구현** | YES — 외부 API 호출 (CoinGecko, KIS) | **CRITICAL** |
| Screening Celery Task | screening_tasks.py | **미구현** | YES — beat schedule, 자동 실행 | **CRITICAL** |
| Beat Schedule 등록 | celery_app.py | **미등록** | YES — L4 경계 | **CRITICAL** |

---

## 3. Stage 2B → Stage 3 NO→YES 전환 항목

| 항목 | Stage 2B | Stage 3 후보 | 위험 증가 |
|------|:--------:|:----------:|:---------:|
| SymbolScreener 호출 | NO (FROZEN) | 수정 불요 (이미 완료) | **NONE** |
| screen_and_update() 수정 | **NO** (FROZEN) | **TBD** — 수정 필요 여부 심사 | MEDIUM~HIGH |
| 외부 API 호출 | **NO** | **YES** (DataProvider) | **CRITICAL** |
| Celery task 등록 | **NO** | **YES** (screening_tasks) | **CRITICAL** |
| Beat schedule 변경 | **NO** | **YES** (celery_app.py) | **CRITICAL** (L4) |
| SectorRotator regime 연결 | **NO** | **YES** | HIGH |
| Symbol.status 자동 변경 | **수동만** | **자동** (Celery 경유) | **CRITICAL** |
| 외부 데이터 의존 | **NO** | **YES** (CoinGecko, KIS) | HIGH |

---

## 4. Runtime Touch Budget 비교

| 측정 항목 | Stage 2B (봉인) | Stage 3 (후보) | 변화 |
|-----------|:--------------:|:-------------:|:----:|
| 변경 함수 수 | 3 (register, transition, ttl) | +3~5 (screener integration, rotator, task) | **2x 증가** |
| 신규 side-effect 수 | 0 (guard/audit만) | +3 (외부 API, auto-demote, beat) | **0→3** |
| 영향 read path 수 | 1 (list_core_symbols) | +2~3 (screener output, rotator weights) | **1→3+** |
| Batch 상한 | 10 (TTL) | TBD (screening 대상 전체?) | **위험 증가** |
| 외부 연결 | 0 | +2~3 (CoinGecko, KIS, KRX) | **0→2+** |
| Rollback 난이도 | LOW (guard 제거) | HIGH (외부 상태, beat 해제) | **증가** |
| Fail-closed 가능 여부 | 전부 YES | 외부 API 실패 시? 부분적 | **약화 가능** |

---

## 5. Blast Radius 분석

### Stage 2B Blast Radius (현재 — 봉인)

```
asset_service.py ─── register_symbol() guard ──→ 등록 거부 (isolated)
                 ├── transition_status() guard ──→ 전이 거부 (isolated)
                 ├── audit recording ──────────→ append-only (no read dependency)
                 └── process_expired_ttl() ────→ max 10, 수동 (contained)
```

**영향 범위:** asset_service.py 내부. 외부 파일 무접촉.

### Stage 3 Blast Radius (후보 — 미승인)

```
screening_tasks.py ─── Celery beat ──→ celery_app.py (L4)
                   ├── DataProvider ──→ 외부 API (CoinGecko, KIS, KRX)
                   ├── SymbolScreener ──→ screen_and_update() (FROZEN?)
                   │                     └── Symbol.status 변경
                   │                     └── candidate_expire_at 설정
                   └── SectorRotator ──→ regime data ──→ sector weights

data_provider.py ──→ 외부 API 실패 시 cascading
                 ├── screening 불가 → 상태 동결? 또는 WATCH 강제?
                 └── rate limit → 부분 screening?
```

**영향 범위:** 외부 API + Celery beat + Symbol.status 자동 변경 + regime 연동. Stage 2B 대비 blast radius **3~5배 확대**.

---

## 6. 위험 분류

### CRITICAL (L4 경계 또는 외부 의존)

| # | 항목 | 사유 |
|:-:|------|------|
| 1 | Beat schedule 등록 | L4 변경. 자동 실행 경로 개방 |
| 2 | 외부 API 호출 (DataProvider) | 네트워크 의존. 실패 시 cascading |
| 3 | Symbol.status 자동 변경 | 수동→자동 전환. CORE pool 자동 축소 가능 |

### HIGH

| # | 항목 | 사유 |
|:-:|------|------|
| 4 | SectorRotator regime 연결 | CR-046 regime 금지와 충돌 가능성 |
| 5 | screen_and_update() FROZEN 해제 여부 | Stage 2B 봉인 조건 파기 |
| 6 | Batch 상한 미정 | TTL은 max 10, screening은? |

### MEDIUM

| # | 항목 | 사유 |
|:-:|------|------|
| 7 | symbol_screener.py 수정 | 이미 완료된 순수 로직, 수정 필요 시 범위 확대 |
| 8 | 테스트 호환성 | 기존 710 테스트와 신규 코드 정합 |

---

## 7. 핵심 질문 (Stage 3 범위 요청서에서 답해야 할 것)

| # | 질문 | Stage 2B 기준 |
|:-:|------|:------------:|
| 1 | screen_and_update()를 수정하는가? | FROZEN |
| 2 | Beat schedule에 screening task를 등록하는가? | 금지 |
| 3 | 외부 API 호출을 허용하는가? | 금지 |
| 4 | Symbol.status 자동 변경을 허용하는가? | 수동만 |
| 5 | Batch 상한은? | 10 (TTL) |
| 6 | SectorRotator는 regime data를 어디서 가져오는가? | N/A |
| 7 | DataProvider 실패 시 fallback 정책은? | N/A |
| 8 | CR-046 regime 금지와 충돌은? | 금지 유지 |

---

```
CR-048 Stage 2B→Stage 3 Runtime Delta v1.0
Document ID: GOV-L3-RUNTIME-DELTA-001
Date: 2026-04-04
Authority: A
Stage 2B: SEALED (5 touch points, all fail-closed)
Stage 3: REVIEW PENDING (CRITICAL items 3, HIGH items 3)
Blast Radius: 3-5x expansion vs Stage 2B
```
