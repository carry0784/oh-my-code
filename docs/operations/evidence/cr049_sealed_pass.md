# CR-049 SEALED PASS — Exchange Mode Contract (DATA_ONLY)

**봉인일**: 2026-04-03
**판정**: Phase 1 SEALED PASS, Phase 2 SEALED PASS, Phase 3 HOLD
**운영 가시화 보강**: ACCEPTED
**Phase 3 설계 카드**: ACCEPTED
**승인자**: A

---

## 1. 문제 정의

`binance_testnet=True` 설정이 **허위 안전 계약**을 형성:

- Public API만 **우연히** 작동 (testnet.binance.vision proxy)
- Private API는 **auth 실패**로 막힘 (mainnet key ≠ testnet key)
- Futures API는 Binance testnet 공식 **deprecated** (`NotSupported`)
- `sync_all_positions`, `check_pending_orders`가 30~60초마다 반복 실패 → 운영 노이즈

**핵심**: 보호가 "정책"이 아니라 "우연한 auth 실패"에 의존하는 상태.
testnet 키를 정상 발급받으면, 또는 testnet 프록시가 변경되면, 안전 계약이 즉시 무효화됨.

## 2. 원인 분석

| 계층 | 문제 |
|------|------|
| Config | `binance_testnet=True`가 safety contract인 것처럼 오해 |
| Adapter | sandbox mode가 policy가 아니라 endpoint redirect일 뿐 |
| Beat | private API 의존 task가 auth 실패로 매번 에러 |
| 운영 | 왜 막히는지 정책적 설명 없음 — 코드/로그를 뒤져야 파악 |

## 3. 적용 범위

**Exchange Mode Contract — adapter-level policy enforcement**

| 원칙 | 적용 |
|------|------|
| `exchange_mode=DATA_ONLY` 기본값 | config.py |
| Public API만 허용, private/write/futures 차단 | 5개 어댑터 전체 |
| `_require_mode()` guard at method entry | BaseExchange mixin |
| `OperationNotPermitted` 예외 | 차단 시 명시적 에러 |
| sandbox mode 해제 (DATA_ONLY) | mainnet public endpoint 사용 |
| broken beat tasks 비활성화 | reason code 기재 |
| 운영 가시화 endpoint | 3개 ops 엔드포인트 |

## 4. Phase 1 결과 — Adapter Guard + Config

### 수정 파일 (8개)

| 분류 | 파일 | 변경 |
|------|------|------|
| Config (1) | `app/core/config.py` | `exchange_mode: str = "DATA_ONLY"`, `binance_testnet` deprecated |
| Base (1) | `exchanges/base.py` | `ExchangeMode` enum, `OperationNotPermitted`, `_require_mode()` |
| Adapters (5) | `exchanges/binance.py` | sandbox 해제 + 5 private API guard |
| | `exchanges/bitget.py` | 5 private API guard |
| | `exchanges/upbit.py` | 5 private API guard |
| | `exchanges/kis.py` | 5 private API guard |
| | `exchanges/kiwoom.py` | 5 private API guard |
| Beat (1) | `workers/celery_app.py` | `sync_all_positions`, `check_pending_orders` 비활성화 |

### 테스트 결과

| 범위 | 결과 |
|------|------|
| 5 어댑터 × 5 guarded API | **25/25 BLOCKED** |
| Binance public API (mainnet) | **OK** (price=78.84) |
| collect_market_state E2E | **OK** (200 bars, regime=ranging) |
| CR-048 baseline (9 files) | **620 passed** |
| Full suite | **4406 passed** (C15 resolved; 격리 실행 71/71 PASS; full-suite 간헐 실패는 TEST-ORDERDEP-001) |

## 5. Phase 2 결과 — DATA_ONLY 계약 도입 + Public Endpoint 정상화

### DATA_ONLY 계약 정의

| API | DATA_ONLY | PAPER | LIVE |
|-----|:---------:|:-----:|:----:|
| `fetch_ticker` | O | O | O |
| `fetch_ohlcv` | O | O | O |
| `fetch_balance` | X | O | O |
| `fetch_positions` | X | O | O |
| `fetch_order` | X | O | O |
| `cancel_order` | X | O | O |
| `create_order` | X | X | O |

### Beat Task 상태

| Task | 상태 | 사유 | CR |
|------|------|------|-----|
| `collect_market_state` (BTC/SOL) | ACTIVE | public API only | CR-038/046 |
| `expire_signals` | ACTIVE | DB only | — |
| `record_asset_snapshot` | ACTIVE | DB only | — |
| `strategy-cycle-*` (3개) | ACTIVE | dry_run=True, public data | CR-048 |
| `ops-daily/hourly-check` | ACTIVE | read-only check | S-02 |
| `governance-monitor-*` | ACTIVE | read-only | G-MON |
| `collect-sentiment-hourly` | ACTIVE | external API | CR-038 |
| `sync_all_positions` | **DISABLED** | REQUIRES_PRIVATE_API | CR-049 |
| `check_pending_orders` | **DISABLED** | REQUIRES_PRIVATE_API | CR-049 |
| `sol-paper-trading-hourly` | **DISABLED** | CR046_STAGE_B_HOLD | CR-046 |

### 데이터 품질 향상 (부수 효과)

