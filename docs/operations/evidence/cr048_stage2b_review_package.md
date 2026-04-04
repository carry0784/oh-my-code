# CR-048 Stage 2B 별도 심사 패키지

**문서 ID:** GOV-L3-STAGE2B-REVIEW-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Stage 2A SEALED (2026-04-04, 4812/4812 PASS)
**참조:** GOV-L3-STAGE2B-001 (범위 요청서), GOV-L3-DELTA-2A2B-001 (경계 분석)

> **A 승인 전까지 Stage 2B 구현 착수는 금지됩니다.**

---

## 1. Stage 2A에서는 NO였지만 2B에서 YES가 되는 항목

| 항목 | Stage 2A | Stage 2B | 위험도 |
|------|:--------:|:--------:|:------:|
| **Runtime 도달** | NO | **YES** | — |
| **TTL 만료 실행** | NO (계산식만) | **YES** (CORE→WATCH 강등) | HIGH |
| **Symbol.status read path 반영** | NO (정의만) | **YES** (runtime_loader가 읽음) | HIGH |
| **asset_service.py 접촉** | NO | **YES** | HIGH |
| **Candidate pool 영향** | NO | **YES** (TTL 만료 → pool 축소) | HIGH |
| **SymbolStatusAudit DB INSERT** | NO (테이블만) | **YES** (전이 시 기록) | LOW |
| **Broker 검증 → 등록 거부** | NO (함수만) | **YES** (등록 시점 차단) | LOW |
| **Regime TTL 일괄 만료** | NO | **제안: Stage 3으로 이관** | CRITICAL |

---

## 2. 허용/금지/회색지대 파일 표

### GREEN (허용)

| 파일 | 작업 | 위험도 |
|------|------|:------:|
| `app/services/asset_service.py` | 신규 메서드 추가 + register_symbol() broker 검증 통합 | **HIGH** |
| `app/schemas/asset_schema.py` | 감사 응답 확장 (필요 시) | LOW |
| `tests/test_asset_service_phase2b.py` | **신규** — 서비스 통합 테스트 | LOW |

### RED (금지)

| 파일 | 사유 |
|------|------|
| `app/services/symbol_screener.py` | Stage 3 |
| `app/services/backtest_qualification.py` | Phase 4 |
| `app/services/runtime_strategy_loader.py` | Phase 5 |
| `app/services/runtime_loader_service.py` | Phase 5 |
| `app/services/feature_cache.py` | Phase 5 |
| `app/services/injection_gateway.py` | Stage 1 SEALED |
| `app/services/registry_service.py` | Stage 1 SEALED |
| `app/api/routes/registry.py` | Stage 1 SEALED |
| `app/services/regime_detector.py` | 수정 금지 |
| `workers/tasks/*` | Celery — Stage 3+ |
| `exchanges/*` | 거래소 어댑터 |

### AMBER (회색지대)

| 파일 | 조건 |
|------|------|
| `app/api/routes/asset.py` (신규 시) | GET만 + 사전 보고 |
| `app/models/asset.py` | column 추가 시 사전 보고 |
| `app/core/constitution.py` | 상수 추가만, 기존 변경 금지 |
| `tests/test_asset_registry.py` | assertion 정렬만 |

---

## 3. asset_service.py 변경 라인 예상 범위

### 현재 코드 구조 (372 lines)

```
Line   1-38   : imports + logger
Line  42-46   : __init__
Line  48-81   : Read (get_symbol, get_symbol_by_id, list_symbols, list_core_symbols)
Line  83-127  : Create (register_symbol)
Line 129-172  : Status Transitions (transition_status)
Line 174-185  : TTL (get_expired_candidates)
Line 187-217  : Screening (record_screening, get_screening_history)
Line 219-283  : Screener Integration (screen_and_update) ⛔ FROZEN
Line 285-356  : Qualification Integration (qualify_and_record) ⛔ FROZEN
Line 358-372  : Qualification History (get_qualification_history)
```

### 예상 변경

| 영역 | 라인 | 변경 내용 | 기존 함수 수정 |
|------|------|-----------|:-------------:|
| **imports** (L1-38) | +3~5 lines | `from app.services.asset_validators import ...` 추가 | 추가만 |
| **register_symbol()** (L83-127) | +5~10 lines | `validate_broker_policy()` 호출 삽입, 위반 시 raise | **수정** (guard 추가) |
| **transition_status()** (L129-172) | +10~15 lines | `validate_status_transition()` 호출 + SymbolStatusAudit 기록 | **수정** (guard + audit) |
| **신규: process_expired_ttl()** | +20~30 lines | get_expired_candidates() 호출 → 각 symbol CORE→WATCH | **추가** |
| **신규: record_status_audit()** | +15~20 lines | SymbolStatusAudit row INSERT | **추가** |
| **screen_and_update()** (L219-283) | 0 lines | **FROZEN — 미수정** | ⛔ |
| **qualify_and_record()** (L285-356) | 0 lines | **FROZEN — 미수정** | ⛔ |

