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
