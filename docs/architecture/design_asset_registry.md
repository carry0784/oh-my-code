# Asset Registry 설계 카드

**문서 ID:** DESIGN-P2-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048 Phase 2 (Asset Registry + Symbol Registry)
**Status:** **DESIGN_ONLY**
**변경 등급:** L0 (설계 문서)

---

## 1. 해석 및 요약

### 목적

종목(Symbol)의 메타데이터, 3상태(CORE/WATCH/EXCLUDED) 관리, 자산 클래스별 분류 체계를 정의하는 레지스트리.
Phase 1 Registry(Indicator/FeaturePack/Strategy)가 "무엇을 실행할 것인가"를 다룬다면,
Asset Registry는 "어떤 종목에 실행할 것인가"를 다룬다.

### 4대 분류 체계

| 체계 | 정의 | 예시 |
|------|------|------|
| **AssetClass** | 시장 대분류 | CRYPTO, US_STOCK, KR_STOCK |
| **AssetSector** | 업종/섹터 | LAYER1, DEFI, TECH, SEMICONDUCTOR |
| **AssetTheme** | 투자 테마 | AI_SEMICONDUCTOR, CLOUD, EV |
| **SymbolStatus** | 종목 운영 상태 | CORE, WATCH, EXCLUDED |

### Symbol 정의

| 속성 | 설명 | 예시 |
|------|------|------|
| **symbol** | 정규화된 심볼 | `SOL/USDT`, `AAPL`, `005930` |
| **name** | 종목 이름 | `Solana`, `Apple Inc.`, `삼성전자` |
| **asset_class** | 자산 클래스 | `CRYPTO` |
| **sector** | 업종 | `LAYER1` |
| **theme** | 투자 테마 | `AI_SEMICONDUCTOR` |
| **exchanges** | 허용 브로커 (JSON) | `["BINANCE", "BITGET"]` |
| **status** | 3상태 | `CORE`, `WATCH`, `EXCLUDED` |
| **screening_score** | 스크리닝 점수 | `0.0 ~ 1.0` |
| **candidate_expire_at** | 후보 TTL 만료 시각 | `2026-04-06T00:00:00Z` |
| **paper_allowed** | Paper 운용 가능 여부 | `True` (CORE만) |
| **live_allowed** | Live 운용 가능 여부 | `True` (CORE만) |

### 종목 3상태 관리

| 상태 | 의미 | 진입 조건 | 허용 행위 | 탈출 조건 |
|------|------|-----------|-----------|-----------|
| **CORE** | 적격 종목, 실전 운영 대상 | 5단계 스크리닝 전부 PASS | 분석, 백테스트, Paper, Live | 스크리닝 재심사 FAIL → WATCH |
| **WATCH** | 관찰 대상, 운영 미허용 | 일부 스크리닝 통과 또는 CORE 탈락 | 분석, 백테스트만 | 스크리닝 전부 PASS → CORE |
| **EXCLUDED** | 완전 제외 | Exclusion Baseline 해당 | 분류만 | A 승인 + 기준 변경 시에만 |

### 핵심 규칙

| 규칙 | 내용 |
|------|------|
| EXCLUDED → CORE 직행 금지 | 반드시 기준 변경(A 승인) + 재심사 경유 |
| EXCLUDED → WATCH 전환 | A 승인 필수, 자동 전환 없음 |
| Candidate TTL | CORE 진입 후 48시간 만료, regime 전환 시 즉시 만료 |
| Broker Policy 연동 | Symbol.exchanges는 broker_matrix.md 허용 목록에서만 선택 |
| 금지 섹터 종목 | Exclusion Baseline 7개 섹터 → 항상 EXCLUDED |
| ETH 특별 규칙 | 분류 가능, operational_ban=True (CR-046) |

### 심볼 정규화

| 자산 클래스 | 정규화 규칙 | 예시 |
|------------|------------|------|
| CRYPTO | `BASE/QUOTE` | `SOL/USDT`, `BTC/USDT` |
| US_STOCK | 대문자 티커 | `AAPL`, `NVDA` |
| KR_STOCK | 6자리 제로패딩 | `005930`, `000660` |

---

## 2. 장점 / 단점

### 장점

