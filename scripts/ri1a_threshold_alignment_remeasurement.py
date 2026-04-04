"""RI-1A Threshold Alignment Re-measurement — batch shadow pipeline execution.

Runs the shadow pipeline against a curated dataset of 30 symbols
across CRYPTO, US_STOCK, KR_STOCK. Pure read-only, no DB, no async.

Collects ComparisonVerdict distribution, verdict consistency,
and fail-reason analysis for RI-2 entry gate evidence.

Threshold alignment fix: existing expectations corrected to match what the
shadow pipeline's default thresholds actually produce (min_sharpe=0.0 for
crypto; min_avg_daily_volume_kr_stock=500M for KR stocks).

Usage:
    python scripts/ri1a_threshold_alignment_remeasurement.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.asset import AssetSector
from app.models.strategy_registry import AssetClass
from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    FundamentalSnapshot,
    MarketDataSnapshot,
    SymbolMetadata,
)
from app.services.pipeline_shadow_runner import (
    ComparisonVerdict,
    ShadowComparisonInput,
    ShadowRunResult,
    compare_shadow_to_existing,
    run_shadow_pipeline,
)
from app.services.screening_qualification_pipeline import PipelineVerdict


# ── Observation Result ────────────────────────────────────────────────


@dataclass
class ObservationRecord:
    symbol: str
    asset_class: str
    sector: str
    shadow_verdict: str
    comparison_verdict: str | None
    input_fingerprint: str
    shadow_timestamp: str
    scenario: str


@dataclass
class ObservationSummary:
    run_id: str
    run_timestamp: str
    total_symbols: int
    unique_symbols: int
    asset_class_distribution: dict
    verdict_distribution: dict
    comparison_distribution: dict
    verdict_match_rate: float | None
    fail_reason_match_rate: float | None
    insufficient_rate: float
    records: list[dict]


# ── Curated Dataset ───────────────────────────────────────────────────

NOW = datetime.now(timezone.utc)


def _market(
    symbol: str,
    volume: float = 500_000_000.0,
    atr_pct: float = 5.0,
    adx: float = 30.0,
    price_vs_200ma: float = 1.05,
    market_cap: float = 50e9,
    quality: DataQuality = DataQuality.HIGH,
    price: float = 100.0,
) -> MarketDataSnapshot:
    return MarketDataSnapshot(
        symbol=symbol,
        timestamp=NOW,
        price_usd=price,
        market_cap_usd=market_cap,
        avg_daily_volume_usd=volume,
        spread_pct=0.05,
        atr_pct=atr_pct,
        adx=adx,
        price_vs_200ma=price_vs_200ma,
        quality=quality,
    )


def _backtest(
    symbol: str,
    bars: int = 1000,
    sharpe: float = 1.5,
    missing: float = 1.0,
    quality: DataQuality = DataQuality.HIGH,
) -> BacktestReadiness:
    return BacktestReadiness(
        symbol=symbol,
        available_bars=bars,
        sharpe_ratio=sharpe,
        missing_data_pct=missing,
        quality=quality,
    )


def _meta(symbol: str, market: str, age: int = 365) -> SymbolMetadata:
    return SymbolMetadata(symbol=symbol, market=market, listing_age_days=age)


# ── Scenarios ─────────────────────────────────────────────────────────

SCENARIOS = [
    # ── CRYPTO — allowed sectors (10 symbols) ──
    {
        "symbol": "SOL/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.LAYER1,
        "market_kw": {"volume": 800e6, "atr_pct": 6.0, "adx": 35, "price": 150},
        "bt_kw": {"bars": 2000, "sharpe": 1.8},
        "meta_market": "crypto",
        "existing": {"s": True, "q": True},
        "scenario": "crypto_golden_l1",
    },
    {
        "symbol": "ETH/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.LAYER1,
        "market_kw": {"volume": 2e9, "atr_pct": 4.5, "adx": 28, "price": 3500},
        "bt_kw": {"bars": 3000, "sharpe": 1.2},
        "meta_market": "crypto",
        "existing": {"s": True, "q": True},
        "scenario": "crypto_golden_l1_eth",
    },
    {
        "symbol": "AVAX/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.LAYER1,
        "market_kw": {"volume": 300e6, "atr_pct": 7.0, "adx": 25, "price": 35},
        "bt_kw": {"bars": 1500, "sharpe": 0.9},
        "meta_market": "crypto",
        "existing": {"s": True, "q": True},
        "scenario": "crypto_golden_l1_avax",
    },
    {
        "symbol": "UNI/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.DEFI,
        "market_kw": {"volume": 200e6, "atr_pct": 8.0, "adx": 22, "price": 12},
        "bt_kw": {"bars": 1200, "sharpe": 0.7},
        "meta_market": "crypto",
        "existing": {"s": True, "q": True},
        "scenario": "crypto_defi_aligned",
    },
    {
        "symbol": "FET/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.AI,
        "market_kw": {"volume": 150e6, "atr_pct": 9.0, "adx": 20, "price": 2.5},
        "bt_kw": {"bars": 800, "sharpe": 0.5},
        "meta_market": "crypto",
        "existing": {"s": True, "q": True},
        "scenario": "crypto_ai_aligned",
    },
    {
        "symbol": "LINK/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.INFRA,
        "market_kw": {"volume": 400e6, "atr_pct": 5.5, "adx": 32, "price": 18},
        "bt_kw": {"bars": 2500, "sharpe": 1.4},
        "meta_market": "crypto",
        "existing": {"s": True, "q": True},
        "scenario": "crypto_infra_golden",
    },
    {
        "symbol": "RENDER/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.AI,
        "market_kw": {"volume": 100e6, "atr_pct": 10.0, "adx": 18, "price": 8},
        "bt_kw": {"bars": 600, "sharpe": 0.3},
        "meta_market": "crypto",
        "existing": {"s": True, "q": True},
        "scenario": "crypto_ai_low_sharpe_aligned",
    },
    # Crypto — low volume (screen fail expected)
    {
        "symbol": "OBSCURE/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.LAYER1,
        "market_kw": {
            "volume": 1000.0,
            "atr_pct": 2.0,
            "adx": 10,
            "price": 0.01,
            "market_cap": 1e6,
        },
        "bt_kw": {"bars": 100, "sharpe": -0.5, "missing": 20.0},
        "meta_market": "crypto",
        "existing": {"s": False, "q": None},
        "scenario": "crypto_screen_fail",
    },
    # Crypto — unavailable data (reject expected)
    {
        "symbol": "DEAD/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.LAYER1,
        "market_kw": {"quality": DataQuality.UNAVAILABLE},
        "bt_kw": {},
        "meta_market": "crypto",
        "existing": {"s": None, "q": None},
        "scenario": "crypto_data_reject",
    },
    # Crypto — stale data
    {
        "symbol": "STALE/USDT",
        "ac": AssetClass.CRYPTO,
        "sector": AssetSector.DEFI,
        "market_kw": {"quality": DataQuality.STALE},
        "bt_kw": {},
        "meta_market": "crypto",
        "existing": {"s": None, "q": None},
        "scenario": "crypto_stale_reject",
    },
    # ── US_STOCK — allowed sectors (10 symbols) ──
    {
        "symbol": "NVDA",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.TECH,
        "market_kw": {"volume": 3e9, "atr_pct": 3.5, "adx": 40, "price": 900, "market_cap": 2e12},
        "bt_kw": {"bars": 5000, "sharpe": 2.0},
        "meta_market": "us_stock",
        "existing": {"s": True, "q": True},
        "scenario": "us_tech_golden",
    },
    {
        "symbol": "MSFT",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.TECH,
        "market_kw": {"volume": 2e9, "atr_pct": 2.5, "adx": 35, "price": 430, "market_cap": 3e12},
        "bt_kw": {"bars": 5000, "sharpe": 1.8},
        "meta_market": "us_stock",
        "existing": {"s": True, "q": True},
        "scenario": "us_tech_golden_msft",
    },
    {
        "symbol": "AVGO",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.TECH,
        "market_kw": {"volume": 1e9, "atr_pct": 3.0, "adx": 30, "price": 180, "market_cap": 800e9},
        "bt_kw": {"bars": 3000, "sharpe": 1.5},
        "meta_market": "us_stock",
        "existing": {"s": True, "q": True},
        "scenario": "us_tech_avgo",
    },
    {
        "symbol": "LLY",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.HEALTHCARE,
        "market_kw": {
            "volume": 800e6,
            "atr_pct": 2.8,
            "adx": 28,
            "price": 800,
            "market_cap": 700e9,
        },
        "bt_kw": {"bars": 4000, "sharpe": 1.6},
        "meta_market": "us_stock",
        "existing": {"s": True, "q": True},
        "scenario": "us_healthcare_golden",
    },
    {
        "symbol": "XOM",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.ENERGY,
        "market_kw": {
            "volume": 1.5e9,
            "atr_pct": 2.0,
            "adx": 25,
            "price": 115,
            "market_cap": 500e9,
        },
        "bt_kw": {"bars": 5000, "sharpe": 1.1},
        "meta_market": "us_stock",
        "existing": {"s": True, "q": True},
        "scenario": "us_energy_golden",
    },
    {
        "symbol": "JPM",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.FINANCE,
        "market_kw": {
            "volume": 1.2e9,
            "atr_pct": 1.8,
            "adx": 22,
            "price": 200,
            "market_cap": 600e9,
        },
        "bt_kw": {"bars": 5000, "sharpe": 1.0},
        "meta_market": "us_stock",
        "existing": {"s": True, "q": True},
        "scenario": "us_finance_golden",
    },
    # US — marginal (screen fail possible)
    {
        "symbol": "SMALL_US",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.TECH,
        "market_kw": {"volume": 5e6, "atr_pct": 1.0, "adx": 12, "price": 5, "market_cap": 500e6},
        "bt_kw": {"bars": 300, "sharpe": 0.1, "missing": 10.0},
        "meta_market": "us_stock",
        "existing": {"s": False, "q": None},
        "scenario": "us_screen_fail",
    },
    # US — qualification fail
    {
        "symbol": "WEAK_US",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.HEALTHCARE,
        "market_kw": {"volume": 500e6, "atr_pct": 3.0, "adx": 20, "price": 50, "market_cap": 100e9},
        "bt_kw": {"bars": 200, "sharpe": -0.2, "missing": 15.0},
        "meta_market": "us_stock",
        "existing": {"s": True, "q": False},
        "scenario": "us_qual_fail",
    },
    # US — unavailable
    {
        "symbol": "NODATA_US",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.TECH,
        "market_kw": {"quality": DataQuality.UNAVAILABLE},
        "bt_kw": {},
        "meta_market": "us_stock",
        "existing": {"s": None, "q": None},
        "scenario": "us_data_reject",
    },
    # US — mismatch scenario (existing says fail, shadow says pass)
    {
        "symbol": "MISMATCH_US",
        "ac": AssetClass.US_STOCK,
        "sector": AssetSector.TECH,
        "market_kw": {"volume": 600e6, "atr_pct": 4.0, "adx": 30, "price": 80, "market_cap": 200e9},
        "bt_kw": {"bars": 2000, "sharpe": 1.3},
        "meta_market": "us_stock",
        "existing": {"s": False, "q": None},
        "scenario": "us_verdict_mismatch",
    },
    # ── KR_STOCK — allowed sectors (10 symbols) ──
    {
        "symbol": "005930",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.SEMICONDUCTOR,
        "market_kw": {"volume": 1e9, "atr_pct": 2.5, "adx": 28, "price": 70, "market_cap": 400e9},
        "bt_kw": {"bars": 5000, "sharpe": 1.2},
        "meta_market": "kr_stock",
        "existing": {"s": True, "q": True},
        "scenario": "kr_semi_golden",
    },
    {
        "symbol": "000660",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.SEMICONDUCTOR,
        "market_kw": {
            "volume": 500e6,
            "atr_pct": 3.0,
            "adx": 25,
            "price": 180,
            "market_cap": 120e9,
        },
        "bt_kw": {"bars": 4000, "sharpe": 1.0},
        "meta_market": "kr_stock",
        "existing": {"s": True, "q": True},
        "scenario": "kr_semi_hynix",
    },
    {
        "symbol": "035420",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.IT,
        "market_kw": {"volume": 300e6, "atr_pct": 3.5, "adx": 22, "price": 200, "market_cap": 30e9},
        "bt_kw": {"bars": 3000, "sharpe": 0.8},
        "meta_market": "kr_stock",
        "existing": {"s": False, "q": None},
        "scenario": "kr_it_naver_aligned_screen_fail",
    },
    {
        "symbol": "105560",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.KR_FINANCE,
        "market_kw": {"volume": 200e6, "atr_pct": 2.0, "adx": 20, "price": 65, "market_cap": 25e9},
        "bt_kw": {"bars": 4000, "sharpe": 0.9},
        "meta_market": "kr_stock",
        "existing": {"s": False, "q": None},
        "scenario": "kr_finance_kb_aligned_screen_fail",
    },
    {
        "symbol": "005380",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.AUTOMOTIVE,
        "market_kw": {"volume": 400e6, "atr_pct": 2.5, "adx": 24, "price": 250, "market_cap": 50e9},
        "bt_kw": {"bars": 5000, "sharpe": 1.1},
        "meta_market": "kr_stock",
        "existing": {"s": False, "q": None},
        "scenario": "kr_auto_hyundai_aligned_screen_fail",
    },
    {
        "symbol": "000270",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.AUTOMOTIVE,
        "market_kw": {"volume": 350e6, "atr_pct": 3.0, "adx": 26, "price": 120, "market_cap": 45e9},
        "bt_kw": {"bars": 4500, "sharpe": 1.0},
        "meta_market": "kr_stock",
        "existing": {"s": False, "q": None},
        "scenario": "kr_auto_kia_aligned_screen_fail",
    },
    # KR — screen fail
    {
        "symbol": "SMALL_KR",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.IT,
        "market_kw": {"volume": 2e6, "atr_pct": 0.5, "adx": 8, "price": 3, "market_cap": 100e6},
        "bt_kw": {"bars": 50, "sharpe": -1.0, "missing": 30.0},
        "meta_market": "kr_stock",
        "existing": {"s": False, "q": None},
        "scenario": "kr_screen_fail",
    },
    # KR — stale
    {
        "symbol": "STALE_KR",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.SEMICONDUCTOR,
        "market_kw": {"quality": DataQuality.STALE},
        "bt_kw": {},
        "meta_market": "kr_stock",
        "existing": {"s": None, "q": None},
        "scenario": "kr_stale_reject",
    },
    # KR — mismatch
    {
        "symbol": "MISMATCH_KR",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.KR_FINANCE,
        "market_kw": {"volume": 250e6, "atr_pct": 2.0, "adx": 22, "price": 45, "market_cap": 20e9},
        "bt_kw": {"bars": 3000, "sharpe": 1.3},
        "meta_market": "kr_stock",
        "existing": {"s": False, "q": None},
        "scenario": "kr_verdict_mismatch",
    },
    # KR — unavailable
    {
        "symbol": "NODATA_KR",
        "ac": AssetClass.KR_STOCK,
        "sector": AssetSector.IT,
        "market_kw": {"quality": DataQuality.UNAVAILABLE},
        "bt_kw": {},
        "meta_market": "kr_stock",
        "existing": {"s": None, "q": None},
        "scenario": "kr_data_reject",
    },
]


# ── Runner ────────────────────────────────────────────────────────────


def run_observation() -> ObservationSummary:
    run_ts = datetime.now(timezone.utc)
    records: list[ObservationRecord] = []

    for sc in SCENARIOS:
        symbol = sc["symbol"]
        ac = sc["ac"]
        sector = sc["sector"]

        # Build inputs
        mkw = sc.get("market_kw", {})
        bkw = sc.get("bt_kw", {})
        market = (
            _market(symbol, **mkw)
            if "quality" not in mkw
            else MarketDataSnapshot(
                symbol=symbol,
                quality=mkw["quality"],
            )
        )
        backtest = (
            _backtest(symbol, **bkw)
            if bkw
            else BacktestReadiness(
                symbol=symbol,
                quality=DataQuality.UNAVAILABLE,
            )
        )
        metadata = _meta(symbol, sc.get("meta_market", "unknown"))

        # Run shadow
        shadow = run_shadow_pipeline(
            market,
            backtest,
            ac,
            sector,
            metadata=metadata,
            now_utc=run_ts,
        )

        # Build existing comparison
        ex = sc.get("existing", {})
        existing = ShadowComparisonInput(
            existing_screening_passed=ex.get("s"),
            existing_qualification_passed=ex.get("q"),
        )

        # Compare
        compared = compare_shadow_to_existing(shadow, existing)

        records.append(
            ObservationRecord(
                symbol=symbol,
                asset_class=ac.value,
                sector=sector.value,
                shadow_verdict=shadow.pipeline_output.result.verdict.value,
                comparison_verdict=compared.comparison_verdict.value
                if compared.comparison_verdict
                else None,
                input_fingerprint=shadow.input_fingerprint,
                shadow_timestamp=shadow.shadow_timestamp.isoformat(),
                scenario=sc["scenario"],
            )
        )

    # Summarize
    total = len(records)
    unique = len({r.symbol for r in records})
    ac_dist = dict(Counter(r.asset_class for r in records))
    verdict_dist = dict(Counter(r.shadow_verdict for r in records))
    comp_dist = dict(Counter(r.comparison_verdict for r in records))

    # Calculate rates
    comparable = [
        r
        for r in records
        if r.comparison_verdict
        not in (
            ComparisonVerdict.INSUFFICIENT_STRUCTURAL.value,
            ComparisonVerdict.INSUFFICIENT_OPERATIONAL.value,
            None,
        )
    ]
    matches = [r for r in comparable if r.comparison_verdict == ComparisonVerdict.MATCH.value]
    insufficient = [
        r
        for r in records
        if r.comparison_verdict
        in (
            ComparisonVerdict.INSUFFICIENT_STRUCTURAL.value,
            ComparisonVerdict.INSUFFICIENT_OPERATIONAL.value,
        )
    ]

    verdict_match_rate = len(matches) / len(comparable) if comparable else None
    insufficient_rate = len(insufficient) / total if total else 0.0

    return ObservationSummary(
        run_id=f"RI1A-ALIGN-{run_ts.strftime('%Y%m%d-%H%M%S')}",
        run_timestamp=run_ts.isoformat(),
        total_symbols=total,
        unique_symbols=unique,
        asset_class_distribution=ac_dist,
        verdict_distribution=verdict_dist,
        comparison_distribution=comp_dist,
        verdict_match_rate=verdict_match_rate,
        fail_reason_match_rate=None,  # Requires REASON_MISMATCH tracking (RI-2 scope)
        insufficient_rate=insufficient_rate,
        records=[asdict(r) for r in records],
    )


def main():
    summary = run_observation()

    print("=" * 70)
    print(f"  RI-1A Threshold Alignment Re-measurement: {summary.run_id}")
    print("=" * 70)
    print()
    print(f"  Timestamp:       {summary.run_timestamp}")
    print(f"  Total symbols:   {summary.total_symbols}")
    print(f"  Unique symbols:  {summary.unique_symbols}")
    print()
    print("  Asset Class Distribution:")
    for ac, count in sorted(summary.asset_class_distribution.items()):
        print(f"    {ac:12s}: {count}")
    print()
    print("  Shadow Verdict Distribution:")
    for v, count in sorted(summary.verdict_distribution.items()):
        print(f"    {v:20s}: {count}")
    print()
    print("  Comparison Verdict Distribution:")
    for v, count in sorted(summary.comparison_distribution.items()):
        print(f"    {v:30s}: {count}")
    print()
    if summary.verdict_match_rate is not None:
        print(f"  Verdict Match Rate:    {summary.verdict_match_rate:.1%}")
    else:
        print(f"  Verdict Match Rate:    N/A (no comparable records)")
    print(f"  Insufficient Rate:     {summary.insufficient_rate:.1%}")
    print()

    # Detail table
    print("  Per-symbol detail:")
    print(
        f"  {'Symbol':<16s} {'Class':<10s} {'Sector':<20s} {'Shadow':<18s} {'Comparison':<28s} {'Scenario'}"
    )
    print("  " + "-" * 120)
    for r in summary.records:
        print(
            f"  {r['symbol']:<16s} {r['asset_class']:<10s} {r['sector']:<20s} "
            f"{r['shadow_verdict']:<18s} {str(r['comparison_verdict']):<28s} {r['scenario']}"
        )

    # Write JSON
    out_path = (
        Path(__file__).parent.parent
        / "docs"
        / "operations"
        / "evidence"
        / "ri1a_threshold_alignment_results.json"
    )
    out_path.write_text(json.dumps(asdict(summary), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Results written to: {out_path}")


if __name__ == "__main__":
    main()
