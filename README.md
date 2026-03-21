# K-Dexter AOS (Algorithmic Operating System) — K-V3

K-Dexter AOS is a self-evolving algorithmic trading operating system built in Python 3.11+.
It is designed for multi-exchange, multi-asset trading with a rigorous governance model,
full auditability, and runtime self-improvement capabilities.

## Architecture

### Governance Layers
| Layer | Role |
|-------|------|
| B1 (Constitutional) | Immutable rules, forbidden actions, mandatory constraints |
| B2 (Build Orchestration) | Strategy assembly, gate sequencing, layer wiring |
| A  (Runtime Execution) | Live trading loops, order management, state transitions |

### 30-Layer Architecture (L1~L30)
The system is decomposed into 30 functional layers covering data ingestion, signal
generation, risk management, order routing, execution, reconciliation, audit, and
self-improvement.

### Triple State Machine
- **Work State** — tracks what the system is currently doing
- **Trust State** — tracks the credibility score of each component/signal
- **Security State** — tracks threat level and access permissions at runtime

### 4 Loops
| Loop | Purpose |
|------|---------|
| Main | Core trading cycle: ingest → signal → risk → execute → reconcile |
| Self-Improvement | Backtests recent performance and proposes parameter updates |
| Evolution | Generates and validates new strategy variants via Claude API |
| Recovery | Detects anomalies, triggers safe-mode, restores consistent state |

### Gate System
Gates G-01~G-08 are mandatory pre-execution checkpoints.
Gates G-16~G-30 are advisory post-execution checkpoints.

### Trading Command Language (TCL)
TCL is the exchange-agnostic abstraction layer.  All strategies emit TCL commands
(e.g. `ORDER.BUY`, `ORDER.SELL`, `POSITION.CLOSE`) which are translated by per-exchange
adapters.

## Supported Exchanges
- Binance (crypto, REST + WebSocket)
- Bitget (crypto, USDT pairs, copy-trading)
- Upbit (KRW crypto)
- 한국투자증권 / KIS (Korean equities, REST API)
- 키움증권 / Kiwoom (Korean equities, COM/OpenAPI+)

## Quick Start
```bash
pip install -e .
python -m kdexter
```

## License
Proprietary — All rights reserved.