**예상 순변경: +55~80 lines, 기존 함수 수정 2개 (register_symbol, transition_status)**

### 기존 import 변경 계획

```python
# 추가할 import (asset_validators.py에서)
from app.services.asset_validators import (
    validate_broker_policy,
    validate_status_transition,
    compute_candidate_ttl,
)
from app.models.asset import SymbolStatusAudit  # audit model

# 건드리지 않을 import (FROZEN)
from app.services.symbol_screener import ...     # ⛔ 유지
from app.services.backtest_qualification import ... # ⛔ 유지
```

---

## 4. TTL 만료 영향 경로

```
[수동 호출]  asset_service.process_expired_ttl()
                |
                v
    get_expired_candidates()  ← 이미 구현됨 (L174-185)
    SELECT * FROM symbols WHERE status='core' AND candidate_expire_at < NOW()
                |
                v
    각 symbol에 대해:
        validate_status_transition("core", "watch")  ← 2A 순수 함수
                |
                v (허용 시)
        symbol.status = WATCH  (DB UPDATE)
        symbol.status_reason_code = "ttl_expired"
                |
                v
        record_status_audit(from="core", to="watch", reason="ttl_expired")
                |
                v
        SymbolStatusAudit INSERT (append-only)
                |
                v (간접 영향)
        runtime_loader 다음 cycle에서 이 symbol 제외
        (runtime_loader.py는 미수정 — 기존 SELECT WHERE status='core' 사용)
```

### TTL 만료 핵심 제한

| 제한 | 값 |
|------|-----|
| 호출 방식 | **수동만** — Celery task/beat 등록 금지 |
| 1회 처리 상한 | 제안: max 10 symbols (대량 강등 방지) |
| 실패 시 | 중단, CORE 유지 (fail-closed) |
| 자동 스케줄 | **Stage 3으로 이관** |

---

## 5. Symbol.status Read Path 영향표

| Read Path | 파일 | 쿼리 | 현재 활성 | 2B 영향 |
|-----------|------|------|:---------:|:-------:|
| runtime_loader CORE 필터 | `runtime_loader_service.py` | `WHERE status='core'` | **미확인** (L3 limited) | 간접 — CORE→WATCH 강등 시 제외 |
| list_core_symbols | `asset_service.py` L75 | `WHERE status=CORE` | 존재 | 직접 — pool 축소 |
| screen_and_update 결과 | `asset_service.py` L264-271 | status 업데이트 | 존재 (FROZEN) | 미영향 — 미수정 |
| universe_manager | 미구현 | — | **미구현** | 미영향 |
| multi_symbol_runner | 미구현 | — | **미구현** | 미영향 |

**결론:** 현재 활성 read path 중 Stage 2B가 영향을 주는 것은 `list_core_symbols()` 하나.
`runtime_loader_service.py`는 L3 limited 상태이므로 실제 runtime 영향은 **제한적**.

---

## 6. Fail-Closed 동작 설명

| 시나리오 | 동작 | 안전 방향 |
|----------|------|:---------:|
| **register_symbol: broker 검증 실패** | 등록 거부 (DB INSERT 안 함) | ✅ 금지 브로커 차단 |
| **transition_status: 전이 규칙 위반** | 전이 거부 (DB flush 안 함) | ✅ 기존 status 유지 |
| **transition_status: DB 오류** | 예외 전파, 기존 status 유지 | ✅ 부분 전이 방지 |
| **process_expired_ttl: DB 오류** | 만료 처리 중단, CORE 유지 | ✅ 잘못된 강등 방지 |
| **process_expired_ttl: 대량 만료** | max 10 제한 (1회 호출당) | ✅ 급감 방지 |
| **record_status_audit: 기록 실패** | 경고 로그, 전이 자체는 완료 | ⚠️ 감사 누락 가능 (수용 가능) |

---

## 7. Rollback 조건 6개 재확인

| # | 트리거 | 롤백 행동 | 자동/수동 | 가역성 |
|:--:|--------|----------|:---------:|:------:|
| 1 | **회귀 테스트 실패** | Stage 2B 코드 전체 revert | 수동 | YES |
| 2 | **TTL 만료 대량 강등** (CORE 50%↓) | process_expired_ttl disable | 수동 (Operator) | YES |
| 3 | **Symbol.status 오류 전이** | SymbolStatusAudit 기반 복원 | 수동 | YES |
| 4 | **register_symbol 오류 등록** | 해당 symbol soft-delete/재등록 | 수동 | YES |
| 5 | **symbol_screener/backtest_qual import 변경** | 즉시 중단 + revert | 수동 | YES |
| 6 | **A 중단 지시** | 즉시 중단 + revert | 수동 | YES |

