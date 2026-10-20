"""
TimescaleDB Hypertable Models — Card A (Data Lake)
Five time-series tables partitioned by time for high-throughput market data storage.

Design constraints:
  - Composite primary key (time + symbol/source) — critical for hypertable chunk pruning
  - `time` column is TIMESTAMPTZ (DateTime with timezone=True) — TimescaleDB partition key
  - All tables include `exchange` for multi-exchange support
  - Parallel to (not replacing) ohlcv_history — that table remains for backtest replay
  - NOT connected to execution/runtime path; data ingestion only

Hypertable conversion is handled in migration 029_timescaledb_hypertables.py.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, JSON, String, UniqueConstraint

from app.core.database import Base


class OhlcvHyper(Base):
    """High-frequency OHLCV candle store — TimescaleDB hypertable, chunk interval 7 days.

    Partition key: time (TIMESTAMPTZ).
    Optimised for range queries on (exchange, symbol, timeframe, time).
    Parallel to ohlcv_history; this table is the live/streaming data plane.
    """

    __tablename__ = "ohlcv_hyper"

    # ── Composite primary key ──────────────────────────────────────────
    time: datetime = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol: str = Column(String(20), primary_key=True, nullable=False)

    # ── Identity ──────────────────────────────────────────────────────
    exchange: str = Column(String(50), nullable=False)
    timeframe: str = Column(String(10), nullable=False)  # 1m, 5m, 15m, 1h, 4h, 1d

    # ── OHLCV ─────────────────────────────────────────────────────────
    open: float = Column(Float, nullable=False)
    high: float = Column(Float, nullable=False)
    low: float = Column(Float, nullable=False)
    close: float = Column(Float, nullable=False)
    volume: float = Column(Float, nullable=False)

    # ── Constraints & indexes ─────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "symbol",
            "timeframe",
            "time",
            name="uq_ohlcv_hyper_slot",
        ),
        Index("ix_ohlcv_hyper_lookup", "exchange", "symbol", "timeframe", "time"),
    )


class FundingRateHyper(Base):
    """Perpetual funding rate time-series — TimescaleDB hypertable, chunk interval 30 days.

    Partition key: time (TIMESTAMPTZ).
    One row per (exchange, symbol, time) funding snapshot.
    """

    __tablename__ = "funding_rate_hyper"

    # ── Composite primary key ──────────────────────────────────────────
    time: datetime = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol: str = Column(String(20), primary_key=True, nullable=False)

    # ── Identity ──────────────────────────────────────────────────────
    exchange: str = Column(String(50), nullable=False)

    # ── Funding data ──────────────────────────────────────────────────
    funding_rate: float = Column(Float, nullable=False)
    mark_price: float | None = Column(Float, nullable=True)
    index_price: float | None = Column(Float, nullable=True)
    next_funding_time: datetime | None = Column(DateTime(timezone=True), nullable=True)

    # ── Constraints & indexes ─────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "symbol",
            "time",
            name="uq_funding_rate_hyper_slot",
        ),
        Index("ix_funding_rate_hyper_lookup", "exchange", "symbol", "time"),
    )


class OpenInterestHyper(Base):
    """Open interest time-series — TimescaleDB hypertable, chunk interval 30 days.

    Partition key: time (TIMESTAMPTZ).
    One row per (exchange, symbol, time) OI snapshot.
    """

    __tablename__ = "open_interest_hyper"

    # ── Composite primary key ──────────────────────────────────────────
    time: datetime = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol: str = Column(String(20), primary_key=True, nullable=False)

    # ── Identity ──────────────────────────────────────────────────────
    exchange: str = Column(String(50), nullable=False)

    # ── OI data ───────────────────────────────────────────────────────
    open_interest: float = Column(Float, nullable=False)
    open_interest_value: float | None = Column(Float, nullable=True)  # in USD notional

    # ── Constraints & indexes ─────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "symbol",
            "time",
            name="uq_open_interest_hyper_slot",
        ),
        Index("ix_open_interest_hyper_lookup", "exchange", "symbol", "time"),
    )


class OrderbookSnapshotHyper(Base):
    """Level-2 orderbook snapshot — TimescaleDB hypertable, chunk interval 30 days.

    Partition key: time (TIMESTAMPTZ).
    Top-20 bid/ask levels stored as JSON arrays for compactness.
    bid_prices / ask_prices: list of floats (price levels, best-first).
    bid_volumes / ask_volumes: list of floats (corresponding quantities).
    """

    __tablename__ = "orderbook_snapshot_hyper"

    # ── Composite primary key ──────────────────────────────────────────
    time: datetime = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol: str = Column(String(20), primary_key=True, nullable=False)

    # ── Identity ──────────────────────────────────────────────────────
    exchange: str = Column(String(50), nullable=False)

    # ── Top-20 orderbook levels (arrays) ─────────────────────────────
    bid_prices: list = Column(JSON, nullable=False)    # [p1, p2, ..., p20]
    bid_volumes: list = Column(JSON, nullable=False)   # [v1, v2, ..., v20]
    ask_prices: list = Column(JSON, nullable=False)    # [p1, p2, ..., p20]
    ask_volumes: list = Column(JSON, nullable=False)   # [v1, v2, ..., v20]

    # ── Derived metrics ───────────────────────────────────────────────
    spread: float = Column(Float, nullable=False)      # ask[0] - bid[0]
    mid_price: float = Column(Float, nullable=False)   # (ask[0] + bid[0]) / 2

    # ── Constraints & indexes ─────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "symbol",
            "time",
            name="uq_orderbook_snapshot_hyper_slot",
        ),
        Index("ix_orderbook_snapshot_hyper_lookup", "exchange", "symbol", "time"),
    )


class SentimentHyper(Base):
    """Market sentiment metric time-series — TimescaleDB hypertable, chunk interval 30 days.

    Partition key: time (TIMESTAMPTZ).
    Flexible schema: one row per (source, symbol, metric_name, time).
    symbol is nullable — some sentiment metrics are global (e.g. crypto Fear & Greed index).
    raw_json stores the original API payload for future re-parsing without data loss.
    """

    __tablename__ = "sentiment_hyper"

    # ── Composite primary key ──────────────────────────────────────────
    time: datetime = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    # symbol nullable but still part of PK (NULL == global metric)
    symbol: str | None = Column(String(20), primary_key=True, nullable=True)

    # ── Identity ──────────────────────────────────────────────────────
    source: str = Column(String(50), nullable=False)        # e.g. "alternative_me", "coinglass"
    metric_name: str = Column(String(100), nullable=False)  # e.g. "fear_greed_index"

    # ── Value ─────────────────────────────────────────────────────────
    metric_value: float = Column(Float, nullable=False)
    raw_json: dict | None = Column(JSON, nullable=True)     # original API payload

    # ── Constraints & indexes ─────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "source",
            "symbol",
            "metric_name",
            "time",
            name="uq_sentiment_hyper_slot",
        ),
        Index("ix_sentiment_hyper_lookup", "source", "symbol", "metric_name", "time"),
    )
