# Phase B — OHLCV 400D Ingestion Path Verification Plan

**문서 ID:** phase_b_ohlcv_400d_ingestion_verification_plan  
**작성일:** 2026-04-10  
**상태:** PLAN_READY  
**Gate 대상:** Gate 3 — `OHLCV_400D_INGESTION_PATH_VERIFIED`  
**관련 대시보드:** `cr046_phase_b_gate_dashboard.md`  
**문서 유형:** DESIGN/PLAN (구현 코드 없음)

---

## 1. 목적

Phase B Replay Engine 진입을 위한 Gate 3 충족 조건으로, 400일치 OHLCV 데이터 수집 파이프라인이 기능적이고 신뢰 가능한 상태임을 사전에 체계적으로 검증한다.

구체적으로는 다음 세 가지를 목표로 한다.

1. **소스 경로 확인:** Binance Futures (CCXT) → `ohlcv_history` 테이블까지의 수집 경로가 end-to-end로 동작함을 확인한다.
2. **품질 기준 충족:** 커버리지(>=99%), 중복 처리, 타임스탬프 단조성, 이벤트 메타데이터 태깅을 정량적으로 검증한다.
3. **fail-closed 보장:** 기준 미달 시 부분 데이터 사용을 원천 차단하는 ABORT 조건이 올바르게 동작함을 확인한다.

이 계획서는 설계/계획 문서이며, 실제 수집 실행은 별도의 Step 실행 단계에서 수행된다.

---

## 2. 소스 식별

### 2.1 거래소 API

| 항목 | 값 |
|------|----|
| 거래소 | Binance Futures (선물) |
| 라이브러리 | CCXT (`fetch_ohlcv`) |
| 엔드포인트 유형 | REST (배치 요청) |
| 배치 크기 | 최대 1,000 캔들 / 요청 (`CCXT_BATCH_LIMIT = 1000`) |
| 요청 방식 | 페이지네이션 — `since` 파라미터를 이전 배치 마지막 타임스탬프로 슬라이딩 |

### 2.2 대상 심볼

| 심볼 | CCXT 표기 | 우선순위 |
|------|-----------|----------|
| SOL/USDT (영구선물) | `SOL/USDT:USDT` | 1순위 |
| BTC/USDT (영구선물) | `BTC/USDT:USDT` | 2순위 |

### 2.3 타임프레임 및 기대 행수

| 항목 | 값 |
|------|----|
| 타임프레임 | `1h` (1시간 봉) |
| 수집 기간 | 400일 |
| 예상 캔들 수 / 심볼 | **9,600개** (400일 x 24시간) |
| 캔들 간격 | 3,600,000 ms (1시간) |
| 총 예상 행수 (2심볼) | **19,200개** |

### 2.4 저장 대상

- **테이블:** `ohlcv_history` (`OhlcvHistory` ORM 모델)
- **유니크 제약:** `uq_ohlcv_canonical_slot` — `(exchange, symbol, timeframe, open_time)` 복합 유니크
- **중복 처리 정책:** `ON CONFLICT DO NOTHING` (PostgreSQL 전용 upsert, `HistoryDataManager.ingest_candles()`)

---

## 3. 검증 항목 (V-001 ~ V-007)

### V-001: API 연결성 및 레이트 리밋 준수

**목적:** CCXT를 통해 Binance Futures API에 정상 접속되고, 배치 요청 중 레이트 리밋 오류가 발생하지 않음을 확인한다.

| 검증 포인트 | 기준 |
|-------------|------|
| API ping 응답 | HTTP 200 정상 |
| `fetch_ohlcv` 최초 1회 성공 | 1,000개 캔들 반환 |
| 레이트 리밋 위반 (429/418) | 발생 시 backoff 후 재시도, 최대 3회 |
| 총 배치 요청 수 | ceil(9,600 / 1,000) = 10회 / 심볼 |

**판정 기준:** ping 성공 + 최초 배치 정상 반환 → PASS

---

### V-002: 수집 완전성 (Coverage)

**목적:** 400일 기간 동안 9,600개 캔들이 99% 이상 수집되었는지 확인한다. `HistoryDataManager.check_coverage()` 메서드의 `CoverageReport`를 활용한다.

