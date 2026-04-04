"""
CR-039 Prerequisite (a): Collection Stability Monitor
Runs source-level health checks independently and logs results.
Does NOT modify operational code. Read-only monitoring.

Sources tested:
  - Binance (CCXT): ticker, OHLCV -- currently testnet, expected to fail
  - Alternative.me: Fear & Greed Index
  - Blockchain.com: hash rate, difficulty, tx count
  - Mempool.space: fee estimates, mempool stats
  - CoinGecko: global market cap, BTC dominance

Usage:
  python scripts/cr039_collection_monitor.py              # single check
  python scripts/cr039_collection_monitor.py --rounds 288 # 24H at 5min intervals
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

# Source URLs (same as sentiment_collector.py)
SOURCES = {
    "alternative_me": "https://api.alternative.me/fng/",
    "blockchain_com": "https://api.blockchain.info/stats",
    "mempool_space_fees": "https://mempool.space/api/v1/fees/recommended",
    "mempool_space_stats": "https://mempool.space/api/mempool",
    "coingecko_global": "https://api.coingecko.com/api/v3/global",
}


@dataclass
class SourceResult:
    source: str
    success: bool
    latency_ms: float = 0.0
    error: str | None = None
    data_keys: int = 0  # number of non-null fields returned


@dataclass
class RoundResult:
    timestamp: str
    sources: list[SourceResult] = field(default_factory=list)
    binance_success: bool = False
    binance_error: str | None = None
    binance_latency_ms: float = 0.0
    total_sources: int = 0
    successful_sources: int = 0
    quality_grade: str = "UNKNOWN"


async def check_http_source(session: aiohttp.ClientSession, name: str, url: str) -> SourceResult:
    """Check a single HTTP source."""
    start = time.monotonic()
    try:
        async with session.get(url, timeout=REQUEST_TIMEOUT) as resp:
            latency = (time.monotonic() - start) * 1000
            if resp.status == 200:
                data = await resp.json()
                keys = len(data) if isinstance(data, dict) else 1
                return SourceResult(
                    source=name, success=True, latency_ms=round(latency, 1), data_keys=keys
                )
            else:
                return SourceResult(
                    source=name,
                    success=False,
                    latency_ms=round(latency, 1),
                    error=f"HTTP {resp.status}",
                )
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return SourceResult(
            source=name,
            success=False,
            latency_ms=round(latency, 1),
            error=f"{type(e).__name__}: {str(e)[:100]}",
        )


async def check_binance_testnet() -> SourceResult:
    """Check Binance CCXT connectivity (testnet)."""
    start = time.monotonic()
    try:
        import ccxt

        ex = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
        ex.set_sandbox_mode(True)
        ticker = ex.fetch_ticker("BTC/USDT")
        latency = (time.monotonic() - start) * 1000
        return SourceResult(
            source="binance_testnet",
            success=True,
            latency_ms=round(latency, 1),
            data_keys=len(ticker) if ticker else 0,
        )
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return SourceResult(
            source="binance_testnet",
            success=False,
            latency_ms=round(latency, 1),
            error=f"{type(e).__name__}: {str(e)[:100]}",
        )


async def check_binance_mainnet_readonly() -> SourceResult:
    """Check Binance mainnet public market data (read-only, no auth).
    price_source=binance_mainnet_readonly
    source_semantics=observational_only
    not_valid_for_cr046_stage_b=true
    """
    start = time.monotonic()
    try:
        import ccxt

        # Mainnet spot, public data only -- NO sandbox, NO auth keys
        ex = ccxt.binance({"enableRateLimit": True})
        ticker = ex.fetch_ticker("BTC/USDT")
        latency = (time.monotonic() - start) * 1000
        return SourceResult(
            source="binance_mainnet_readonly",
            success=True,
            latency_ms=round(latency, 1),
            data_keys=len(ticker) if ticker else 0,
        )
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return SourceResult(
            source="binance_mainnet_readonly",
            success=False,
            latency_ms=round(latency, 1),
            error=f"{type(e).__name__}: {str(e)[:100]}",
        )


async def run_single_check() -> RoundResult:
    """Run one round of all source checks."""
    now = datetime.now(timezone.utc)
    result = RoundResult(timestamp=now.isoformat())

    # HTTP sources
    connector = aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_http_source(session, name, url) for name, url in SOURCES.items()]
        http_results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in http_results:
        if isinstance(r, Exception):
            result.sources.append(SourceResult(source="unknown", success=False, error=str(r)))
        else:
            result.sources.append(r)

    # Binance testnet (sync CCXT)
    testnet_result = await check_binance_testnet()
    result.sources.append(testnet_result)
    result.binance_success = testnet_result.success
    result.binance_error = testnet_result.error
    result.binance_latency_ms = testnet_result.latency_ms

    # Binance mainnet read-only (CR-039 observation only, NOT for CR-046 operations)
    mainnet_result = await check_binance_mainnet_readonly()
    result.sources.append(mainnet_result)

    # Compute quality grade
    result.total_sources = len(result.sources)
    result.successful_sources = sum(1 for s in result.sources if s.success)

    ratio = result.successful_sources / result.total_sources if result.total_sources > 0 else 0
    if ratio >= 1.0:
        result.quality_grade = "FULL"
    elif ratio >= 0.8:
        result.quality_grade = "PARTIAL"
    elif ratio >= 0.5:
        result.quality_grade = "DEGRADED"
    else:
        result.quality_grade = "UNUSABLE"

    return result


def print_round(r: RoundResult, round_num: int = 0):
    """Print one round result."""
    print(
        f"\n--- Round {round_num} [{r.timestamp}] Grade: {r.quality_grade} ({r.successful_sources}/{r.total_sources}) ---"
    )
    for s in r.sources:
        status = "OK" if s.success else "FAIL"
        err = f" ({s.error})" if s.error else ""
        print(f"  [{status}] {s.source:25s} {s.latency_ms:7.1f}ms{err}")


def compute_summary(rounds: list[RoundResult]) -> dict:
    """Compute aggregate summary over all rounds."""
    if not rounds:
        return {}

    source_names = set()
    for r in rounds:
        for s in r.sources:
            source_names.add(s.source)

    source_stats = {}
    for name in sorted(source_names):
        total = 0
        success = 0
        latencies = []
        for r in rounds:
            for s in r.sources:
                if s.source == name:
                    total += 1
                    if s.success:
                        success += 1
                        latencies.append(s.latency_ms)

        rate = success / total if total > 0 else 0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0

        # p95 / max latency (A's idea #2)
        sorted_lat = sorted(latencies)
        p95_lat = (
            sorted_lat[int(len(sorted_lat) * 0.95)]
            if len(sorted_lat) >= 2
            else (sorted_lat[0] if sorted_lat else 0)
        )
        max_lat = sorted_lat[-1] if sorted_lat else 0

        if rate >= 0.95:
            base_label = "STABLE"
        elif rate >= 0.80:
            base_label = "FLAKY"
        elif rate >= 0.50:
            base_label = "DEGRADED"
        else:
            base_label = "UNUSABLE"

        # A's idea #1: STABLE_OBSERVATIONAL vs STABLE_OPERATIONAL
        OBSERVATIONAL_SOURCES = {"binance_mainnet_readonly"}
        if base_label == "STABLE" and name in OBSERVATIONAL_SOURCES:
            label = "STABLE_OBSERVATIONAL"
        elif base_label == "STABLE":
            label = "STABLE_OPERATIONAL"
        else:
            label = base_label

        source_stats[name] = {
            "total_checks": total,
            "successes": success,
            "failures": total - success,
            "success_rate": round(rate, 4),
            "avg_latency_ms": round(avg_lat, 1),
            "p95_latency_ms": round(p95_lat, 1),
            "max_latency_ms": round(max_lat, 1),
            "label": label,
        }

    # Grade distribution
    grade_counts = {"FULL": 0, "PARTIAL": 0, "DEGRADED": 0, "UNUSABLE": 0, "UNKNOWN": 0}
    for r in rounds:
        grade_counts[r.quality_grade] = grade_counts.get(r.quality_grade, 0) + 1

    # Cadence analysis
    timestamps = [datetime.fromisoformat(r.timestamp) for r in rounds]
    cadence_gaps = []
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
        cadence_gaps.append(gap)

    avg_cadence = sum(cadence_gaps) / len(cadence_gaps) if cadence_gaps else 0
    max_cadence = max(cadence_gaps) if cadence_gaps else 0
    cadence_violations = sum(1 for g in cadence_gaps if g > 360)  # >6min = violation

    return {
        "total_rounds": len(rounds),
        "duration_hours": round((timestamps[-1] - timestamps[0]).total_seconds() / 3600, 2)
        if len(timestamps) > 1
        else 0,
        "source_stats": source_stats,
        "grade_distribution": grade_counts,
        "cadence": {
            "avg_seconds": round(avg_cadence, 1),
            "max_seconds": round(max_cadence, 1),
            "violations_gt_6min": cadence_violations,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="CR-039 Collection Stability Monitor")
    parser.add_argument(
        "--rounds", type=int, default=1, help="Number of rounds (1 round = 1 check)"
    )
    parser.add_argument(
        "--interval", type=int, default=300, help="Seconds between rounds (default: 300 = 5min)"
    )
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    print("=" * 60)
    print("CR-039 Prerequisite (a): Collection Stability Monitor")
    print(f"Rounds: {args.rounds}, Interval: {args.interval}s")
    print("=" * 60)

    rounds = []
    for i in range(args.rounds):
        result = asyncio.run(run_single_check())
        rounds.append(result)
        print_round(result, i + 1)

        if i < args.rounds - 1:
            print(f"  ... waiting {args.interval}s until next round ...")
            time.sleep(args.interval)

    # Summary
    summary = compute_summary(rounds)
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total rounds: {summary.get('total_rounds', 0)}")
    print(f"Duration: {summary.get('duration_hours', 0)}h")
    print(f"\nSource Health:")
    for name, stats in summary.get("source_stats", {}).items():
        print(
            f"  {name:30s} {stats['success_rate'] * 100:5.1f}% ({stats['successes']}/{stats['total_checks']}) "
            f"avg={stats['avg_latency_ms']:7.1f}ms p95={stats['p95_latency_ms']:7.1f}ms max={stats['max_latency_ms']:7.1f}ms [{stats['label']}]"
        )
    print(f"\nGrade Distribution: {summary.get('grade_distribution', {})}")
    print(
        f"Cadence: avg={summary.get('cadence', {}).get('avg_seconds', 0)}s, "
        f"max={summary.get('cadence', {}).get('max_seconds', 0)}s, "
        f"violations={summary.get('cadence', {}).get('violations_gt_6min', 0)}"
    )

    # Save
    output_path = args.output or os.path.join(
        PROJECT_ROOT, "docs", "operations", "evidence", "cr039_collection_monitor_results.json"
    )
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    output_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {"rounds": args.rounds, "interval_seconds": args.interval},
        "summary": summary,
        "rounds": [
            {
                "timestamp": r.timestamp,
                "quality_grade": r.quality_grade,
                "successful_sources": r.successful_sources,
                "total_sources": r.total_sources,
                "sources": [
                    {
                        "source": s.source,
                        "success": s.success,
                        "latency_ms": s.latency_ms,
                        "error": s.error,
                    }
                    for s in r.sources
                ],
            }
            for r in rounds
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\n[OUTPUT] {output_path}")

    return summary


if __name__ == "__main__":
    main()
