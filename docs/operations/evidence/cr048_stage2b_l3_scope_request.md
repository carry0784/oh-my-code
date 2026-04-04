# CR-048 Stage 2B L3 범위 요청서

**문서 ID:** GOV-L3-STAGE2B-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**변경 등급:** L3 (서비스 로직 — runtime-adjacent)
**전제:** Stage 2A SEALED (A 승인 후)
**참조:** `cr048_staged_l3_expansion_proposal.md` Stage 2, A 판정 2A/2B 분리 지시

> **본 문서는 Stage 2B L3 범위 요청서입니다. Stage 2A 봉인 완료 후, 별도 A 승인 전까지 구현 착수는 금지됩니다.**

---

## 1. 문서 성격

Stage 2B는 **runtime-adjacent 영향이 있는 범위**를 별도 분리한 것입니다.
Stage 2A(정적 메타데이터/순수 함수)와 달리, 이 범위는:

- `asset_service.py` 접촉 (symbol_screener/backtest_qualification import 존재)
- `Symbol.status` 실제 DB UPDATE (runtime 종목 풀 변경)
- TTL 자동 만료 실행 (CORE→WATCH 자동 강등)
- 상태 전이 감사 이벤트 DB 기록

을 포함하므로 **별도 심사가 필요**합니다.

---

## 2. 실제 Runtime 영향 경로도

```
                asset_service.py
                     |
          ┌──────────┼──────────┐
          v          v          v
   transition_    TTL 만료    screen_and_update()
   status()      처리()      qualify_and_record()
          |          |          |
          v          v          v
   Symbol.status  Symbol.status  qualification_status
   DB UPDATE      DB UPDATE      DB UPDATE
          |          |          |
          └──────────┼──────────┘
                     v
            symbols 테이블 status 변경
                     |
                     v (간접 read path)
          ┌──────────┼──────────┐
          v          v          v
   runtime_loader  multi_symbol  universe_manager
   (status 읽기)   _runner       (CORE only 필터)
                     |
                     v
            실행면 종목 풀 변경
```

### 영향받는 Read Path 목록

| Read Path | 파일 | 읽는 대상 | 영향 |
|-----------|------|-----------|------|
| RuntimeStrategyLoader symbol 필터 | `runtime_loader_service.py` | `Symbol.status == CORE` | CORE→WATCH 강등 시 실행 대상에서 제외 |
| UniverseManager 적격 풀 | `universe_manager.py` (미구현) | `Symbol.status == CORE` | Phase 6에서 CORE pool로 사용 예정 |
| MultiSymbolRunner 대상 종목 | `multi_symbol_runner.py` (미구현) | CORE symbols | Phase 6에서 사용 예정 |
| SymbolScreener 재심사 대상 | `symbol_screener.py` | `Symbol.status` 전체 | Stage 3에서 사용 예정 |
| BacktestQualifier 대상 | `backtest_qualification.py` | `Symbol.status != EXCLUDED` | Phase 4에서 사용 예정 |

**현재 상태:** runtime_loader_service, universe_manager, multi_symbol_runner는
아직 Symbol.status를 실시간으로 읽는 구현이 **활성화되어 있지 않거나 미구현**.
하지만 asset_service.py의 변경은 향후 이 경로들에 영향을 줄 **기반을 만드는** 것이므로,
사전 심사가 필요합니다.

---

## 3. Universe / Screener / Qualification / Candidate Pool 영향 표

| 영역 | Stage 2B 변경으로 인한 영향 | 직접/간접 | 위험도 |
|------|--------------------------|:---------:|:------:|
| **Universe (CORE pool)** | TTL 만료 → CORE→WATCH 강등 → CORE pool 축소 | 직접 | **HIGH** |
| **Screener** | screen_and_update() 기존 로직 유지, 2B에서 수정 시 판정 변경 가능 | 직접 | **HIGH** |
| **Qualification** | qualify_and_record() 기존 로직 유지, 2B에서 수정 시 자격 변경 가능 | 직접 | **MEDIUM** |
| **Candidate Pool** | candidate_expire_at TTL 만료 처리 → 후보 종목 제거 | 직접 | **HIGH** |
| **Regime 전환** | regime 전환 시 TTL 일괄 만료 → 전체 CORE pool 재심사 유발 | 직접 | **CRITICAL** |

---

## 4. Fail-Closed 전략

| 시나리오 | Fail-Closed 행동 | 근거 |
|----------|-----------------|------|
| TTL 만료 처리 중 DB 오류 | **만료 중단, CORE 유지** | 종목을 잘못 강등하는 것보다 유지가 안전 |
| Symbol-Broker 교차 검증 실패 | **등록 거부** | 금지 브로커 접근보다 등록 차단이 안전 |
| status transition 중 예외 | **전이 중단, 기존 status 유지** | 부분 전이 방지 |
| regime 전환 시 TTL 일괄 만료 오류 | **일괄 만료 중단, 개별 TTL 유지** | 전면 강등보다 점진적 만료가 안전 |
| screen_and_update 중 screener 오류 | **screening 중단, status 미변경** | 잘못된 screening 결과 반영 방지 |
| asset_service import 실패 | **서비스 시작 거부** | 불완전 서비스보다 미시작이 안전 |

