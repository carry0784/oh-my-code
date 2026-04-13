"""Prometheus metrics for K-Dexter AOS.

Exposes operational metrics at /metrics endpoint.
All metrics are append-only counters or gauges — no state mutation.

Usage:
    from app.core.metrics import (
        REQUEST_COUNT, REQUEST_LATENCY,
        SIGNAL_COUNT, ORDER_COUNT,
        REGIME_GAUGE, GOVERNANCE_VIOLATIONS,
    )
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

# ── Application Info ─────────────────────────────────────────────────

APP_INFO = Info("kdexter", "K-Dexter AOS application metadata")

# ── HTTP Metrics ─────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "kdexter_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "kdexter_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# ── Trading Metrics ──────────────────────────────────────────────────

SIGNAL_COUNT = Counter(
    "kdexter_signals_total",
    "Total trading signals generated",
    ["symbol", "strategy", "action"],
)

ORDER_COUNT = Counter(
    "kdexter_orders_total",
    "Total orders submitted",
    ["symbol", "exchange", "side", "status"],
)

POSITION_VALUE = Gauge(
    "kdexter_position_value_usd",
    "Current position value in USD",
    ["symbol", "exchange"],
)

# ── Regime Metrics ───────────────────────────────────────────────────

REGIME_GAUGE = Gauge(
    "kdexter_regime_current",
    "Current regime state (encoded as int: 0=unknown, 1=bull, 2=bear, 3=sideways)",
    ["symbol", "detector_version"],
)

REGIME_TRANSITION_COUNT = Counter(
    "kdexter_regime_transitions_total",
    "Total regime transitions detected",
    ["symbol", "from_regime", "to_regime"],
)

# ── Governance Metrics ───────────────────────────────────────────────

GOVERNANCE_VIOLATIONS = Counter(
    "kdexter_governance_violations_total",
    "Total governance rule violations",
    ["rule_id", "severity"],
)

PPF_GATE_DECISIONS = Counter(
    "kdexter_ppf_gate_decisions_total",
    "PPF gate pass/reject decisions",
    ["symbol", "decision"],
)

# ── Infrastructure Metrics ───────────────────────────────────────────

CELERY_TASK_COUNT = Counter(
    "kdexter_celery_tasks_total",
    "Total Celery tasks executed",
    ["task_name", "status"],
)

DB_QUERY_LATENCY = Histogram(
    "kdexter_db_query_duration_seconds",
    "Database query latency",
    ["operation"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

OHLCV_COVERAGE = Gauge(
    "kdexter_ohlcv_coverage_pct",
    "OHLCV data coverage percentage",
    ["symbol", "exchange", "timeframe"],
)
