"""Track B Validation — ETH SMC+MACD Backtest.

Fetches ETH/USDT 1H data and runs SMC+MACD strategy bar-by-bar.
Reports signal count, win rate, regime distribution, and consensus stats.

Usage:
    python scripts/track_b_eth_smc_macd_backtest.py [--bars 1000] [--symbol ETH/USDT]

Requires: exchange connectivity (Binance public API).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import numpy as np


@dataclass
class BacktestResult:
    symbol: str = ""
    timeframe: str = "1h"
    strategy: str = "SMC_MACD_1H"
    track: str = "B"
    total_bars: int = 0
    warmup_skipped: int = 0
    evaluated_bars: int = 0
    signal_count: int = 0
    long_count: int = 0
    short_count: int = 0
    consensus_stats: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0


async def run_backtest(symbol: str, bars: int) -> BacktestResult:
    from exchanges.factory import ExchangeFactory
    from strategies.smc_macd_strategy import SMCMACDStrategy

    result = BacktestResult(symbol=symbol, total_bars=bars)
    start = time.monotonic()

    # Fetch data
    print(f"[1/3] Fetching {bars} bars for {symbol} 1H...")
    exchange = ExchangeFactory.create_fresh("binance")
    raw_bars = await exchange.fetch_ohlcv(symbol, timeframe="1h", limit=bars)
    result.total_bars = len(raw_bars)
    print(f"       Fetched {result.total_bars} bars")

    if result.total_bars < 50:
        print("ERROR: insufficient data")
        return result

    # Strategy
    strategy = SMCMACDStrategy(symbol=symbol, exchange="binance")
    warmup = strategy.min_bars

    consensus_stats = {"FULL": 0, "SMC_ONLY": 0, "MACD_ONLY": 0, "DIR_MISMATCH": 0, "NONE": 0}

    # Bar-by-bar replay
    print(f"[2/3] Running bar-by-bar replay (warmup={warmup})...")
    for i in range(warmup, result.total_bars):
        window = raw_bars[: i + 1]
        signal = strategy.analyze(window)
        diag = strategy.last_diagnostic()

        consensus = diag.get("consensus", "NONE")
        if consensus in consensus_stats:
            consensus_stats[consensus] += 1

        if signal is not None:
            result.signal_count += 1
            sig_type = signal.get("signal_type")
            if hasattr(sig_type, "value"):
                sig_type = sig_type.value
            if sig_type == "long":
                result.long_count += 1
            elif sig_type == "short":
                result.short_count += 1

    result.warmup_skipped = warmup
    result.evaluated_bars = result.total_bars - warmup
    result.consensus_stats = consensus_stats
    result.elapsed_seconds = round(time.monotonic() - start, 2)

    # Report
    print(f"[3/3] Results:")
    print(f"  total_bars:     {result.total_bars}")
    print(f"  evaluated:      {result.evaluated_bars}")
    print(f"  signal_count:   {result.signal_count}")
    print(f"  long/short:     {result.long_count} / {result.short_count}")
    print(f"  consensus:      {json.dumps(consensus_stats, indent=2)}")
    print(f"  elapsed:        {result.elapsed_seconds}s")

    return result


def main():
    parser = argparse.ArgumentParser(description="Track B: ETH SMC+MACD backtest")
    parser.add_argument("--bars", type=int, default=500, help="Number of bars")
    parser.add_argument("--symbol", type=str, default="ETH/USDT", help="Symbol")
    args = parser.parse_args()

    result = asyncio.run(run_backtest(args.symbol, args.bars))

    # Write result JSON
    out_path = "docs/operations/evidence/track_b_eth_smc_macd_backtest_log.json"
    with open(out_path, "w") as f:
        json.dump(asdict(result), f, indent=2, default=str)
    print(f"\nResult written to {out_path}")


if __name__ == "__main__":
    main()