---

## 5. 롤백 조건

| 트리거 | 롤백 행동 | 자동/수동 | 가역성 |
|--------|----------|:---------:|:------:|
| **회귀 테스트 실패** | 전체 Stage 2B 코드 revert | 수동 | YES |
| **TTL 만료가 예상 외 대량 강등 유발** | TTL 처리 기능 disable (flag) | 수동 (Operator) | YES |
| **Symbol.status 오류 전이 감지** | 해당 전이 revert (이전 status 복원) | 수동 | 조건부 (감사 이벤트로 추적 가능) |
| **runtime pool 급감** (CORE 50% 이상 감소) | Stage 2B 전체 비활성화 | 수동 (Approver) | YES |
| **symbol_screener/backtest_qualification import 변경** | 즉시 중단 + 코드 revert | 수동 | YES |
| **A 중단 지시** | 즉시 중단 + revert | 수동 | YES |

---

## 6. 파일 3분할 분류표

### GREEN (허용) — Stage 2B에서 변경 가능

| 파일 | 작업 | 등급 | 위험도 |
|------|------|:----:|:------:|
| `app/services/asset_service.py` | Symbol-Broker 검증 통합, TTL 만료 실행, 감사 이벤트 | L3 | **HIGH** |
| `app/schemas/asset_schema.py` | 감사 응답, TTL 응답 스키마 확장 | L2 | LOW |
| `tests/test_asset_service_phase2b.py` | **신규** — 서비스 통합 테스트 | L1 | LOW |

### RED (금지) — Stage 2B에서도 변경 불가

| 파일/범위 | 사유 |
|-----------|------|
| `app/services/symbol_screener.py` | **Stage 3** — screen_and_update 내부 호출은 기존 유지 |
| `app/services/backtest_qualification.py` | **Phase 4** — qualify_and_record 내부 호출은 기존 유지 |
| `app/services/runtime_strategy_loader.py` | Data Plane — Phase 5 |
| `app/services/runtime_loader_service.py` | Data Plane — Phase 5 |
| `app/services/feature_cache.py` | Data Plane — Phase 5 |
| `app/services/injection_gateway.py` | Stage 1 SEALED |
| `app/services/registry_service.py` | Stage 1 SEALED |
| `app/api/routes/registry.py` | Stage 1 SEALED |
| `workers/tasks/*` | Celery task — Stage 3 이상 |
| `exchanges/*` | 거래소 어댑터 |
| `app/services/regime_detector.py` | 수정 금지 (이벤트 수신 인터페이스 정의만 허용) |

### AMBER (회색지대) — 사전 예외 승인 시에만

| 파일 | 잠재적 필요성 | 예외 조건 |
|------|-------------|-----------|
| `app/api/routes/asset.py` (존재 시) | TTL/감사 조회 API | GET만 + write는 사전 승인 |
| `app/models/asset.py` | column/enum 추가 (Stage 2A에서 미포함 시) | ADD 만 허용 |
| `app/core/constitution.py` | 상수 추가 (Stage 2A에서 미포함 시) | 추가만 허용 |
| `tests/test_asset_registry.py` (기존) | 기존 테스트 호환 수정 | assertion 정렬만 |

---

## 7. Data Plane Impact Matrix

| 변경 항목 | 직접 영향 파일 | 간접 영향 파일 | 현재 runtime 도달 가능 | Fail-Closed | Rollback 가능 | 승인 단계 |
|-----------|---------------|---------------|:--------------------:|:-----------:|:-------------:|:---------:|
| **Symbol-Broker 검증 → asset_service 통합** | asset_service.py | 없음 (등록 시점만) | **LOW** (새 등록만 영향) | YES (등록 거부) | YES (code revert) | **2B** |
| **TTL 만료 실행** (CORE→WATCH) | asset_service.py | runtime_loader, universe | **YES** | NO (강등 비가역) | NO (이미 전환) | **2B** |
| **상태 전이 감사 이벤트 기록** | asset_service.py | 없음 (append-only log) | **NO** (읽기 전용 기록) | N/A | YES (log 삭제/무시) | **2B** |
| **EXCLUDED→CORE 직행 금지 강화** | asset_service.py | 없음 | **NO** (기존 방어 강화) | YES (전이 거부) | YES (code revert) | **2B** |
| **Regime 전환 TTL 인터페이스** | asset_service.py | regime_detector (읽기만) | **YES** (일괄 만료 시) | YES (만료 중단) | YES (인터페이스 제거) | **2B** |
| **screen_and_update 수정** (만약 수정 시) | asset_service.py | symbol_screener, runtime | **YES** | 구현 의존 | 조건부 | **2B 별도 승인** |

