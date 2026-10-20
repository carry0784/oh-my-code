"""
ExtendedSentimentCollector — Card B item B-5
Additional sentiment data from 4 free public APIs:
  - CryptoPanic: hot news count, bullish/bearish ratio
  - LunarCrush: galaxy_score, alt_rank, social_volume per symbol
  - DefiLlama: total TVL, chain-specific TVL, top protocol TVL changes
  - Messari: market_cap, volume_24h, percent_change_24h per symbol

Persists all collected metrics to the sentiment_hyper TimescaleDB hypertable.
Each source failure is fully independent — others continue on error.
Read-only API calls; no side effects beyond DB persistence.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.models.timescale_hypertables import SentimentHyper

logger = get_logger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

# ── API endpoints (all free, no key required) ────────────────────────────────
CRYPTOPANIC_URL = (
    "https://cryptopanic.com/api/free/v1/posts/"
    "?auth_token=free&public=true&filter=hot"
)
LUNARCRUSH_URL = "https://lunarcrush.com/api4/public/coins/list/v1"
DEFILLAMA_CHAINS_URL = "https://api.llama.fi/v2/chains"
DEFILLAMA_PROTOCOLS_URL = "https://api.llama.fi/protocols"
MESSARI_ASSET_URL = "https://data.messari.io/api/v1/assets/{slug}/metrics"

# ── Messari slug mapping (lowercase symbol → messari slug) ───────────────────
# Covers all 24 symbols commonly traded in this system + common aliases.
MESSARI_SLUG_MAP: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binance-coin",
    "XRP": "xrp",
    "ADA": "cardano",
    "AVAX": "avalanche",
    "DOT": "polkadot",
    "MATIC": "polygon",
    "POL": "polygon",
    "LINK": "chainlink",
    "LTC": "litecoin",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "NEAR": "near-protocol",
    "FTM": "fantom",
    "ARB": "arbitrum",
    "OP": "optimism",
    "SUI": "sui",
    "APT": "aptos",
    "INJ": "injective-protocol",
    "SEI": "sei-network",
    "TIA": "celestia",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    "TON": "toncoin",
}

# ── LunarCrush symbol aliases (our symbol → lunarcrush symbol field) ─────────
LUNARCRUSH_SYMBOL_MAP: dict[str, str] = {
    "MATIC": "POL",  # Polygon rebranded
}


def _strip_usdt(symbol: str) -> str:
    """Strip '/USDT', '/BTC', '/ETH' suffixes. 'BTC/USDT' → 'BTC'."""
    return symbol.split("/")[0].upper().strip()


@dataclass
class ExtendedSentimentResult:
    """Aggregated result from all 4 extended sentiment sources."""

    # {hot_count, bullish_ratio, bearish_ratio, total_posts}
    cryptopanic: dict[str, Any] | None = None
    # {SYMBOL: {galaxy_score, alt_rank, social_volume, market_cap}}
    lunarcrush: dict[str, dict[str, Any]] | None = None
    # {total_tvl, top_chains: {chain: tvl}, top_protocol_changes: [...]}
    defillama: dict[str, Any] | None = None
    # {SYMBOL: {market_cap, volume_24h, pct_change_24h}}
    messari: dict[str, dict[str, Any]] | None = None

    sources_ok: int = 0
    sources_failed: int = 0
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ExtendedSentimentCollector:
    """Collects additional sentiment data from 4 free APIs + persists to hypertable.

    Each source failure is fully independent: one source failing does not
    block the others. DB persistence is attempted after all collections.

    Args:
        db_session_factory: async_sessionmaker instance from app.core.database.
            Pass None to skip DB persistence (useful for testing / dry runs).
    """

    def __init__(self, db_session_factory=None) -> None:
        self.db_session_factory = db_session_factory

    @asynccontextmanager
    async def _create_session(self):
        """Create a shared aiohttp session with ThreadedResolver (mirrors existing collector)."""
        connector = aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
        async with aiohttp.ClientSession(
            connector=connector, timeout=REQUEST_TIMEOUT
        ) as session:
            yield session

    # ── Public API ───────────────────────────────────────────────────────────

    async def collect_all(
        self, symbols: list[str] | None = None
    ) -> ExtendedSentimentResult:
        """Collect from all 4 sources concurrently.

        Args:
            symbols: Trading pair symbols to resolve per-symbol data for.
                     Accepts 'BTC/USDT' or bare 'BTC' forms.
                     Defaults to ['BTC', 'ETH', 'SOL'] when None.
        """
        resolved = self._resolve_symbols(symbols)

        async with self._create_session() as http:
            cp_task = asyncio.create_task(self._fetch_cryptopanic(http))
            lc_task = asyncio.create_task(self._fetch_lunarcrush(http, resolved))
            dl_task = asyncio.create_task(self._fetch_defillama(http))
            ms_task = asyncio.create_task(self._fetch_messari(http, resolved))

            cp, lc, dl, ms = await asyncio.gather(
                cp_task, lc_task, dl_task, ms_task, return_exceptions=False
            )

        sources_ok = sum(1 for v in (cp, lc, dl, ms) if v is not None)
        sources_failed = 4 - sources_ok

        result = ExtendedSentimentResult(
            cryptopanic=cp,
            lunarcrush=lc,
            defillama=dl,
            messari=ms,
            sources_ok=sources_ok,
            sources_failed=sources_failed,
        )

        logger.info(
            "extended_sentiment_collected",
            sources_ok=sources_ok,
            sources_failed=sources_failed,
            symbols=resolved,
        )

        if self.db_session_factory:
            rows_written = await self._persist_to_hypertable(result)
            logger.info("extended_sentiment_persisted", rows=rows_written)

        return result

    # ── Fetch methods ────────────────────────────────────────────────────────

    async def _fetch_cryptopanic(
        self, http: aiohttp.ClientSession
    ) -> dict[str, Any] | None:
        """Fetch CryptoPanic hot posts.

        Extracts: hot_count, bullish_ratio, bearish_ratio, total_posts.
        Free tier may return 200 with limited data or 429/403 on rate limit.
        """
        try:
            async with http.get(CRYPTOPANIC_URL) as resp:
                if resp.status == 429:
                    logger.warning("cryptopanic_rate_limited", status=429)
                    return None
                if resp.status != 200:
                    logger.warning("cryptopanic_http_error", status=resp.status)
                    return None

                data = await resp.json(content_type=None)
                results = data.get("results", [])
                if not results:
                    logger.warning("cryptopanic_empty_results")
                    return None

                total = len(results)
                bullish = sum(
                    1
                    for p in results
                    if (p.get("votes") or {}).get("positive", 0)
                    > (p.get("votes") or {}).get("negative", 0)
                )
                bearish = sum(
                    1
                    for p in results
                    if (p.get("votes") or {}).get("negative", 0)
                    > (p.get("votes") or {}).get("positive", 0)
                )

                payload = {
                    "hot_count": total,
                    "bullish_ratio": round(bullish / total, 4) if total else 0.0,
                    "bearish_ratio": round(bearish / total, 4) if total else 0.0,
                    "total_posts": total,
                }
                logger.info(
                    "cryptopanic_collected",
                    hot_count=payload["hot_count"],
                    bullish_ratio=payload["bullish_ratio"],
                )
                return payload

        except asyncio.TimeoutError:
            logger.warning("cryptopanic_timeout")
            return None
        except Exception as e:
            logger.warning("cryptopanic_fetch_failed", error=str(e))
            return None

    async def _fetch_lunarcrush(
        self, http: aiohttp.ClientSession, symbols: list[str]
    ) -> dict[str, dict[str, Any]] | None:
        """Fetch LunarCrush public coins list and filter for requested symbols.

        Returns per-symbol dict with galaxy_score, alt_rank, social_volume, market_cap.
        Public endpoint; no auth required. Returns None on any failure so callers
        are not impacted.
        """
        try:
            async with http.get(LUNARCRUSH_URL) as resp:
                if resp.status == 401 or resp.status == 403:
                    logger.warning(
                        "lunarcrush_access_restricted", status=resp.status
                    )
                    return None
                if resp.status != 200:
                    logger.warning("lunarcrush_http_error", status=resp.status)
                    return None

                data = await resp.json(content_type=None)
                coins = data.get("data", [])
                if not coins:
                    logger.warning("lunarcrush_empty_response")
                    return None

                # Build lookup by symbol (uppercase)
                coin_by_symbol: dict[str, dict] = {}
                for coin in coins:
                    sym = (coin.get("symbol") or "").upper()
                    if sym:
                        coin_by_symbol[sym] = coin

                result: dict[str, dict[str, Any]] = {}
                for sym in symbols:
                    # Apply alias mapping
                    lookup = LUNARCRUSH_SYMBOL_MAP.get(sym, sym)
                    coin = coin_by_symbol.get(lookup)
                    if coin is None:
                        continue
                    result[sym] = {
                        "galaxy_score": coin.get("galaxy_score"),
                        "alt_rank": coin.get("alt_rank"),
                        "social_volume": coin.get("social_volume"),
                        "market_cap": coin.get("market_cap"),
                    }

                if not result:
                    logger.warning(
                        "lunarcrush_no_matching_symbols", requested=symbols
                    )
                    return None

                logger.info(
                    "lunarcrush_collected",
                    symbols_found=list(result.keys()),
                )
                return result

        except asyncio.TimeoutError:
            logger.warning("lunarcrush_timeout")
            return None
        except Exception as e:
            logger.warning("lunarcrush_fetch_failed", error=str(e))
            return None

    async def _fetch_defillama(
        self, http: aiohttp.ClientSession
    ) -> dict[str, Any] | None:
        """Fetch DefiLlama chain TVL and top protocol changes.

        Collects:
          - total_tvl: sum of all chain TVL in USD
          - top_chains: {chain_name: tvl} for the top 10 chains by TVL
          - top_protocol_changes: list of {name, tvl, change_1d} for top 10 by abs change
        """
        try:
            chains_raw, protocols_raw = await asyncio.gather(
                self._defillama_fetch_chains(http),
                self._defillama_fetch_protocols(http),
                return_exceptions=True,
            )

            if isinstance(chains_raw, Exception) or chains_raw is None:
                logger.warning(
                    "defillama_chains_failed",
                    error=str(chains_raw) if isinstance(chains_raw, Exception) else "none",
                )
                chains_raw = None

            if isinstance(protocols_raw, Exception) or protocols_raw is None:
                logger.warning(
                    "defillama_protocols_failed",
                    error=str(protocols_raw)
                    if isinstance(protocols_raw, Exception)
                    else "none",
                )
                protocols_raw = None

            if chains_raw is None and protocols_raw is None:
                return None

            payload: dict[str, Any] = {}

            if chains_raw is not None:
                # Sort by tvl descending
                sorted_chains = sorted(
                    chains_raw,
                    key=lambda c: c.get("tvl") or 0,
                    reverse=True,
                )
                total_tvl = sum(c.get("tvl") or 0 for c in sorted_chains)
                top_chains = {
                    c.get("name", "unknown"): c.get("tvl", 0)
                    for c in sorted_chains[:10]
                }
                payload["total_tvl"] = total_tvl
                payload["top_chains"] = top_chains

            if protocols_raw is not None:
                # Top 10 by absolute 1-day TVL change
                protocols_with_change = [
                    p
                    for p in protocols_raw
                    if p.get("change_1d") is not None and p.get("tvl") is not None
                ]
                protocols_with_change.sort(
                    key=lambda p: abs(p.get("change_1d") or 0), reverse=True
                )
                payload["top_protocol_changes"] = [
                    {
                        "name": p.get("name"),
                        "tvl": p.get("tvl"),
                        "change_1d": p.get("change_1d"),
                    }
                    for p in protocols_with_change[:10]
                ]

            logger.info(
                "defillama_collected",
                total_tvl=payload.get("total_tvl"),
                top_chains_count=len(payload.get("top_chains", {})),
                protocol_changes_count=len(payload.get("top_protocol_changes", [])),
            )
            return payload

        except asyncio.TimeoutError:
            logger.warning("defillama_timeout")
            return None
        except Exception as e:
            logger.warning("defillama_fetch_failed", error=str(e))
            return None

    async def _defillama_fetch_chains(
        self, http: aiohttp.ClientSession
    ) -> list[dict] | None:
        async with http.get(DEFILLAMA_CHAINS_URL) as resp:
            if resp.status != 200:
                logger.warning("defillama_chains_http_error", status=resp.status)
                return None
            return await resp.json(content_type=None)

    async def _defillama_fetch_protocols(
        self, http: aiohttp.ClientSession
    ) -> list[dict] | None:
        async with http.get(DEFILLAMA_PROTOCOLS_URL) as resp:
            if resp.status != 200:
                logger.warning("defillama_protocols_http_error", status=resp.status)
                return None
            return await resp.json(content_type=None)

    async def _fetch_messari(
        self, http: aiohttp.ClientSession, symbols: list[str]
    ) -> dict[str, dict[str, Any]] | None:
        """Fetch Messari asset metrics for each requested symbol.

        Rate limit: ~20 req/min on free tier. Requests are sent sequentially
        with a short delay to avoid hitting the limit.

        Returns {SYMBOL: {market_cap, volume_24h, pct_change_24h}} or None
        if all requests fail.
        """
        result: dict[str, dict[str, Any]] = {}
        any_success = False

        for sym in symbols:
            slug = MESSARI_SLUG_MAP.get(sym)
            if slug is None:
                logger.warning("messari_unknown_symbol", symbol=sym)
                continue

            metric = await self._fetch_messari_symbol(http, sym, slug)
            if metric is not None:
                result[sym] = metric
                any_success = True

            # Brief pause between requests to respect free-tier rate limit
            await asyncio.sleep(0.2)

        if not any_success:
            return None

        logger.info("messari_collected", symbols_found=list(result.keys()))
        return result

    async def _fetch_messari_symbol(
        self, http: aiohttp.ClientSession, symbol: str, slug: str
    ) -> dict[str, Any] | None:
        """Fetch Messari metrics for a single asset slug."""
        url = MESSARI_ASSET_URL.format(slug=slug)
        try:
            async with http.get(url) as resp:
                if resp.status == 429:
                    logger.warning("messari_rate_limited", symbol=symbol, slug=slug)
                    return None
                if resp.status == 404:
                    logger.warning("messari_not_found", symbol=symbol, slug=slug)
                    return None
                if resp.status != 200:
                    logger.warning(
                        "messari_http_error",
                        symbol=symbol,
                        slug=slug,
                        status=resp.status,
                    )
                    return None

                data = await resp.json(content_type=None)
                market_data = (
                    data.get("data", {}).get("market_data") or {}
                )
                return {
                    "market_cap": market_data.get("market_cap_usd"),
                    "volume_24h": market_data.get("volume_last_24_hours"),
                    "pct_change_24h": market_data.get("percent_change_usd_last_24_hours"),
                }

        except asyncio.TimeoutError:
            logger.warning("messari_timeout", symbol=symbol, slug=slug)
            return None
        except Exception as e:
            logger.warning("messari_fetch_failed", symbol=symbol, slug=slug, error=str(e))
            return None

    # ── Persistence ──────────────────────────────────────────────────────────

    async def _persist_to_hypertable(self, result: ExtendedSentimentResult) -> int:
        """Persist all collected sentiment metrics to the sentiment_hyper table.

        Each metric becomes one row:
          (time=now, source, symbol, metric_name, metric_value, raw_json)

        Uses ON CONFLICT DO NOTHING so re-runs within the same minute are safe.

        Returns the number of rows successfully inserted.
        """
        rows = self._build_rows(result)
        if not rows:
            return 0

        rows_written = 0
        async with self.db_session_factory() as session:
            try:
                stmt = (
                    pg_insert(SentimentHyper)
                    .values(rows)
                    .on_conflict_do_nothing(
                        index_elements=["source", "symbol", "metric_name", "time"]
                    )
                )
                await session.execute(stmt)
                await session.commit()
                rows_written = len(rows)
            except Exception as e:
                await session.rollback()
                logger.warning(
                    "extended_sentiment_persist_failed",
                    error=str(e),
                    rows_attempted=len(rows),
                )

        return rows_written

    def _build_rows(self, result: ExtendedSentimentResult) -> list[dict[str, Any]]:
        """Convert ExtendedSentimentResult into flat DB rows for sentiment_hyper."""
        ts = result.collected_at
        rows: list[dict[str, Any]] = []

        # ── CryptoPanic ───────────────────────────────────────────────────────
        if result.cryptopanic is not None:
            cp = result.cryptopanic
            raw = cp  # full payload as raw_json
            for metric_name, metric_value in [
                ("hot_count", cp.get("hot_count")),
                ("bullish_ratio", cp.get("bullish_ratio")),
                ("bearish_ratio", cp.get("bearish_ratio")),
                ("total_posts", cp.get("total_posts")),
            ]:
                if metric_value is not None:
                    rows.append(
                        self._row(ts, "cryptopanic", None, metric_name, float(metric_value), raw)
                    )

        # ── LunarCrush ────────────────────────────────────────────────────────
        if result.lunarcrush is not None:
            for sym, metrics in result.lunarcrush.items():
                raw = metrics
                for metric_name, metric_value in [
                    ("galaxy_score", metrics.get("galaxy_score")),
                    ("alt_rank", metrics.get("alt_rank")),
                    ("social_volume", metrics.get("social_volume")),
                    ("market_cap", metrics.get("market_cap")),
                ]:
                    if metric_value is not None:
                        rows.append(
                            self._row(
                                ts, "lunarcrush", sym, metric_name, float(metric_value), raw
                            )
                        )

        # ── DefiLlama ─────────────────────────────────────────────────────────
        if result.defillama is not None:
            dl = result.defillama
            if "total_tvl" in dl and dl["total_tvl"] is not None:
                rows.append(
                    self._row(ts, "defillama", None, "total_tvl", float(dl["total_tvl"]), dl)
                )
            # Per-chain TVL rows (symbol = chain name, truncated to 20 chars)
            for chain_name, tvl in (dl.get("top_chains") or {}).items():
                if tvl is not None:
                    chain_sym = chain_name[:20]
                    rows.append(
                        self._row(
                            ts,
                            "defillama",
                            chain_sym,
                            "chain_tvl",
                            float(tvl),
                            {"chain": chain_name, "tvl": tvl},
                        )
                    )

        # ── Messari ───────────────────────────────────────────────────────────
        if result.messari is not None:
            for sym, metrics in result.messari.items():
                raw = metrics
                for metric_name, metric_value in [
                    ("market_cap", metrics.get("market_cap")),
                    ("volume_24h", metrics.get("volume_24h")),
                    ("pct_change_24h", metrics.get("pct_change_24h")),
                ]:
                    if metric_value is not None:
                        rows.append(
                            self._row(
                                ts, "messari", sym, metric_name, float(metric_value), raw
                            )
                        )

        return rows

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _row(
        ts: datetime,
        source: str,
        symbol: str | None,
        metric_name: str,
        metric_value: float,
        raw_json: dict | None,
    ) -> dict[str, Any]:
        return {
            "time": ts,
            "source": source,
            "symbol": symbol,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "raw_json": raw_json,
        }

    @staticmethod
    def _resolve_symbols(symbols: list[str] | None) -> list[str]:
        """Strip USDT/BTC/ETH suffixes and deduplicate. Returns uppercase bare symbols."""
        if not symbols:
            return ["BTC", "ETH", "SOL"]
        seen: set[str] = set()
        resolved: list[str] = []
        for s in symbols:
            bare = _strip_usdt(s)
            if bare not in seen:
                seen.add(bare)
                resolved.append(bare)
        return resolved
