# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Start infrastructure (Postgres, Redis)
docker-compose up -d

# Run database migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# Start Celery worker
celery -A workers.celery_app worker --loglevel=info

# Start Celery beat scheduler
celery -A workers.celery_app beat --loglevel=info

# Monitor Celery tasks (Flower UI at localhost:5555)
# Already included in docker-compose

# Run all tests
pytest

# Run single test file
pytest tests/test_api.py -v

# Run with coverage
pytest --cov=app tests/

# Lint
ruff check .
black --check .

# Format
black .
ruff check --fix .
```

## Architecture

### Layer Structure
- `app/` - FastAPI application core
  - `api/routes/` - HTTP endpoints (orders, signals, positions, agents)
  - `core/` - Configuration, database, logging setup
  - `models/` - SQLAlchemy ORM models
  - `schemas/` - Pydantic request/response schemas
  - `services/` - Business logic layer
  - `agents/` - LLM agent implementations
- `workers/` - Celery background tasks
  - `tasks/` - Task definitions (order submission, signal validation, market sync)
- `exchanges/` - CCXT exchange wrappers (Binance, UpBit, Bitget, KIS, Kiwoom)
- `strategies/` - Trading strategy implementations
- `tests/` - pytest test suite

### Key Patterns
- **Async everywhere**: All database and exchange operations use async/await
- **Service layer**: Routes delegate to services, services use repositories
- **Exchange factory**: `ExchangeFactory.create("binance")` returns singleton exchange clients
- **Agent orchestrator**: Coordinates signal validation → risk check → execution pipeline

### Data Flow
1. Signals created via API or external source
2. `SignalValidatorAgent` validates using LLM
3. `RiskManagerAgent` checks position sizing and portfolio risk
4. Orders submitted to exchange via `OrderService`
5. Celery workers sync positions and check order status

### Database
- PostgreSQL with async SQLAlchemy
- Alembic for migrations
- Models: Order, Signal, Position, Trade

### Exchange Integration
- CCXT library for unified exchange API
- Testnet mode enabled by default (set `BINANCE_TESTNET=false` for production)
- Supports futures/perpetuals trading

### LLM Agents
- `SignalValidatorAgent`: Evaluates signal quality, returns JSON with approved/rejected
- `RiskManagerAgent`: Position sizing, portfolio risk assessment
- `AgentOrchestrator`: Chains agents for full execution pipeline
- Default provider: Anthropic Claude (configurable via `provider` param)

## CR-046 Current State (2026-04-01)

### Operational Path
- **SOL/USDT**: paper rollout GO (1st priority)
- **BTC/USDT**: guarded paper rollout only (2nd priority, latency guard mandatory)
- **ETH/USDT**: research only, excluded from deployment

### Strategy Scope
- Canonical core: SMC (pure-causal, Version B) + WaveTrend
- Strategy is regime-conditional (bear strong, sideways weak)
- No production filter adopted from Track C v1

### Sealed Results
- CG-2A: SEALED PASS (7/7 shadow days)
- CG-2B: PROVEN (CR-047, 1H timeframe)
- Phase 1 (repaint audit): PASS
- Phase 2 (OOS/WF/CV): CONDITIONAL PASS (3/5)
- Phase 3 (multi-asset): CONDITIONAL PASS (BTC/SOL positive, ETH negative)
- Phase 4 (execution realism): SEALED PASS (8/8)
- Track C v1 (regime filter): FAIL (ADX/BB/ATR non-discriminative in crypto 1H)

### Next Session Priorities
1. Phase 5a: SOL paper trading start
2. Phase 5a: BTC guarded paper trading start
3. Track B: ETH SMC+MACD branch validation
4. Track C-v2: alternative regime indicators (realized vol, choppiness, directional efficiency)

### Key Documents
- All evidence: `docs/operations/evidence/cr046_*.md`
- SOL rollout plan: `cr046_sol_paper_rollout_plan.md`
- BTC latency guard: `cr046_btc_latency_guard_checklist.md`
- Deployment readiness: `cr046_deployment_readiness_table.md`
- Three-tier judgment: `cr046_three_tier_judgment.md`
