# AI Trading System

Production-grade crypto trading automation with LLM-powered signal validation and execution.

## Stack

- **API**: FastAPI + Uvicorn
- **Database**: PostgreSQL + SQLAlchemy (async)
- **Queue**: Redis + Celery
- **Exchanges**: Binance, OKX via CCXT
- **LLM**: Anthropic Claude / OpenAI GPT-4

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env with your API keys

# 4. Start infrastructure
docker-compose up -d

# 5. Run migrations
alembic upgrade head

# 6. Start API server
uvicorn app.main:app --reload

# 7. Start Celery worker (separate terminal)
celery -A workers.celery_app worker --loglevel=info

# 8. Start Celery beat (separate terminal, for scheduled tasks)
celery -A workers.celery_app beat --loglevel=info
```

## API Endpoints

- `GET /health` - Health check
- `POST /api/v1/orders/` - Create order
- `GET /api/v1/orders/` - List orders
- `POST /api/v1/signals/` - Create signal
- `POST /api/v1/signals/{id}/validate` - Validate signal with LLM
- `GET /api/v1/positions/` - List positions
- `POST /api/v1/agents/analyze` - Run agent analysis
- `POST /api/v1/agents/execute` - Execute trading pipeline

## Testing

```bash
pytest
pytest tests/test_api.py -v
pytest --cov=app tests/
```

## Architecture

```
Signal Source → Signal Service → LLM Validator → Risk Manager → Order Execution
                     ↓                                              ↓
                 Database                                      Exchange API
                     ↑                                              ↓
              Celery Workers ←────── Position Sync ←───────── Market Data
```