| 장점 | 설명 |
|------|------|
| **3상태 원천 관리** | CORE/WATCH/EXCLUDED가 코드 레벨에서 강제되어 금지 종목 운용 차단 |
| **Exclusion Baseline 자동 연동** | 금지 섹터 종목은 등록 시점부터 EXCLUDED 고정 |
| **Candidate TTL** | 스크리닝 결과 유효 기간을 강제하여 stale 후보 방지 |
| **Broker Policy 일관성** | Symbol↔Broker 매핑이 broker_matrix.md와 항상 일치 |
| **감사 추적** | ScreeningResult 테이블이 모든 스크리닝 이력을 append-only로 기록 |
| **Manual Override 기록** | 수동 상태 변경 시 override_by + override_reason + override_at 필수 기록 |

### 단점

| 단점 | 완화 방안 |
|------|-----------|
| 종목 수 증가 시 스크리닝 부하 | 1단계(Exclusion Filter)에서 대량 조기 제거 |
| EXCLUDED ↔ WATCH 전환에 A 승인 필요 | 의도적 설계 — 안전 우선 |
| TTL 만료 시 재심사 지연 가능 | 만료 임박 알림 + 자동 재심사 enqueue |

---

## 3. 이유 / 근거

### 근거 1 — 기존 구현(app/models/asset.py)과의 관계

현재 `app/models/asset.py`에 Symbol, ScreeningResult 모델이 이미 구현되어 있음.
이 설계 카드는 기존 구현의 설계 의도를 문서화하고, Phase 2 확장 방향을 정의.

기존 모델 현황:

| 모델 | 상태 | 비고 |
|------|------|------|
| Symbol | 구현됨 | 3상태, screening_score, TTL, paper/live 플래그 |
| ScreeningResult | 구현됨 | 5단계 결과, append-only |
| AssetSector enum | 구현됨 | 허용 + 제외 섹터 정의 |
| AssetTheme enum | 구현됨 | 8개 투자 테마 |
| SymbolStatus enum | 구현됨 | CORE/WATCH/EXCLUDED |
| canonicalize_symbol() | 구현됨 | 심볼 정규화 헬퍼 |

### 근거 2 — Exclusion Baseline과의 강제 연동

`exclusion_baseline.md`에서 정의한 7개 금지 섹터:

| 금지 섹터 | 시장 |
|-----------|------|
| MEME | CRYPTO |
| LOW_LIQUIDITY_NEW_TOKEN | CRYPTO |
| GAMEFI | CRYPTO |
| HIGH_VALUATION_PURE_SW | US_STOCK |
| WEAK_CONSUMER_BETA | US_STOCK |
| OIL_SENSITIVE | KR_STOCK |
| LOW_LIQUIDITY_THEME | KR_STOCK |

이 7개 섹터에 해당하는 종목은 `EXCLUDED_SECTORS` frozenset으로 코드에서 강제.
`app/core/constitution.py`의 `FORBIDDEN_SECTOR_VALUES`에서 원천 제공.

### 근거 3 — Broker Matrix와의 일관성

Symbol.exchanges 필드는 broker_matrix.md 허용 목록에서만 선택 가능.
자산 클래스별 허용 브로커:

| AssetClass | 허용 브로커 |
|------------|------------|
| CRYPTO | BINANCE, BITGET, UPBIT |
| US_STOCK | KIS_US |
| KR_STOCK | KIS_KR, KIWOOM_KR |

금지 브로커(ALPACA, KIWOOM_US)가 Symbol.exchanges에 포함되면 Injection Gateway에서 거부.

### 근거 4 — Candidate TTL의 필요성

| 항목 | 값 | 근거 |
|------|-----|------|
| 기본 TTL | 48시간 | 시장 상황은 빠르게 변화 — 2일 전 적격이 오늘 부적격일 수 있음 |
| Regime 전환 시 | 즉시 만료 | 시장 체제 변화 시 기존 스크리닝 결과 신뢰 불가 |
| 만료 후 행동 | CORE → WATCH 강등, 재심사 enqueue | 만료 종목에 대한 analyze 거부 |

---

## 4. 실현 / 구현 대책

### 기존 구현 활용

| 항목 | 파일 | 상태 |
|------|------|------|
| Symbol 모델 | `app/models/asset.py` | 구현됨 |
| ScreeningResult 모델 | `app/models/asset.py` | 구현됨 |
| Asset Schema | `app/schemas/asset_schema.py` | 구현됨 |
| Asset Service | `app/services/asset_service.py` | 구현됨 |
| Alembic | `008_asset_tables.py` | 구현됨 |