---

## 8. Stage 2B 범위 제한 규칙

### asset_service.py 내부 접촉 규칙

| 영역 | 허용 | 금지 |
|------|------|------|
| **신규 메서드 추가** | YES — validate_broker_for_symbol(), process_expired_ttl(), record_status_audit() | — |
| **기존 메서드 수정** | 최소한 — register_symbol() 내 broker 검증 추가만 | screen_and_update(), qualify_and_record() 수정 금지 |
| **import 변경** | constitution.py 추가 import | symbol_screener, backtest_qualification import 변경 금지 |
| **기존 함수 삭제** | 금지 | — |
| **기존 함수 시그니처 변경** | 금지 | — |

### screen_and_update / qualify_and_record 보호 규칙

이 두 함수는 **Stage 3/Phase 4 연결 지점**이므로:

1. 함수 본문 수정 **금지**
2. 함수 시그니처 변경 **금지**
3. 함수 호출 경로 변경 **금지**
4. 이 함수가 사용하는 import (symbol_screener, backtest_qualification) 변경 **금지**
5. 만약 이 함수에 버그 발견 시 → **즉시 중단, A 보고**

---

## 9. 중단 조건 / 봉인 조건

### 중단 조건

| 조건 | 행동 |
|------|------|
| 회귀 실패 | 즉시 중단, 원인 분석 |
| RED 파일 변경 필요 | 즉시 중단, 예외 요청 |
| screen_and_update() 수정 필요 | **즉시 중단** — Stage 3 경계 |
| qualify_and_record() 수정 필요 | **즉시 중단** — Phase 4 경계 |
| symbol_screener/backtest_qualification import 변경 필요 | **즉시 중단** |
| TTL 만료가 예상 외 대량 강등 유발 | 즉시 중단, 기능 disable |
| runtime pool 급감 감지 | 즉시 중단, Approver 통보 |
| A 중단 지시 | 즉시 중단 |

### 봉인 조건

| # | 조건 | 검증 방법 |
|:--:|------|-----------|
| 1 | Symbol-Broker 교차 검증 테스트 PASS | 금지 브로커 등록 거부 + 허용 브로커 정상 |
| 2 | TTL 만료 로직 테스트 PASS | 만료 → CORE→WATCH 강등 정상 |
| 3 | EXCLUDED→CORE 직행 금지 테스트 PASS | 상태 전이 거부 확인 |
| 4 | EXCLUDED→WATCH A 승인 필요 테스트 PASS | manual_override 필수 확인 |
| 5 | 상태 전이 감사 이벤트 테스트 PASS | from/to/reason/at 기록 |
| 6 | Fail-closed 동작 테스트 PASS | DB 오류 시 기존 status 유지 |
| 7 | screen_and_update **미수정** 확인 | `git diff` 기준 0 lines changed |
| 8 | qualify_and_record **미수정** 확인 | `git diff` 기준 0 lines changed |
| 9 | symbol_screener/backtest_qualification **미접촉** 확인 | `git diff` 기준 0 lines |
| 10 | 기존 계약 테스트 유지 (57+30건) | regression |
| 11 | Stage 2A 테스트 유지 | regression |
| 12 | 전체 회귀 PASS (Stage 2A 기준선+a) | `pytest --tb=short -q` |
| 13 | **A 판정** | 제출 후 판정 |

---

## 10. 예외 승인 필요 지점

| 지점 | 예외 유형 | 처리 |
|------|-----------|------|
| screen_and_update() 버그 수정 | Phase 3 경계 | **A 직접 판정** |
| qualify_and_record() 버그 수정 | Phase 4 경계 | **A 직접 판정** |
| symbol_screener import 경유 함수 호출 | Stage 3 경계 | **금지 (별도 CR 필요)** |
| Celery task 추가 (TTL 자동 만료 스케줄) | L4 | **Stage 3 이상에서만** |
| runtime_loader에 새 필터 추가 | Phase 5 | **금지** |

---

**Stage 2B는 Stage 2A 봉인 완료 후, 별도 A 승인 전까지 구현 착수 금지입니다.**

---

```
CR-048 Stage 2B L3 Scope Request v1.0
Document ID: GOV-L3-STAGE2B-001
Date: 2026-04-04
Authority: A
Status: REQUEST (Stage 2A 봉인 + A 별도 승인 전까지 구현 착수 불가)
Gate: LOCKED (유지 전제)
Prerequisite: Stage 2A SEALED
asset_service.py: GREEN (Stage 2B에서만)
symbol_screener: RED (미접촉)
backtest_qualification: RED (미접촉)
screen_and_update: FROZEN (미수정)
qualify_and_record: FROZEN (미수정)
Runtime 도달: YES (TTL 만료, status 변경)
Fail-Closed: 전 항목 적용
```
