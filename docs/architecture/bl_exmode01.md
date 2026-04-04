# BL-EXMODE01 — Exchange Mode Contract

**제정일**: 2026-04-03
**근거**: CR-049 Phase 1 + Phase 2 SEALED PASS
**승인자**: A

---

## 1. 목적

거래소 어댑터의 API 접근 수준을 **설정이 아닌 정책**으로 제어한다.
운영 모드에 따라 허용/금지 API를 어댑터 레벨에서 강제하여,
우연한 auth 실패나 sandbox mode에 의존하는 허위 안전 계약을 제거한다.

## 2. Mode 정의

| Mode | 코드 | 의미 | 구현 상태 |
|------|------|------|-----------|
| **DATA_ONLY** | `ExchangeMode.DATA_ONLY` | Public market data만 허용. Private/write/futures 차단. | **구현 완료** |
| **PAPER** | `ExchangeMode.PAPER` | Public + private read + 시뮬레이션 체결. 실 주문 미생성. | 설계만 완료 |
| **LIVE** | `ExchangeMode.LIVE` | 전체 접근. A 승인 필수. | 설계만 완료 |

### 기본값

```
exchange_mode = "DATA_ONLY"
```

Config 출처: `app/core/config.py` → `settings.exchange_mode`

## 3. Mode별 허용/금지 API 매트릭스

| API | DATA_ONLY | PAPER | LIVE |
|-----|:---------:|:-----:|:----:|
| `fetch_ticker` | **O** | O | O |
| `fetch_ohlcv` | **O** | O | O |
| `fetch_balance` | **X** | O | O |
| `fetch_positions` | **X** | O | O |
| `fetch_order` | **X** | O | O |
| `cancel_order` | **X** | O | O |
| `create_order` | **X** | X | O |

**O** = 허용, **X** = `OperationNotPermitted` 예외 발생.

## 4. Task별 허용/금지 매트릭스

| Task | DATA_ONLY | PAPER | LIVE | 사유 |
|------|:---------:|:-----:|:----:|------|
| `collect_market_state` | **O** | O | O | public API only |
| `expire_signals` | **O** | O | O | DB only |
| `record_asset_snapshot` | **O** | O | O | DB only |
| `collect_sentiment_only` | **O** | O | O | external API |
| `strategy-cycle-*` (dry_run) | **O** | O | O | public data + DB |
| `ops-daily/hourly-check` | **O** | O | O | read-only check |
| `governance-monitor-*` | **O** | O | O | read-only |
| `sync_all_positions` | **X** | O | O | fetch_positions 의존 |
| `check_pending_orders` | **X** | O | O | fetch_order 의존 |
| `sol-paper-trading-hourly` | **X** | O | X | paper 전용 |

## 5. Adapter Guard 원칙

### 5.1 구현 패턴

모든 어댑터는 private/write API 진입점에서 `_require_mode()`를 호출해야 한다.

```python
async def create_order(self, ...):
    self._require_mode(ExchangeMode.LIVE, operation="create_order")
    # ... 실제 로직

async def fetch_positions(self):
    self._require_mode(ExchangeMode.PAPER, ExchangeMode.LIVE, operation="fetch_positions")
    # ... 실제 로직
```

### 5.2 적용 어댑터

| 어댑터 | 파일 | Guard 적용 |
|--------|------|-----------|
| Binance | `exchanges/binance.py` | 5 private API |
| Bitget | `exchanges/bitget.py` | 5 private API |
| UpBit | `exchanges/upbit.py` | 5 private API |
| KIS (KR) | `exchanges/kis.py` | 5 private API |
| Kiwoom | `exchanges/kiwoom.py` | 5 private API |

### 5.3 Guard 위치

Guard는 반드시 **메서드 첫 줄**에 위치해야 한다.
토큰 발급, 클라이언트 호출 등 어떤 부수 효과보다 먼저 실행.

### 5.4 예외 타입

```python
class OperationNotPermitted(RuntimeError):
    """Raised when an API call is blocked by the current exchange_mode."""
```

메시지에 포함되는 정보:
- 차단된 operation 이름
- 필요한 mode 목록
- 현재 mode
- CR-049 참조

## 6. Blocked Reason Code Registry