| 필드 | 기준 |
|------|------|
| `coverage_pct` | >= 99.0% |
| `total_candles` | >= 9,504 (9,600 x 0.99) |
| `days_covered` | >= 396.0일 |

**판정 기준:** `coverage_pct >= 99.0` → PASS / `< 95.0` → ABORT (V-007 참조)

---

### V-003: 중복 제거 검증 (Deduplication)

**목적:** 동일한 `(exchange, symbol, timeframe, open_time)` 조합이 두 번 이상 삽입 시도될 때, `ON CONFLICT DO NOTHING`이 올바르게 작동하여 `duplicate_ignored` 카운트가 증가하고 실제 행은 하나만 존재함을 확인한다.

**검증 방법:**
1. 이미 수집된 7일 구간을 대상으로 동일 데이터를 재수집 시도
2. `IngestionResult.candles_skipped > 0` 확인
3. DB에서 해당 구간 `COUNT(*)` = 최초 수집 수와 동일한지 확인

| 검증 포인트 | 기준 |
|-------------|------|
| `candles_inserted` (재시도 시) | 0 (새 삽입 없음) |
| `candles_skipped` (재시도 시) | > 0 (모두 무시됨) |
| DB 행 수 변화 | 없음 (동일 유지) |

**판정 기준:** 재삽입 후 DB 행 수 불변 → PASS

---

### V-004: 타임스탬프 단조성 검증 (Monotonicity)

**목적:** `ohlcv_history` 에 저장된 캔들의 `open_time`이 strictly increasing이고, 연속 캔들 간 간격이 정확히 3,600,000 ms임을 확인한다.

**검증 방법:** `check_coverage()`에서 반환되는 `gap_timestamps`와 별개로, 전체 타임스탬프 목록을 순회하여 아래를 점검한다.

| 검증 포인트 | 기준 |
|-------------|------|
| 역전 (timestamp[i] <= timestamp[i-1]) | 0건 |
| 간격 != 3,600,000 ms인 인접 쌍 | gap으로 분류, V-006 처리 대상 |
| 중복 타임스탬프 | 0건 (유니크 제약으로 DB 수준 보장) |

**판정 기준:** 역전 0건 + 중복 0건 → PASS / 역전 1건 이상 → ABORT

---

### V-005: 이벤트 메타데이터 태깅 검증 (Event Metadata)

**목적:** `event_week_flag`, `high_volatility_flag` 컬럼이 정상적으로 업데이트 가능하고, 태깅된 캔들의 필드값이 올바름을 확인한다.

**ORM 필드 (OhlcvHistory 모델):**
- `event_week_flag: bool` (server_default="false")
- `macro_event_type: str | None` (FOMC, CPI, NFP, HALVING 등)
- `high_volatility_flag: bool` (server_default="false")

**검증 방법:**
1. 테스트용 시간 범위(검증 기간 내 임의 24시간 구간)에 `tag_event_week()` 호출
2. 해당 구간 캔들의 `event_week_flag = True`, `macro_event_type` 값 확인
3. 동일 구간 일부 캔들에 `tag_high_volatility()` 호출 후 `high_volatility_flag = True` 확인

| 검증 포인트 | 기준 |
|-------------|------|
| `tag_event_week()` 반환값 | > 0 (업데이트 발생) |
| 태깅된 캔들의 `event_week_flag` | True |
| `tag_high_volatility()` 반환값 | > 0 (업데이트 발생) |
| 태깅된 캔들의 `high_volatility_flag` | True |

**판정 기준:** 두 태깅 메서드 모두 정상 업데이트 확인 → PASS

---

### V-006: Backfill/Repair 경로 (Gap 탐지 → 재수집 → 재검증)

**목적:** `check_coverage()`의 갭 탐지 결과를 바탕으로 누락 구간을 식별하고, 해당 구간을 재수집하여 갭이 해소되는지 확인한다.

**처리 흐름:**

```
check_coverage() → gap_timestamps 식별
  → 갭 구간 re-fetch (CCXT fetch_ohlcv, 해당 since 파라미터)
  → ingest_candles() 재삽입 (ON CONFLICT DO NOTHING 으로 중복 안전)
  → check_coverage() 재실행 → gap_count 감소 확인
```

