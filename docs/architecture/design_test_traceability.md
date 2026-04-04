# CR-048 설계 문서 ↔ 테스트 추적표

**문서 ID:** TRACE-001
**작성일:** 2026-04-04
**CR:** CR-048
**변경 등급:** L0 (문서)

---

## 추적 규칙

- 각 설계 문서의 허용/금지/승인 필요 항목 → 테스트 케이스 1:1 매핑
- 테스트는 **구현 코드 없이** 설계 계약(상수, 규칙, 매트릭스)만 검증
- 테스트 파일: `tests/test_cr048_design_contracts.py`

---

## 1. injection_constitution.md → 테스트

| # | 계약 항목 | 테스트 ID | 검증 내용 |
|---|----------|-----------|-----------|
| C-01 | 금지 브로커 목록 불변 | `test_forbidden_brokers_contains_alpaca_kiwoom_us` | ALPACA, KIWOOM_US 존재 |
| C-02 | 금지 섹터 목록 불변 | `test_forbidden_sectors_seven_items` | 7개 금지 섹터 전수 확인 |
| C-03 | 허용 브로커 자산 클래스별 | `test_allowed_brokers_per_asset_class` | CRYPTO 3개, US_STOCK 1개, KR_STOCK 2개 |
| C-04 | 금지 브로커 ∩ 허용 브로커 = ∅ | `test_forbidden_and_allowed_no_overlap` | 교집합 0 |
| C-05 | 노출 상한 값 | `test_exposure_caps_values` | 8개 상한 값 정확 |
| C-06 | Gateway 검증 항목 6단계 | `test_gateway_checks_six_steps` | 6개 체크 순서 |
| C-07 | Strategy Bank 7개 | `test_strategy_bank_seven_states` | 7 Bank 이름 |
| C-08 | Paper Shadow 최소 2주 | `test_paper_shadow_minimum_two_weeks` | 14일 이상 |

## 2. broker_matrix.md → 테스트

| # | 계약 항목 | 테스트 ID | 검증 내용 |
|---|----------|-----------|-----------|
| B-01 | 허용 브로커 6개 | `test_total_allowed_brokers_six` | 중복 제거 6개 |
| B-02 | 금지 브로커 불변 + 삭제 불가 | `test_forbidden_brokers_frozenset` | frozenset 타입 |
| B-03 | KIS_US는 US_STOCK 전용 | `test_kis_us_only_in_us_stock` | CRYPTO/KR_STOCK에 없음 |
| B-04 | 거래 시간 정의 | `test_trading_hours_defined` | 6개 브로커 전부 정의 |
| B-05 | 24/7 브로커 식별 | `test_crypto_brokers_24_7` | BINANCE, BITGET, UPBIT |
| B-06 | 금지 브로커로 등록 시도 거부 | `test_forbidden_broker_registration_rejected` | ALPACA → reject |

## 3. exclusion_baseline.md → 테스트

| # | 계약 항목 | 테스트 ID | 검증 내용 |
|---|----------|-----------|-----------|
| E-01 | 금지 섹터 7개 완전성 | `test_forbidden_sectors_complete` | 7개 전수 |
| E-02 | EXCLUDED → CORE 직행 불가 | `test_excluded_cannot_become_core` | 상태 전이 거부 |
| E-03 | EXCLUDED → WATCH 직행 불가 | `test_excluded_cannot_become_watch_without_approval` | A 승인 필요 |
| E-04 | 종목 3상태 정의 | `test_symbol_three_states` | CORE, WATCH, EXCLUDED |
| E-05 | Meme 코인 항상 EXCLUDED | `test_meme_always_excluded` | DOGE, SHIB, PEPE |
| E-06 | 저유동성 기준 ($50M) | `test_low_mcap_threshold` | 시총 < $50M → EXCLUDED |
| E-07 | ETH 특별 규칙 (CR-046) | `test_eth_operational_ban` | 분류 가능, 운영 금지 |

## 4. design_promotion_state.md → 테스트

| # | 계약 항목 | 테스트 ID | 검증 내용 |
|---|----------|-----------|-----------|
| P-01 | 10개 상태 정의 | `test_promotion_states_ten` | 10개 enum 값 |
| P-02 | 유효 전이 매트릭스 | `test_valid_transitions_matrix` | 모든 유효 전이 허용 |
| P-03 | 무효 전이 거부 | `test_invalid_transitions_rejected` | REGISTERED→LIVE 등 거부 |
| P-04 | BLOCKED 종료 상태 | `test_blocked_is_terminal` | 전이 불가 |
| P-05 | RETIRED 종료 상태 | `test_retired_is_terminal` | 전이 불가 |
| P-06 | A 승인 필요 전이 5건 | `test_approval_required_transitions` | 5건 정확 |
| P-07 | 단계 건너뛰기 금지 | `test_skip_stage_prohibited` | DRAFT→LIVE 등 불가 |
| P-08 | BACKTEST_FAIL 재시도 가능 | `test_backtest_fail_can_retry` | BACKTEST_FAIL→REGISTERED |

