"""Track C-v2 Validation — Alternative Regime Indicator Comparison.

Compares V1 (ADX/BB/ATR) vs V2 (Choppiness/DER/RealizedVol) regime
classification on historical OHLCV data.

Reports:
  - Regime distribution for each detector
  - Agreement/disagreement rate
  - Transition frequency (how often regime changes)
  - Discriminative power (entropy of regime distribution)

Usage:
    python scripts/track_c_v2_regime_validation.py [--bars 1000] [--symbol SOL/USDT]

Requires: exchange connectivity (Binance public API).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from collections import Counter
from dataclasses import dataclass, field

import numpy as np


@dataclass
class RegimeComparisonResult:
    symbol: str = ""
    timeframe: str = "1h"
    total_bars: int = 0
    v1_distribution: dict = field(default_factory=dict)
    v2_distribution: dict = field(default_factory=dict)
    agreement_rate: float = 0.0
    v1_transitions: int = 0
    v2_transitions: int = 0
    v1_entropy: float = 0.0
    v2_entropy: float = 0.0
    v2_indicator_stats: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0


def _entropy(distribution: dict) -> float:
    """Shannon entropy of regime distribution (higher = more discriminative)."""
    total = sum(distribution.values())
    if total == 0:
        return 0.0
    probs = [v / total for v in distribution.values() if v > 0]
    return -sum(p * math.log2(p) for p in probs)


def _transitions(labels: list[str]) -> int:
    """Count number of regime transitions."""
    count = 0
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            count += 1
    return count


async def run_comparison(symbol: str, bars: int) -> RegimeComparisonResult:
    from app.services.regime_detector import RegimeDetector
    from app.services.regime_detector_v2 import RegimeDetectorV2
    from exchanges.factory import ExchangeFactory

    result = RegimeComparisonResult(symbol=symbol, total_bars=bars)
    start = time.monotonic()

    # Fetch data
    print(f"[1/4] Fetching {bars} bars for {symbol} 1H...")
    exchange = ExchangeFactory.create_fresh("binance")
    raw_bars = await exchange.fetch_ohlcv(symbol, timeframe="1h", limit=bars)
    result.total_bars = len(raw_bars)
    print(f"       Fetched {result.total_bars} bars")

    if result.total_bars < 30:
        print("ERROR: insufficient data")
        return result

    # V1: batch detection
    print("[2/4] Running V1 regime detection (RegimeDetector.detect_batch)...")
    v1_detector = RegimeDetector()
    v1_results = v1_detector.detect_batch(raw_bars)
    v1_labels = [r.regime for r in v1_results]

    # V2: batch detection
    print("[3/4] Running V2 regime detection (RegimeDetectorV2.detect_batch)...")
    v2_detector = RegimeDetectorV2()
    v2_results = v2_detector.detect_batch(raw_bars)
    v2_labels = [r.regime for r in v2_results]

    # Statistics
    print("[4/4] Computing comparison statistics...")

    # Distributions
    v1_dist = dict(Counter(v1_labels))
    v2_dist = dict(Counter(v2_labels))
    result.v1_distribution = v1_dist
    result.v2_distribution = v2_dist

    # Agreement rate (matching regime labels)
    agree = sum(1 for a, b in zip(v1_labels, v2_labels) if a == b)
    result.agreement_rate = round(agree / len(v1_labels), 4) if v1_labels else 0.0

    # Transitions
    result.v1_transitions = _transitions(v1_labels)
    result.v2_transitions = _transitions(v2_labels)

    # Entropy (discriminative power)
    result.v1_entropy = round(_entropy(v1_dist), 4)
    result.v2_entropy = round(_entropy(v2_dist), 4)

    # V2 indicator statistics
    ci_vals = [r.choppiness_index for r in v2_results if r.choppiness_index > 0]
    der_vals = [r.directional_efficiency for r in v2_results if r.directional_efficiency > 0]
    rv_vals = [r.realized_volatility for r in v2_results if r.realized_volatility > 0]

    result.v2_indicator_stats = {
        "choppiness_index": {
            "mean": round(np.mean(ci_vals), 4) if ci_vals else 0,
            "std": round(np.std(ci_vals), 4) if ci_vals else 0,
            "min": round(min(ci_vals), 4) if ci_vals else 0,
            "max": round(max(ci_vals), 4) if ci_vals else 0,
        },
        "directional_efficiency": {
            "mean": round(np.mean(der_vals), 4) if der_vals else 0,
            "std": round(np.std(der_vals), 4) if der_vals else 0,
            "min": round(min(der_vals), 4) if der_vals else 0,
            "max": round(max(der_vals), 4) if der_vals else 0,
        },
        "realized_volatility": {
            "mean": round(np.mean(rv_vals), 4) if rv_vals else 0,
            "std": round(np.std(rv_vals), 4) if rv_vals else 0,
            "min": round(min(rv_vals), 4) if rv_vals else 0,
            "max": round(max(rv_vals), 4) if rv_vals else 0,
        },
    }

    result.elapsed_seconds = round(time.monotonic() - start, 2)

    # Report
    print(f"\n{'='*60}")
    print(f"  Track C-v2 Regime Comparison: {symbol}")
    print(f"{'='*60}")
    print(f"  Bars:        {result.total_bars}")
    print(f"  V1 dist:     {v1_dist}")
    print(f"  V2 dist:     {v2_dist}")
    print(f"  Agreement:   {result.agreement_rate:.1%}")
    print(f"  V1 trans:    {result.v1_transitions}")
    print(f"  V2 trans:    {result.v2_transitions}")
    print(f"  V1 entropy:  {result.v1_entropy}")
    print(f"  V2 entropy:  {result.v2_entropy}")
    print(f"  Elapsed:     {result.elapsed_seconds}s")
    print(f"{'='*60}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Track C-v2: Regime comparison")
    parser.add_argument("--bars", type=int, default=500, help="Number of bars")
    parser.add_argument("--symbol", type=str, default="SOL/USDT", help="Symbol")
    args = parser.parse_args()

    from dataclasses import asdict
    result = asyncio.run(run_comparison(args.symbol, args.bars))

    out_path = "docs/operations/evidence/track_c_v2_regime_comparison_log.json"
    with open(out_path, "w") as f:
        json.dump(asdict(result), f, indent=2, default=str)
    print(f"\nResult written to {out_path}")


if __name__ == "__main__":
    main()