| 검증 포인트 | 기준 |
|-------------|------|
| 갭 탐지 → 재수집 사이클 | 최소 1회 정상 동작 확인 |
| 재수집 후 `gap_count` | 재수집 전보다 감소 또는 0 |
| 재수집 후 `coverage_pct` | 재수집 전보다 향상 |

**판정 기준:** 재수집 후 갭 감소 확인 → PASS

---

### V-007: Fail-Closed 조건 (부분 데이터 사용 차단)

**목적:** 수집 품질이 임계값 미달일 때 파이프라인이 ABORT하여 부분 데이터가 백테스트에 사용되지 않음을 보장한다.

| 조건 | 임계값 | 판정 |
|------|--------|------|
| `coverage_pct < 95.0%` | 즉시 ABORT | 부분 데이터 사용 금지 |
| `gap_count > 24` (1일치 누락 초과) | 즉시 ABORT | 연속성 보장 불가 |
| 단조성 위반 (역전 타임스탬프) | 즉시 ABORT | 재생 순서 신뢰 불가 |
| API 레이트 리밋 초과 | RETRY, backoff, 최대 3회 후 ABORT | |

**검증 방법:** 각 ABORT 조건을 별도 시뮬레이션(mock 또는 제한된 데이터셋)으로 ABORT 경로가 실행됨을 확인한다.

**판정 기준:** 각 조건 발동 시 ABORT 경로 진입 확인 → PASS

---

## 4. 검증 스크립트 설계

### 4.1 스크립트 위치 및 이름

```
scripts/phase_b_ohlcv_ingestion_verify.py
```

### 4.2 동작 원칙

- **읽기 전용 검증 모드:** 이 계획서 단계에서는 실제 수집을 수행하지 않음
- **검증 전용:** 이미 수집된 데이터를 대상으로 V-001~V-007 점검
- **멱등성:** 동일 스크립트를 여러 번 실행해도 DB 상태 변화 없음 (태깅 검증은 별도 트랜잭션 롤백 처리)
- **출력 형식:** 각 항목별 PASS/FAIL 결과 + 검수 로그(JSON) 출력

### 4.3 주요 의존성

| 모듈 | 용도 |
|------|------|
| `app.models.ohlcv_history.OhlcvHistory` | ORM 모델 (테이블 접근) |
| `app.services.history_data_manager.HistoryDataManager` | `check_coverage()`, `get_candle_count()`, `list_symbols()` |
| `app.core.database` | AsyncSession 생성 |
| `ccxt` | V-001 API 연결성 ping |

### 4.4 출력 형식

스크립트는 실행 완료 후 아래 형식의 JSON 검수 로그를 표준 출력 또는 파일로 저장한다.

```json
{
  "ingestion_id": "<uuid>",
  "verified_at": "<ISO-8601 UTC>",
  "symbol": "SOL/USDT:USDT",
  "exchange": "binance",
  "timeframe": "1h",
  "total_expected_bars": 9600,
  "total_ingested_bars": 9587,
  "coverage_pct": 99.86,
  "gap_count": 2,
  "gap_details": [1712345600000, 1712349200000],
  "duplicate_attempted": 168,
  "duplicate_ignored": 168,
  "event_week_tagged": true,
  "high_vol_tagged": true,
  "monotonic_check": "PASS",
  "checks": {
    "V-001": "PASS",
    "V-002": "PASS",
    "V-003": "PASS",
    "V-004": "PASS",
    "V-005": "PASS",
    "V-006": "PASS",
    "V-007": "PASS"
  },
  "overall_verdict": "PASS"
}
```

---

