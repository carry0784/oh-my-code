# CR-049 Phase 3 — PAPER / LIVE Mode Design Card

**상태**: DESIGN ONLY (구현 미착수)
**작성일**: 2026-04-03
**선행 조건**: CR-049 Phase 1+2 SEALED PASS

---

## 1. PAPER Mode 정의

### 1.1 의미

`exchange_mode=PAPER`는 **실 거래소 API를 호출하되, 실제 주문을 생성하지 않는** 모드.

| 구분 | 허용 |
|------|------|
| Public API (ticker, ohlcv) | O |
| Private read (balance, positions, orders) | O |
| Write (create_order, cancel_order) | **시뮬레이션만** |
| Futures | 거래소별 판단 |

### 1.2 Simulated Fill Source

PAPER 모드에서 `create_order()` 호출 시:

1. **실 거래소에 주문을 보내지 않는다.**
2. 대신 `PaperExecutionEngine`이 현재 시장가(fetch_ticker)를 기반으로 시뮬레이션 체결을 생성한다.
3. 시뮬레이션 체결 결과:
   - Market order → 즉시 fill (current last price + slippage model)
   - Limit order → pending, 다음 bar에서 price touch 확인 후 fill

```
create_order() 호출
    → _require_mode(PAPER, LIVE) PASS
    → if self.mode == PAPER:
        → PaperExecutionEngine.simulate_fill(symbol, side, qty, price)
        → return simulated_order_receipt
    → if self.mode == LIVE:
        → 실 거래소 API 호출
```

### 1.3 Slippage Model

| 자산 클래스 | Slippage |
|------------|----------|
| Crypto (Binance/Bitget) | 0.05% |
| KR Stock (KIS/Kiwoom) | 0.1% |
| US Stock (KIS_US) | 0.05% |

수수료도 시뮬레이션에 반영:
| 거래소 | Maker | Taker |
|--------|-------|-------|
| Binance | 0.10% | 0.10% |
| Bitget | 0.10% | 0.10% |
| UpBit | 0.05% | 0.05% |
| KIS_KR | 0.015% | 0.015% |
| KIS_US | $0.0035/share | $0.0035/share |

## 2. Local Positions Truth Source

### 2.1 원칙

PAPER 모드에서 포지션의 truth source는 **로컬 DB**이다 (거래소 아님).

| 항목 | Truth Source |
|------|-------------|
| DATA_ONLY | N/A (포지션 없음) |
| PAPER | **Local DB** (`paper_positions` 테이블) |
| LIVE | **거래소** (fetch_positions → DB 동기화) |

### 2.2 paper_positions 테이블 설계

```
paper_positions:
    id: UUID
    exchange: str           # binance, kis_kr, etc.
    symbol: str
    side: str               # long / short
    quantity: float
    entry_price: float
    entry_time: datetime
    strategy_id: str
    simulated_fill_id: UUID  # PaperExecutionEngine receipt
    current_pnl: float      # 주기적 mark-to-market
    status: str             # OPEN / CLOSED
    close_price: float | None
    close_time: datetime | None
    close_reason: str | None  # SL / TP / SIGNAL / MANUAL
```

### 2.3 포지션 라이프사이클

```
Signal LONG → create_order(PAPER) → PaperExecutionEngine.fill()
    → INSERT paper_positions (OPEN)
    → 주기적 mark-to-market (fetch_ticker로 현재가 갱신)
    → Exit signal / SL / TP 도달
    → close_order(PAPER) → PaperExecutionEngine.close_fill()
    → UPDATE paper_positions (CLOSED)
```

## 3. Pending Order Lifecycle

### 3.1 Market Order

즉시 fill. pending 상태 없음.

### 3.2 Limit Order

```
create_order(limit, price=X)
    → INSERT paper_orders (PENDING)
    → 매 bar (5분) 체크: high >= X (buy) or low <= X (sell)
    → 조건 충족 시: fill → paper_positions INSERT
    → 조건 미충족 + TTL 만료: EXPIRED
```

### 3.3 paper_orders 테이블