### Phase 2 확장 필요 항목 (L3 승인 필요)

| 항목 | 설명 | 등급 |
|------|------|------|
| Symbol-Broker 교차 검증 | Symbol.exchanges ∩ FORBIDDEN_BROKERS = ∅ 강제 | L3 |
| TTL 자동 만료 로직 | candidate_expire_at 기반 자동 WATCH 강등 | L3 |
| Regime 전환 시 TTL 일괄 만료 | RegimeDetector 이벤트 연동 | L3 |
| SymbolScreener 5단계 파이프라인 | design_screening_engine.md 참조 | L3 |
| Universe Manager | CORE 종목만 실행 대상으로 선택 | L3 |

---

## 5. 실행방법

### 현재 단계 (L0/L1)

1. 본 설계 카드 확정
2. 계약 테스트 작성 (기존 asset.py 상수 기반)
3. design_test_traceability.md 확장

### 다음 단계 (L3 승인 후)

1. Symbol-Broker 교차 검증 서비스
2. TTL 자동 만료 로직
3. SymbolScreener 파이프라인 (design_screening_engine.md 의존)

---

## 6. 더 좋은 아이디어

### 종목 상태 전이 감사 강화

현재 ScreeningResult가 스크리닝 이력을 기록하지만,
**상태 전이 자체**(WATCH→CORE, CORE→WATCH, manual override 등)를 별도 이벤트로 기록하면
PromotionEvent와 유사한 추적이 가능합니다.

```
SymbolStatusEvent {
    symbol_id, from_status, to_status,
    reason, triggered_by,
    screening_result_id (nullable),
    created_at
}
```

이는 Phase 2 L3 구현 시 검토 가능.

---

## L3 선행조건 체크리스트

| # | 조건 | 충족 여부 |
|---|------|:---------:|
| 1 | 본 설계 카드 A 승인 | |
| 2 | 계약 테스트 PASS | |
| 3 | design_test_traceability.md Phase 2 항목 반영 | |
| 4 | design_screening_engine.md 확정 (Phase 3A 의존) | |
| 5 | broker_matrix.md 일관성 확인 | |
| 6 | exclusion_baseline.md 7섹터 계약 테스트 PASS | |
| 7 | 기존 asset.py 모델과 설계 카드 정합성 확인 | |
| 8 | L3 범위 확장 제안서 A 승인 | |

## 구현 착수 불가 항목

| 항목 | 사유 |
|------|------|
| Symbol-Broker 교차 검증 서비스 | L3 서비스 로직 |
| TTL 자동 만료 Celery task | L3 실행 로직 |
| Universe Manager | L3 실행 로직 |
| SymbolScreener 파이프라인 | L3 서비스 로직 (Phase 3A 의존) |
| write API (종목 등록/수정) | write path 금지 |

## 문서-테스트 추적 항목 (Phase 2)

| # | 계약 항목 | 테스트 ID |
|---|----------|-----------|
| A-01 | AssetClass 3종 정의 | `test_asset_class_three_types` |
| A-02 | SymbolStatus 3상태 정의 | `test_symbol_status_three_states` |
| A-03 | 금지 섹터 7개 = EXCLUDED_SECTORS | `test_excluded_sectors_seven` |
| A-04 | 금지 섹터 ∩ 허용 섹터 = ∅ | `test_excluded_and_allowed_no_overlap` |
| A-05 | EXCLUDED → CORE 직행 금지 | `test_excluded_to_core_prohibited` |
| A-06 | EXCLUDED → WATCH 전환 시 A 승인 필요 | `test_excluded_to_watch_requires_approval` |
| A-07 | Candidate TTL 48시간 | `test_candidate_ttl_48h` |
| A-08 | AssetClass별 허용 브로커 수 | `test_brokers_per_asset_class` |
| A-09 | 심볼 정규화 규칙 3종 | `test_symbol_canonicalization` |
| A-10 | ScreeningResult 5단계 구조 | `test_screening_five_stages` |
| A-11 | ETH operational_ban 규칙 | `test_eth_operational_ban` |
| A-12 | Manual Override 감사 필드 | `test_manual_override_audit_fields` |

---

```
Design Card: Asset Registry v1.0
Document ID: DESIGN-P2-001
Date: 2026-04-04
CR: CR-048 Phase 2
Status: DESIGN_ONLY
```