## 5. 검수 로그 필드 정의

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `ingestion_id` | `str (UUID)` | 이 검증 실행의 고유 식별자 |
| `symbol` | `str` | 검증 대상 심볼 (예: `SOL/USDT:USDT`) |
| `exchange` | `str` | 거래소 식별자 (예: `binance`) |
| `timeframe` | `str` | 타임프레임 (예: `1h`) |
| `total_expected_bars` | `int` | 400일 기준 기대 캔들 수 (기본 9,600) |
| `total_ingested_bars` | `int` | 실제 DB 저장 캔들 수 (`get_candle_count()` 반환) |
| `coverage_pct` | `float` | 커버리지 비율 (`check_coverage()` 반환, %) |
| `gap_count` | `int` | 탐지된 갭(누락 캔들) 총 수 |
| `gap_details` | `list[int]` | 누락 캔들의 `open_time` 목록 (최대 100개, Unix ms) |
| `duplicate_attempted` | `int` | 중복 삽입 시도 캔들 수 (재삽입 테스트 기준) |
| `duplicate_ignored` | `int` | `ON CONFLICT DO NOTHING`으로 무시된 캔들 수 |
| `event_week_tagged` | `bool` | `tag_event_week()` 정상 동작 여부 |
| `high_vol_tagged` | `bool` | `tag_high_volatility()` 정상 동작 여부 |
| `monotonic_check` | `"PASS" or "FAIL"` | 타임스탬프 단조성 검증 결과 |
| `checks` | `dict[str, "PASS" or "FAIL"]` | V-001~V-007 개별 결과 |
| `overall_verdict` | `"PASS" or "FAIL" or "ABORT"` | 최종 Gate 3 판정 |
| `verified_at` | `str (ISO-8601 UTC)` | 검증 실행 시각 |

---

## 6. 실행 순서

### Step 1: Dry-run Coverage Check (API Ping + 가용 캔들 수 조회)

**목적:** 실제 수집 전 API 연결 상태와 데이터 가용 범위를 사전 확인한다.

- CCXT `exchange.ping()` 또는 `fetch_ohlcv` 1회 소량 요청으로 API 연결 확인 (V-001 일부)
- Binance에서 가장 이른 가용 타임스탬프 조회 (400일치 데이터 존재 확인)
- 기대 행수(9,600) 대비 API에서 실제 반환 가능한 최대 캔들 수 계산
- 결과: API 정상 응답 + 충분한 이력 데이터 확인 시 Step 2 진행

**중단 조건:** API 무응답 또는 이력 데이터 부족 → 실행 중단, 원인 기록

---

### Step 2: 소구간 수집 테스트 (7일)

**목적:** 전체 수집 전에 소규모 테스트로 파이프라인 end-to-end를 검증한다.

- 최근 7일 구간 (168개 캔들) 수집
- `HistoryDataManager.ingest_candles()` 호출
- `IngestionResult` 확인: `candles_fetched = 168`, `candles_inserted > 0`
- V-003 중복 테스트: 동일 구간 재수집 → `candles_skipped = 168`
- V-004 타임스탬프 단조성: 168개 캔들 순회 점검

**중단 조건:** `candles_inserted = 0` (DB 연결 불가) → 실행 중단

---

### Step 3: 전체 400일 수집

**목적:** SOL/USDT:USDT, BTC/USDT:USDT 각 9,600개 캔들을 전량 수집한다.

- 10회 배치 요청 / 심볼 (1,000개씩)
- 각 배치 후 레이트 리밋 backoff 적용 (CCXT enableRateLimit 설정)
- 실패 배치: 재시도 최대 3회, 3회 초과 시 해당 심볼 ABORT
- 수집 완료 후 `IngestionResult` 기록

**소요 예상 시간:** 심볼당 약 2~5분 (Binance 레이트 리밋 준수 기준)

---

### Step 4: 수집 후 검증 (V-001 ~ V-007 전체)

**목적:** Step 3 수집 결과를 대상으로 7개 검증 항목을 순차 실행한다.

| 실행 순서 | 검증 항목 | 사용 메서드 |
|-----------|-----------|-------------|
| 4-1 | V-002 커버리지 | `check_coverage()` → `coverage_pct` |
| 4-2 | V-003 중복 제거 | 소구간 재삽입 + `candles_skipped` 확인 |
| 4-3 | V-004 단조성 | 전체 타임스탬프 순회 |
| 4-4 | V-005 이벤트 태깅 | `tag_event_week()`, `tag_high_volatility()` |
| 4-5 | V-006 Backfill | gap 식별 → 재수집 → 재검증 |
| 4-6 | V-007 Fail-Closed | 시뮬레이션(mock) 또는 경계값 테스트 |
| 4-7 | V-001 API 최종 확인 | Step 1 결과 포함 |

---

### Step 5: Gate 3 판정

**목적:** V-001~V-007 전체 PASS 시 Gate 3 충족을 선언한다.

**판정 기준:**

