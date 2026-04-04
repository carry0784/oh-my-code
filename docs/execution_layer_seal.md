# Execution Layer Final Seal

**Card**: C-43 (Execution Layer Seal)
**Type**: Institutional Seal
**Date**: 2026-03-25
**Baseline at seal**: 1631 passed, 0 failed

---

## 1. Purpose

The execution layer exists to **translate validated trading decisions into exchange orders** through a controlled, auditable pipeline.

- Execution converts approved signals into orders.
- Execution is subordinate to governance gates and risk management.
- Execution does **not** generate trading signals.
- Execution does **not** override governance decisions.
- Execution is bounded by position sizing and risk filters.

---

## 2. System Scope

### Modules

| Module | File | Role |
|--------|------|------|
| Order Service | `app/services/order_service.py` | Order lifecycle management |
| Signal Service | `app/services/signal_service.py` | Signal CRUD and status tracking |
| Position Service | `app/services/position_service.py` | Position state management |
| Exchange Factory | `exchanges/factory.py` | Singleton exchange client creation |
| Exchange Adapters | `exchanges/{binance,upbit,bitget,kis,kiwoom}.py` | CCXT exchange wrappers |
| Order Model | `app/models/order.py` | Order ORM |
| Trade Model | `app/models/trade.py` | Trade ORM |
| Position Model | `app/models/position.py` | Position ORM |
| Signal Model | `app/models/signal.py` | Signal ORM |
| Orders API | `app/api/routes/orders.py` | Order HTTP endpoints |
| Positions API | `app/api/routes/positions.py` | Position HTTP endpoints |
| Signals API | `app/api/routes/signals.py` | Signal HTTP endpoints |

### Explicit Non-Scope

- Signal generation or market analysis
- Governance policy definition
- Notification delivery
- Retry management
- Dashboard rendering

---

## 3. Allowed Responsibilities

1. Submit orders to exchanges via CCXT adapters
2. Track order status and lifecycle
3. Record trades from filled orders
4. Manage position state from trade data
5. Expose order/position/signal data via API
6. Use exchange factory for singleton client access
7. Enforce testnet mode by configuration

---

## 4. Forbidden Responsibilities

1. Generate trading signals autonomously
2. Override governance gate decisions
3. Bypass risk manager assessment
4. Directly mutate governance or trust state
5. Own notification or retry logic
6. Run background trading loops (belongs to engine layer)
7. Self-register autonomous execution hooks
8. Expose raw credentials or API keys

---

## 5. Execution Flow Constitution

```
signal_approved → risk_check → order_submit → exchange_fill → trade_record → position_update
```

Each step requires the previous step's approval. No step may bypass the pipeline.

---

## 6. Invariants

1. Orders are only submitted for approved signals
2. Exchange calls go through factory-created singleton clients
3. Testnet mode is default; production requires explicit configuration
4. All order/trade/position changes are persisted to database
5. Async everywhere: all DB and exchange operations use async/await
6. Service layer mediates between routes and repositories
7. No autonomous order generation

---

## 7. Amendment Rule

Changes to the execution layer require an explicit constitutional card with full review.

---

*Sealed by Card C-43.*