---

## 8. Boundary Delta 핵심 질문에 대한 답변

### Q1. screen_and_update() / qualify_and_record() FROZEN 유지 가능한가?

**YES.** Stage 2B에서 추가하는 기능(broker 검증, TTL 만료, 감사 기록)은 모두 **신규 메서드**이거나 **register_symbol/transition_status에 guard 삽입**입니다. screen_and_update()와 qualify_and_record()는 수정할 이유가 없습니다.

### Q2. TTL 자동 스케줄 필요한가?

**NO.** Stage 2B에서는 **수동 호출만** 허용합니다. Celery beat task 등록은 Stage 3에서 SymbolScreener와 함께 도입하는 것이 자연스럽습니다.

### Q3. Regime TTL 일괄 만료는 Stage 2B인가 Stage 3인가?

**Stage 3으로 이관을 제안합니다.** Regime 전환 시 TTL 일괄 만료는:
- RegimeDetector 이벤트 수신이 필요 (Stage 3 인접)
- 전체 CORE pool 영향 (CRITICAL 위험)
- SymbolScreener 재심사와 연동이 자연스러움

Stage 2B에서는 regime_change를 **TTL 만료 사유 코드로만 정의**하고, 실제 연동은 Stage 3에서 수행합니다.

### Q4. asset_service.py import 변경 없이 가능한가?

**YES.** 기존 `symbol_screener`/`backtest_qualification` import는 건드리지 않습니다.
추가하는 import는 `asset_validators`(2A에서 만든 순수 함수)와 `SymbolStatusAudit`(2A에서 만든 모델)뿐입니다.

### Q5. CORE pool 급감 보호 메커니즘 필요한가?

**YES — 1회 처리 상한으로 구현합니다.** `process_expired_ttl(max_count=10)` 파라미터로 1회 호출당 최대 10개만 처리. 나머지는 다음 호출까지 대기. 이는 자동 스케줄이 아닌 수동 호출이므로 운영자가 상황을 보고 제어 가능합니다.

---

## 9. Stage 2B 제안 범위 축소안

Boundary Delta 분석 결과, **Regime TTL 일괄 만료를 Stage 3으로 이관**하면 Stage 2B의 CRITICAL 위험이 제거됩니다.

### 최종 Stage 2B 범위

| 기능 | 포함 | 위험도 |
|------|:----:|:------:|
| register_symbol broker 검증 통합 | **YES** | LOW |
| transition_status + 감사 이벤트 | **YES** | HIGH (fail-closed) |
| process_expired_ttl (수동, max 10) | **YES** | HIGH (fail-closed, 상한 제한) |
| record_status_audit | **YES** | LOW |
| Regime TTL 일괄 만료 | **NO → Stage 3** | ~~CRITICAL~~ 제거 |
| Celery beat task | **NO → Stage 3** | — |
| screen_and_update 수정 | **NO → FROZEN** | — |
| qualify_and_record 수정 | **NO → FROZEN** | — |

---

## 10. 봉인 조건

| # | 조건 |
|:--:|------|
| 1 | Symbol-Broker 교차 검증 테스트 PASS (register_symbol 통합) |
| 2 | TTL 만료 CORE→WATCH 강등 테스트 PASS (max 10 제한 포함) |
| 3 | EXCLUDED→CORE 직행 금지 테스트 PASS |
| 4 | EXCLUDED→WATCH manual_override 필수 테스트 PASS |
| 5 | SymbolStatusAudit 기록 테스트 PASS |
| 6 | Fail-closed 동작 테스트 PASS (DB 오류 시 기존 status 유지) |
| 7 | screen_and_update **미수정** 확인 (git diff 0 lines) |
| 8 | qualify_and_record **미수정** 확인 (git diff 0 lines) |
| 9 | symbol_screener/backtest_qualification import **미변경** 확인 |
| 10 | 기존 계약 테스트 유지 (57+30건) |
| 11 | Stage 2A 테스트 유지 (103건) |
| 12 | 전체 회귀 PASS (4812+a) |
| 13 | **A 판정** |

---

**A 승인 전까지 Stage 2B 구현 착수는 금지됩니다.**

---

```
CR-048 Stage 2B Review Package v1.0
Document ID: GOV-L3-STAGE2B-REVIEW-001
Date: 2026-04-04
Authority: A
Status: REVIEW SUBMITTED (A 판정 대기)
Gate: LOCKED
Prerequisite: Stage 2A SEALED (4812/4812 PASS)
Regime TTL: DEFERRED TO STAGE 3
screen_and_update: FROZEN
qualify_and_record: FROZEN
```
