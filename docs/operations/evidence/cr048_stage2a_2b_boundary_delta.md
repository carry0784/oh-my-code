# CR-048 Stage 2A→2B Boundary Delta

**문서 ID:** GOV-L3-DELTA-2A2B-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**목적:** Stage 2A 봉인 후, Stage 2B 심사를 위한 경계 분석

> Stage 2B 심사 시 참조 문서입니다. 구현 승인은 별도 A 판정이 필요합니다.

---

## 1. Stage 2A에서 추가된 정적 정의

| 추가 항목 | 파일 | 유형 | Runtime 도달 |
|-----------|------|------|:------------:|
| `BROKER_POLICY_RULES` | constitution.py | 상수 dict | NO |
| `TTL_DEFAULTS` (48/72/72h) | constitution.py | 상수 dict | NO |
| `TTL_MIN_HOURS` (12) / `TTL_MAX_HOURS` (168) | constitution.py | 상수 int | NO |
| `STATUS_TRANSITION_RULES` (6개 전이) | constitution.py | 상수 dict | NO |
| `validate_broker_policy()` | asset_validators.py | 순수 함수 | NO |
| `validate_status_transition()` | asset_validators.py | 순수 함수 | NO |
| `compute_candidate_ttl()` | asset_validators.py | 순수 함수 | NO |
| `check_forbidden_brokers()` | asset_validators.py | 순수 함수 | NO |
| `is_excluded_sector()` | asset_validators.py | 순수 함수 | NO |
| `validate_symbol_data()` | asset_validators.py | 순수 함수 | NO |
| `validate_constitution_consistency()` | asset_validators.py | 순수 함수 | NO |
| `SymbolStatusAudit` 테이블 | asset.py + migration 020 | DDL 정의 | NO |
| 6종 Pydantic 응답 스키마 | asset_schema.py | 스키마 | NO |

---

## 2. Stage 2B에서 처음으로 Runtime에 닿는 지점

| 항목 | 현재 (2A 봉인 후) | 2B에서 변경 시 | Runtime 도달 변화 |
|------|:-----------------:|:--------------:|:-----------------:|
| `Symbol.status` DB UPDATE | **미실행** (정의만) | `asset_service.transition_status()` 경유 실행 | **NO → YES** |
| TTL 만료 처리 | **미실행** (계산식만) | `asset_service.process_expired_ttl()` 경유 실행 | **NO → YES** |
| SymbolStatusAudit 기록 | **테이블만 존재** (0 rows) | `asset_service`에서 전이 시 기록 | **NO → YES** (간접) |
| Broker 검증 → 등록 거부 | **함수만 존재** | `asset_service.register_symbol()` 통합 | **NO → YES** (등록 시점) |
| Regime TTL 일괄 만료 | **인터페이스 미정의** | `asset_service` 이벤트 수신 메서드 | **NO → YES** |

---

## 3. Runtime 도달 전환 상세 (NO → YES)

### 3.1 Symbol.status DB UPDATE

```
2A: validate_status_transition("core", "watch") → (True, "allowed")
    ↑ 값만 반환, DB 미접촉

2B: asset_service.transition_status(symbol_id, WATCH, "ttl_expired")
    → Symbol.status = WATCH (DB UPDATE)
    → runtime_loader가 다음 cycle에서 이 symbol 제외
    ↑ DB 변경 → runtime pool 영향
```

**Fail-Closed:** 전이 중 예외 → 기존 status 유지 (DB flush 안 함)
**Rollback:** 감사 이벤트(SymbolStatusAudit)로 이전 status 복원 가능

### 3.2 TTL 만료 처리

```
2A: compute_candidate_ttl(75.0, "crypto") → timedelta(hours=42)
    ↑ 값만 반환, DB 미접촉

2B: asset_service.process_expired_ttl()
    → get_expired_candidates() (이미 구현됨)
    → 각 symbol: CORE → WATCH (DB UPDATE)
    → runtime pool 축소
```

**Fail-Closed:** DB 오류 → 만료 중단, CORE 유지
**Rollback:** 개별 강등이므로 각 symbol 복원 가능 (감사 이벤트 추적)

### 3.3 Broker 검증 → 등록 거부

```
2A: validate_broker_policy(["ALPACA"], "crypto") → ["ALPACA is forbidden"]
    ↑ 위반 목록 반환, DB 미접촉

2B: asset_service.register_symbol(data)
    → validate_broker_policy() 호출
    → 위반 시 등록 거부 (DB INSERT 안 함)
    → 기존 종목 미영향 (신규 등록만 차단)
```

**Fail-Closed:** 검증 실패 → 등록 거부 (안전 방향)
**Rollback:** 등록 거부는 비가역적이지 않음 (재등록 가능)

---

## 4. 변경 항목별 종합 위험 평가

| 변경 항목 | 2A 도달 | 2B 도달 | Fail-Closed | Rollback | 위험도 |
|-----------|:-------:|:-------:|:-----------:|:--------:|:------:|
| Status transition 실행 | NO | **YES** | YES (flush 안 함) | YES (audit 복원) | **HIGH** |
| TTL 만료 실행 | NO | **YES** | YES (중단 유지) | YES (개별 복원) | **HIGH** |
| Broker 검증 통합 | NO | **YES** (등록 시점) | YES (등록 거부) | YES (재등록) | **LOW** |
| Audit 기록 | NO | **YES** (간접) | N/A (append-only) | N/A | **LOW** |
| Regime TTL 일괄 만료 | NO | **YES** | YES (일괄 중단) | 조건부 (대량 복원 어려움) | **CRITICAL** |

---

## 5. 2B 심사 시 핵심 질문

1. **screen_and_update() / qualify_and_record() 보호**: 이 두 함수가 Stage 2B에서도 **FROZEN** 유지 가능한가?
2. **TTL 자동 스케줄**: Celery task 없이 수동 호출만으로 충분한가, 아니면 beat 등록이 필요한가?
3. **Regime 연동**: regime 전환 시 TTL 일괄 만료가 정말 Stage 2B 범위인가, Stage 3으로 미뤄야 하는가?
4. **symbol_screener import**: asset_service.py를 수정할 때, 기존 import를 건드리지 않는 것이 현실적으로 가능한가?
5. **CORE pool 급감 보호**: TTL 만료로 CORE 50% 이상 감소 시 자동 중단 메커니즘이 필요한가?

---

```
CR-048 Stage 2A→2B Boundary Delta v1.0
Document ID: GOV-L3-DELTA-2A2B-001
Date: 2026-04-04
Authority: A
Purpose: Stage 2B 심사 참조 자료
Stage 2A: SEALED
Stage 2B: REVIEW PENDING
```