| 지표 | testnet (이전) | mainnet public (이후) |
|------|:---:|:---:|
| OHLCV bars | 29 | **200** |
| Regime detection | always `unknown` | **`ranging`** (정상 판정) |
| Price source | testnet proxy | **mainnet 실가** |

## 6. 운영 가시화 보강 (Phase 2 후속)

### 신규 엔드포인트

| 엔드포인트 | 내용 |
|------------|------|
| `GET /api/v1/ops/exchange-mode` | 현재 모드, BL-EXMODE01 계약, API 허용/차단 매트릭스, 5개 어댑터 guard 상태 |
| `GET /api/v1/ops/beat-tasks` | 전체 beat task 상태 (ACTIVE/DISABLED), reason code, CR 참조 |
| `GET /api/v1/ops/blocked-operations` | 차단된 API + 비활성 task 통합 뷰, 재활성 조건 |

### 기존 엔드포인트 보강

| 엔드포인트 | 변경 |
|------------|------|
| `GET /status` | `exchange_mode` 필드 추가 |

### Blocked Reason Code Registry

| 코드 | 의미 |
|------|------|
| `REQUIRES_PRIVATE_API` | private/write API 의존 — DATA_ONLY에서 차단 |
| `CR046_STAGE_B_HOLD` | SOL paper trading HOLD 상태 |
| `BINANCE_TESTNET_DEPRECATED` | Binance futures testnet 공식 폐지 |

### Startup 경고

| 조건 | 로그 |
|------|------|
| 기동 시 | `exchange_mode_initialized: mode=DATA_ONLY, contract=BL-EXMODE01` |
| `binance_testnet=True` | `DEPRECATED: binance_testnet=True is superseded by exchange_mode` |

### 테스트

| 파일 | 결과 |
|------|------|
| `tests/test_ops_visibility.py` | **11/11 PASS** |
| Full suite | **4406 passed** (C15 resolved; 격리 실행 71/71 PASS; full-suite 간헐 실패는 TEST-ORDERDEP-001) |

## 7. Phase 3 설계 카드

**상태: DESIGN ONLY — 구현 HOLD**

설계 카드 위치: `docs/operations/evidence/cr049_phase3_design_card.md`

포함 내용:
- PAPER 의미 정의 (시뮬레이션 체결, 실 주문 미생성)
- Simulated fill source (PaperExecutionEngine)
- Local positions truth source (PAPER=로컬DB, LIVE=거래소)
- Pending order lifecycle (market=즉시, limit=bar체크+TTL)
- LIVE 승격 조건 7개 (A 승인 필수)
- Operator/Approver gate
- 모드 전환 감사 로그

## 8. 헌법 대조

| 조항 | 준수 |
|------|------|
| dry_run=True 유지 | O (DATA_ONLY > dry_run) |
| 실주문 경로 차단 | O (adapter guard) |
| CR-046 Stage B HOLD | O |
| LLM 본선 제외 | O |
| mainnet private auth 미사용 | O |
| PAPER/LIVE 미구현 | O |
| 운영 설명 가능성 | O (ops endpoint) |

## 9. 범위 밖 이슈 이관표

| 이슈 | 이관 대상 | 상태 |
|------|-----------|------|
| PAPER mode 구현 | CR-049 Phase 3 | HOLD (설계 카드만 완료) |
| LIVE mode 구현 | CR-049 Phase 3 | HOLD (설계 카드만 완료) |
| `binance_testnet` 완전 제거 | 후속 소규모 카드 | 미착수 (startup 경고 추가됨) |
| dashboard mode 표시 | 운영 가시화 카드 | **완료** (ops endpoint) |
| `sync_all_positions` spot 재설계 | 별도 CR | 미착수 |
| daily check exchange_mode 편입 | BL-EXMODE01 | **완료** |

## 10. 규약 승격

**BL-EXMODE01 — Exchange Mode Contract**로 승격 완료.

규약 문서 위치: `docs/architecture/bl_exmode01.md`

## 11. 미해결 리스크

| 리스크 | 완화 |
|--------|------|
| `values_callable` 누락 반복 가능성 | BL-ENUM01 패턴 문서화 (CR-048B) |
| PAPER 구현 시 범위 확대 위험 | Phase 3 설계 카드로 사전 고정 |
| `binance_testnet` 설정 잔존 | deprecated 경고 추가, 후속 제거 카드 |
| ops endpoint가 dashboard에 미편입 | 대시보드 통합은 별도 카드 |

## 12. 최종 상태 전이표

```
[이전] binance_testnet=True + auth 실패 의존 + beat 노이즈
    ↓
[Phase 1] _require_mode() guard + OperationNotPermitted + beat 비활성화
    ↓
[Phase 2] DATA_ONLY 계약 + mainnet public + 정확한 데이터
    ↓
[가시화] ops endpoint 3개 + /status 보강 + startup 경고
    ↓
[규약화] BL-EXMODE01 공식 문서
    ↓
[현재] 운영 설명 가능 상태 — 정책이 코드와 문서 양쪽에 존재
    ↓
[미래] Phase 3: PAPER/LIVE 구현 (A 승인 시)
```

---

**CR-049 Phase 1 + Phase 2: SEALED PASS / 운영 가시화: ACCEPTED / Phase 3: HOLD / 종료**