## 5. design_strategy_registry.md → 테스트

| # | 계약 항목 | 테스트 ID | 검증 내용 |
|---|----------|-----------|-----------|
| S-01 | Gateway 7단계 검증 순서 | `test_gateway_seven_checks_order` | 순서 보장 |
| S-02 | 금지 브로커 전략 등록 거부 | `test_strategy_with_forbidden_broker_rejected` | ALPACA 사용 전략 거부 |
| S-03 | 금지 섹터 전략 등록 거부 | `test_strategy_with_forbidden_sector_rejected` | MEME 섹터 전략 거부 |
| S-04 | FP 의존성 필수 | `test_strategy_requires_feature_pack` | FP 없이 등록 거부 |
| S-05 | 자산-브로커 호환 | `test_asset_broker_compatibility` | CRYPTO+KIS_US 거부 |

## 6. design_asset_registry.md → 테스트

| # | 계약 항목 | 테스트 ID | 검증 내용 |
|---|----------|-----------|-----------|
| A-01 | AssetClass 3종 정의 | `test_asset_class_three_types` | CRYPTO, US_STOCK, KR_STOCK |
| A-02 | SymbolStatus 3상태 정의 | `test_symbol_status_three_states` | CORE, WATCH, EXCLUDED |
| A-03 | 금지 섹터 7개 = EXCLUDED_SECTORS | `test_excluded_sectors_seven` | 7개 전수 |
| A-04 | 금지 섹터 ∩ 허용 섹터 = ∅ | `test_excluded_and_allowed_no_overlap` | 교집합 0 |
| A-05 | EXCLUDED → CORE 직행 금지 | `test_excluded_to_core_prohibited` | 상태 전이 거부 |
| A-06 | EXCLUDED → WATCH 전환 시 A 승인 필요 | `test_excluded_to_watch_requires_approval` | 자동 전환 없음 |
| A-07 | Candidate TTL 48시간 | `test_candidate_ttl_48h` | 48시간 상수 |
| A-08 | AssetClass별 허용 브로커 수 | `test_brokers_per_asset_class` | CRYPTO 3, US 1, KR 2 |
| A-09 | 심볼 정규화 규칙 3종 | `test_symbol_canonicalization` | CRYPTO/US/KR 각 패턴 |
| A-10 | ScreeningResult 5단계 구조 | `test_screening_five_stages` | stage1~stage5 필드 |
| A-11 | ETH operational_ban 규칙 | `test_eth_operational_ban` | 분류 가능, 운영 금지 |
| A-12 | Manual Override 감사 필드 | `test_manual_override_audit_fields` | override_by/reason/at |

## 7. design_screening_engine.md → 테스트

| # | 계약 항목 | 테스트 ID | 검증 내용 |
|---|----------|-----------|-----------|
| SC-01 | 5단계 파이프라인 순서 | `test_screening_five_stages_order` | Stage 1~5 순서 |
| SC-02 | Stage 1 FAIL → EXCLUDED (절대적) | `test_stage1_fail_always_excluded` | 이후 단계 무시 |
| SC-03 | Stage 2~5 FAIL → WATCH | `test_stage2_to_5_fail_is_watch` | WATCH로 분류 |
| SC-04 | 5단계 전부 PASS → CORE | `test_all_stages_pass_is_core` | CORE 진입 |
| SC-05 | Candidate TTL 48시간 | `test_candidate_ttl_48h_screening` | CORE 시 TTL 설정 |
| SC-06 | Regime 전환 시 TTL 즉시 만료 | `test_regime_change_expires_ttl` | 즉시 만료 |
| SC-07 | Stage 1 금지 섹터 = Exclusion Baseline 7개 | `test_stage1_matches_exclusion_baseline` | 일치 |
| SC-08 | Stage 2 유동성 기준 시장별 분리 | `test_stage2_thresholds_per_market` | 3시장 각각 |
| SC-09 | Stage 3 ATR/ADX/MA 기준값 | `test_stage3_technical_thresholds` | ATR 1~20%, ADX>15 |
| SC-10 | Stage 5 최소 500bars | `test_stage5_min_bars_500` | 500 bars 상수 |
| SC-11 | ScreeningResult append-only | `test_screening_result_append_only` | 수정/삭제 불가 |
| SC-12 | 스크리닝 실행 주기 정의 | `test_screening_schedule_defined` | 1h/1d/regime/manual |

---

## 테스트 통계

| 문서 | 테스트 수 |
|------|:---------:|
| injection_constitution.md | 8 |
| broker_matrix.md | 6 |
| exclusion_baseline.md | 7 |
| design_promotion_state.md | 8 |
| design_strategy_registry.md | 5 |
| design_asset_registry.md | 12 |
| design_screening_engine.md | 12 |
| **합계** | **58** |

---

```
Design-Test Traceability v1.1
Date: 2026-04-04
CR: CR-048
Phase 2+3A traceability added
```