```
IF V-001 == PASS
   AND V-002 == PASS (coverage_pct >= 99.0)
   AND V-003 == PASS
   AND V-004 == PASS
   AND V-005 == PASS
   AND V-006 == PASS
   AND V-007 == PASS:
     overall_verdict = "PASS"
     Gate 3: OHLCV_400D_INGESTION_PATH_VERIFIED = MET
ELSE:
     overall_verdict = "FAIL"
     Gate 3: NOT MET
```

**판정 후 조치:**
- PASS: `cr046_phase_b_gate_dashboard.md`의 Gate 3 행을 `MET`으로 업데이트
- FAIL: 실패 항목 원인 기록 후 해당 Step 재실행

---

## 7. Fail-Closed 조건 상세

이하 조건 중 하나라도 발동되면 파이프라인은 즉시 ABORT하고 부분 데이터의 백테스트 투입을 금지한다.

| 조건 | 임계값 | 발동 시 동작 |
|------|--------|-------------|
| 커버리지 부족 | `coverage_pct < 95.0%` | ABORT — 부분 데이터 사용 금지 |
| 갭 과다 | `gap_count > 24` (1일치 이상 누락) | ABORT — 연속성 보장 불가 |
| 단조성 위반 | 역전 타임스탬프 1건 이상 | ABORT — 재생 순서 신뢰 불가 |
| API 레이트 리밋 초과 | 3회 재시도 후 지속 실패 | ABORT — 수집 자체 중단 |

**ABORT 시 금지 사항:**
- 부분 수집된 데이터로 백테스트 실행 금지
- `overall_verdict = "ABORT"` 로깅 후 Gate 3 = NOT MET 유지
- 수집된 부분 데이터 삭제 여부는 운영자 수동 확인 후 결정 (`delete_symbol_data()` 사용 가능)

**Retry 정책 (레이트 리밋):**

```
재시도 1회: 대기 5초 후 재요청
재시도 2회: 대기 15초 후 재요청
재시도 3회: 대기 30초 후 재요청
3회 모두 실패: ABORT
```

---

## 8. 검증 범위 외 사항 (이 계획에서 제외)

| 항목 | 제외 이유 |
|------|-----------|
| 실시간 스트림 수집 | 백테스트 데이터 플레인은 bulk ingestion 전용 |
| ETH/USDT 검증 | CR-046 현재 상태: ETH = research only, 배포 제외 |
| 1H 외 타임프레임 | Phase B 대상 타임프레임은 1H 단일 |
| 실행 경로(주문/포지션) | `ohlcv_history` 모델은 백테스트 데이터 플레인 전용, 실행 경로 무관 |

---

## 9. 사전 조건

이 검증 계획 실행 전에 아래 조건이 충족되어야 한다.

| 조건 | 확인 방법 |
|------|-----------|
| PostgreSQL 기동 상태 | `docker-compose up -d` + DB 연결 확인 |
| `026_ohlcv_history_backtest_plane` 마이그레이션 적용 | `alembic upgrade head` |
| Binance API 키 설정 (읽기 전용) | `.env` 설정 확인 |
| CCXT 버전 호환성 | `pip show ccxt` → 적용 버전 기록 |
| `app.services.history_data_manager.HistoryDataManager` import 정상 | Python import 테스트 |

---

## 10. 관련 파일 참조

| 파일 | 역할 |
|------|------|
| `app/models/ohlcv_history.py` | ORM 모델 — `uq_ohlcv_canonical_slot` 유니크 제약 |
| `app/services/history_data_manager.py` | 수집/조회/커버리지/태깅 서비스 레이어 |
| `alembic/versions/026_ohlcv_history_backtest_plane.py` | DB 스키마 마이그레이션 |
| `docs/operations/evidence/cr046_phase_b_gate_dashboard.md` | Gate 3 충족 추적 대시보드 |
| `docs/operations/evidence/phase_b_replay_engine_design_lock.md` | Gate 2 대상 설계 잠금 문서 |
| `scripts/phase_b_ohlcv_ingestion_verify.py` | 검증 스크립트 (구현 예정) |

---

## 변경 이력

| 일시 | 변경 | 작성자 |
|------|------|--------|
| 2026-04-10 | 최초 작성 — PLAN_READY | claude-sonnet-4-6 |
