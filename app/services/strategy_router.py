"""Strategy Router — minimal strategy-to-asset routing.

Phase 5A of CR-048.  Determines which strategies are allowed to run
on which symbols, based on the strategy's market matrix constraints.

No ensemble logic — just routing eligibility.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Routing Result ─────────────────────────────────────────────────────


@dataclass
class RoutingCheck:
    check_name: str
    passed: bool
    detail: str | None = None


@dataclass
class RoutingResult:
    """Whether a strategy is routable to a specific symbol."""

    strategy_id: str = ""
    symbol: str = ""
    timeframe: str = ""
    routable: bool = False
    checks: list[RoutingCheck] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)


# ── Strategy Router (stateless) ────────────────────────────────────────


class StrategyRouter:
    """Stateless routing engine — checks strategy market matrix against symbol.

    Routing checks:
      1. asset_class match
      2. exchange match (symbol's broker is in strategy's allowed exchanges)
      3. sector match (if strategy specifies sectors)
      4. timeframe match
      5. max_symbols not exceeded
    """

    def route(
        self,
        *,
        # Strategy constraints (from Strategy model)
        strategy_id: str,
        strategy_asset_classes: list[str],
        strategy_exchanges: list[str],
        strategy_sectors: list[str] | None,
        strategy_timeframes: list[str],
        strategy_max_symbols: int,
        # Symbol properties
        symbol: str,
        symbol_asset_class: str,
        symbol_exchanges: list[str],
        symbol_sector: str,
        # Request
        timeframe: str,
        current_symbol_count: int = 0,
    ) -> RoutingResult:
        checks: list[RoutingCheck] = []

        # Check 1: asset class match
        c1 = symbol_asset_class in strategy_asset_classes
        checks.append(
            RoutingCheck(
                check_name="asset_class_match",
                passed=c1,
                detail=f"symbol={symbol_asset_class}, strategy={strategy_asset_classes}",
            )
        )

        # Check 2: exchange match
        sym_exchanges_upper = {e.upper() for e in symbol_exchanges}
        strat_exchanges_upper = {e.upper() for e in strategy_exchanges}
        c2 = bool(sym_exchanges_upper & strat_exchanges_upper)
        checks.append(
            RoutingCheck(
                check_name="exchange_match",
                passed=c2,
                detail=f"symbol={list(sym_exchanges_upper)}, strategy={list(strat_exchanges_upper)}",
            )
        )

        # Check 3: sector match (if strategy specifies sectors)
        if strategy_sectors:
            strat_sectors_lower = {s.lower() for s in strategy_sectors}
            c3 = symbol_sector.lower() in strat_sectors_lower
        else:
            c3 = True  # no sector constraint = any sector
        checks.append(
            RoutingCheck(
                check_name="sector_match",
                passed=c3,
                detail=f"symbol={symbol_sector}, strategy={strategy_sectors}",
            )
        )

        # Check 4: timeframe match
        c4 = timeframe in strategy_timeframes
        checks.append(
            RoutingCheck(
                check_name="timeframe_match",
                passed=c4,
                detail=f"requested={timeframe}, strategy={strategy_timeframes}",
            )
        )

        # Check 5: max symbols cap
        c5 = current_symbol_count < strategy_max_symbols
        checks.append(
            RoutingCheck(
                check_name="max_symbols_cap",
                passed=c5,
                detail=f"current={current_symbol_count}, max={strategy_max_symbols}",
            )
        )

        failed = [c for c in checks if not c.passed]
        return RoutingResult(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            routable=len(failed) == 0,
            checks=checks,
            failed_checks=[c.check_name for c in failed],
        )

    def find_eligible_strategies(
        self,
        *,
        strategies: list[dict],
        symbol: str,
        symbol_asset_class: str,
        symbol_exchanges: list[str],
        symbol_sector: str,
        timeframe: str,
    ) -> list[RoutingResult]:
        """Find all strategies eligible for a given symbol+timeframe.

        Each strategy dict must have keys:
          id, asset_classes, exchanges, sectors, timeframes, max_symbols,
          current_symbol_count
        """
        results = []
        for strat in strategies:
            result = self.route(
                strategy_id=strat["id"],
                strategy_asset_classes=strat["asset_classes"],
                strategy_exchanges=strat["exchanges"],
                strategy_sectors=strat.get("sectors"),
                strategy_timeframes=strat["timeframes"],
                strategy_max_symbols=strat.get("max_symbols", 20),
                symbol=symbol,
                symbol_asset_class=symbol_asset_class,
                symbol_exchanges=symbol_exchanges,
                symbol_sector=symbol_sector,
                timeframe=timeframe,
                current_symbol_count=strat.get("current_symbol_count", 0),
            )
            results.append(result)
        return results