```
paper_orders:
    id: UUID
    exchange: str
    symbol: str
    side: str
    order_type: str         # market / limit
    quantity: float
    price: float | None
    status: str             # PENDING / FILLED / EXPIRED / CANCELLED
    created_at: datetime
    filled_at: datetime | None
    fill_price: float | None  # 실제 fill 가격 (slippage 포함)
    ttl_hours: int           # default 24
    strategy_id: str
```

## 4. LIVE 승격 조건

### 4.1 필수 선행 조건

| 조건 | 검증 방법 |
|------|-----------|
| PAPER 모드 2주 이상 운영 | paper_positions 기록 확인 |
| PAPER Sharpe > 0 | paper 포지션 성과 계산 |
| PAPER MaxDD < 15% | paper 포지션 성과 계산 |
| 전략 GUARDED_LIVE 이상 | promotion_state 확인 |
| 거래소 API key 유효성 | fetch_balance() 성공 확인 |
| dry_run=False 설정 | config 확인 |
| **A 승인** | 승인 레코드 필수 |

### 4.2 LIVE 전환 절차

```
1. Operator: LIVE 전환 요청 제출
2. 시스템: 선행 조건 7개 자동 검증
3. 검증 PASS → Approver (A) 승인 대기 큐
4. A 승인 → exchange_mode=LIVE 설정 변경
5. RuntimeStrategyLoader: LIVE 전략만 로드
6. 15분 모니터링 기간 (이상 시 자동 PAPER 복귀)
```

### 4.3 LIVE → PAPER 자동 복귀 조건

| 조건 | 행동 |
|------|------|
| 브로커 장애 | Circuit breaker → PAPER 복귀 |
| 연속 3건 주문 실패 | 자동 PAPER 복귀 |
| 일일 손실 > 3% | 자동 PAPER 복귀 |
| Kill Switch 발동 | 자동 DATA_ONLY 복귀 |

## 5. Operator / Approver Gate

### 5.1 모드 전환 권한

| 전환 | 필요 권한 |
|------|-----------|
| DATA_ONLY → PAPER | Operator 요청 + Approver 승인 |
| PAPER → LIVE | Operator 요청 + **A 승인 필수** |
| LIVE → PAPER (수동) | Operator |
| LIVE → DATA_ONLY (긴급) | Operator (Kill Switch) |
| 자동 복귀 (LIVE→PAPER) | 시스템 자동 |

### 5.2 모드 전환 감사

모든 모드 전환은 `mode_transition_log`에 기록:

```
mode_transition_log:
    id: UUID
    from_mode: str
    to_mode: str
    requested_by: str
    approved_by: str | None
    reason: str
    timestamp: datetime
    auto_triggered: bool
```

## 6. 어댑터별 구현 변경 예상

| 어댑터 | PAPER 변경 |
|--------|------------|
| binance | sandbox_mode 비활성 유지, PaperExecutionEngine 연결 |
| bitget | PaperExecutionEngine 연결 |
| upbit | PaperExecutionEngine 연결 (현물 전용) |
| kis | PaperExecutionEngine 연결, demo 모드 활용 가능 |
| kiwoom | PaperExecutionEngine 연결, demo 모드 활용 가능 |

## 7. 신규 파일 예상

| 파일 | 용도 |
|------|------|
| `app/services/paper_execution_engine.py` | 시뮬레이션 체결 엔진 |
| `app/models/paper_position.py` | paper_positions 모델 |
| `app/models/paper_order.py` | paper_orders 모델 |
| `app/models/mode_transition_log.py` | 모드 전환 감사 로그 |
| `app/services/mode_transition.py` | 모드 전환 서비스 (권한 검증) |
| `alembic/versions/019_paper_mode_tables.py` | DB 마이그레이션 |
| `tests/test_paper_execution.py` | PaperExecutionEngine 테스트 |
| `tests/test_mode_transition.py` | 모드 전환 권한 테스트 |

---

**이 카드는 설계 문서입니다. 구현은 A 승인 후 별도 CR로 진행합니다.**