| 코드 | 의미 | 적용 대상 |
|------|------|-----------|
| `REQUIRES_PRIVATE_API` | private/write exchange API 의존 task가 DATA_ONLY에서 차단됨 | sync_all_positions, check_pending_orders |
| `CR046_STAGE_B_HOLD` | SOL paper trading HOLD 상태 (CR-046 선행 조건 미충족) | sol-paper-trading-hourly |
| `BINANCE_TESTNET_DEPRECATED` | Binance futures testnet 공식 폐지 | 참조용 (직접 차단 코드 아님) |

### 코드 추가 규칙

- 새 disabled task 추가 시 반드시 reason code를 등록한다.
- reason code는 `app/api/routes/ops.py`의 `_REASON_CODES` dict에 추가한다.
- reason code는 대문자 스네이크 케이스로 작성한다.
- 각 코드에 재활성 조건(re_enable_when)을 명시한다.

## 7. Re-enable 조건

| 비활성 항목 | Re-enable 조건 |
|------------|----------------|
| `sync_all_positions` | `exchange_mode` → PAPER 이상 + private API 인증 성공 확인 |
| `check_pending_orders` | `exchange_mode` → PAPER 이상 + private API 인증 성공 확인 |
| `sol-paper-trading-hourly` | CR-046 Stage B 활성화 조건 충족 (3x manual dry_run + PromotionReceipt) |
| `create_order` (API) | `exchange_mode` → LIVE + A 승인 |
| `cancel_order` (API) | `exchange_mode` → PAPER 이상 |
| `fetch_balance` (API) | `exchange_mode` → PAPER 이상 |
| `fetch_positions` (API) | `exchange_mode` → PAPER 이상 |
| `fetch_order` (API) | `exchange_mode` → PAPER 이상 |

## 8. 테스트 및 CI 강제 항목

### 8.1 필수 테스트

| 테스트 | 파일 | 검증 내용 |
|--------|------|-----------|
| Adapter guard 25점 | `tests/test_exchange_mode_guard.py` | 5 어댑터 × 5 API = 25 OperationNotPermitted |
| Ops visibility | `tests/test_ops_visibility.py` | 3 endpoint 응답 구조 + 수치 정합성 |
| Blocked operation count | `tests/test_ops_visibility.py` | blocked_api_count=5, blocked_task_count=3 |
| Reason code completeness | `tests/test_ops_visibility.py` | 모든 DISABLED task에 유효한 reason_code |
| /status exchange_mode | `tests/test_ops_visibility.py` | /status 응답에 exchange_mode 포함 |

### 8.2 CI 규칙

- 새 어댑터 추가 시 private/write API에 `_require_mode()` guard 필수.
- guard 누락 시 코드 리뷰에서 차단.
- 새 beat task 추가 시 `_BEAT_TASKS` registry에 등록 필수.
- disabled task 추가 시 reason code 등록 필수.

## 9. Deprecated 설정 처리

### `binance_testnet`

| 항목 | 현재 |
|------|------|
| 설정 위치 | `app/core/config.py` |
| 기본값 | `True` |
| 상태 | **DEPRECATED** — `exchange_mode`로 대체됨 |
| 동작 | DATA_ONLY에서 무시 (sandbox 비활성), PAPER/LIVE에서 참조 가능 |
| 제거 계획 | 후속 소규모 카드에서 완전 제거 |
| 경고 | startup 로그에 deprecation 경고 출력 |

### 경고 형식

```
WARNING: binance_testnet=True is set but exchange_mode=DATA_ONLY supersedes it.
binance_testnet is DEPRECATED by CR-049 BL-EXMODE01. Use exchange_mode instead.
```

## 10. 운영 가시화 연동

| 항목 | 엔드포인트 |
|------|-----------|
| 현재 mode 조회 | `GET /api/v1/ops/exchange-mode` |
| Task 상태 조회 | `GET /api/v1/ops/beat-tasks` |
| 차단 현황 조회 | `GET /api/v1/ops/blocked-operations` |
| 통합 상태 | `GET /status` (exchange_mode 포함) |
| Startup 로그 | mode + deprecated 경고 |

## 11. Mode 전환 정책

| 전환 | 필요 권한 | 비고 |
|------|-----------|------|
| DATA_ONLY → PAPER | Approver 승인 | Phase 3 구현 후 |
| PAPER → LIVE | **A 승인 필수** | Phase 3 구현 후 |
| LIVE → PAPER | Operator | 수동 다운그레이드 |
| LIVE → DATA_ONLY | Operator (Kill Switch) | 긴급 차단 |
| 자동 복귀 | 시스템 | 장애 시 LIVE→PAPER |

---

**BL-EXMODE01 제정 완료. CR-049 근거.**
