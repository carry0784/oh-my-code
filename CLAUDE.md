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
  - `ppf/` - Pattern Projection Filter (supplementary gate, see PPF section below)
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

### PPF (Pattern Projection Filter)

PPF is a supplementary gate filter, NOT an independent strategy.
It sits above the execution engine as an external orchestration wrapper.

**Core constraints (Constitution C1-C11):**
- C1: PPF never generates orders (gate-only)
- C7: Core safety modules unchanged; wrapper injection only; no direct mutation to execution safety modules
- C9: PPF standalone trade prohibited
- C10: No runtime parameter adaptation (frozen dataclass)
- C11: Novelty brake (O9=True → PPF disabled)

**Module structure** (`strategies/ppf/`, 17 tracked files):
- `ppf_gate_handler.py` - Step 5.75 wrapper gate handler (orchestrator integration)
- `constitution.py` - C1-C11 invariant checks
- `gate.py` - PPF gate evaluation logic
- `decision.py` - Decision framework
- `parameters.py` - Frozen PPF parameters (C10)
- `constants.py` - PPFState, RejectionCode enums
- `observation.py`, `interpretation.py`, `logging_schema.py` - Data pipeline
- `session_ledger.py` - LV-3 session lifecycle tracking
- `execution_ledger.py` - LV-2 execution divergence tracking
- `pattern_engine/matcher.py` - Historical pattern similarity search
- `indicators/ssl_hybrid.py`, `indicators/volume_osc.py` - Technical indicators

**Integration point** (`app/agents/orchestrator.py`):
- Step 5.75: Between SubmitLedger receipt (Step 5.5) and OrderExecutor (Step 6)
- Post-execution: LV-2/LV-3 recording path
- Handler-absent safe: all PPF paths guarded by `if self.ppf_gate_handler is not None`

**Current state** (2026-04-13):
- Implementation: BASELINE_SEALED (commit 45041f7)
- Source tracking: COMPLETE (17 files tracked)
- Test tracking: COMPLETE (7 files tracked)
- Shadow mode: Boot smoke PASS, shadow connect pending
- Production: NOT authorized

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

## Coding Principles

These four principles are derived from Andrej Karpathy's guidelines for working
with AI coding assistants (forrestchang/karpathy-claude-md). Apply them to every
task in this repository.

### 1. Think Before Coding
Don't guess. Don't hide confusion. Surface tradeoffs explicitly before writing
any code.

- State assumptions out loud before execution.
- If multiple interpretations are possible, present all of them — do not silently
  pick one.
- If a simpler approach exists, mention it. Push back if a request seems wrong.
- If something is unclear, stop and ask what is confusing rather than guessing.

### 2. Simplicity First
Write the minimum code needed to solve the problem.

- No features beyond what was requested.
- No abstractions for one-off code (no interfaces/factories for a 3-line helper).
- No unrequested flexibility, configurability, or "future-proofing".
- If 200 lines can be 50, rewrite it.
- If a senior developer would call it "complex", simplify.

### 3. Surgical Changes
Only modify what is strictly necessary. Stay inside the scope of the request.

- Every changed line must connect directly to the user's request. If it doesn't,
  don't touch it.
- When editing existing code, do not improve nearby code, comments, or
  formatting. Do not refactor working code. Preserve the existing style.
- If unrelated unused code is found, **report it — do not delete it**.
  (e.g. "This file has an unused import — should I remove it?")
- Do not create files the user did not ask for, and do not delete files for
  things you were not asked to change.
- At the end, confirm: only what was requested was changed.

### 4. Goal-Driven Execution
Define success criteria. Iterate until they are met. Convert tasks into
**verifiable** goals.

- Instead of "fix the bug" → "write a test that reproduces the bug, then make
  it pass, then confirm existing tests still pass."
- Instead of "refactor this" → "ensure tests pass before and after the refactor."
- For multi-step work, present a brief plan and include a verification step at
  each stage.
- Don't declare a task done until the verification step actually passes — not
  just because the change "looks right".

### Expected Outcome
- Fewer unnecessary changes outside the requested scope.
- Less excessive complexity that hurts readability.
- Claude asks clarifying questions *before* implementing, not after writing 200
  lines of the wrong thing.
