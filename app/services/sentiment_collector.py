"""
SentimentCollector — CR-038 Phase 1
External API sentiment + on-chain data collection.
All sources are FREE with no API key required:
  - Alternative.me: Fear & Greed Index
  - Blockchain.com: hash rate, difficulty, tx count, mempool
  - Mempool.space: mempool stats, fee estimates
  - CoinGecko: global market cap, BTC dominance, volume
Read-only, no side effects.
"""

from datetime import datetime, timezone

import aiohttp

from app.core.logging import get_logger
from app.schemas.market_state_schema import OnChainData, SentimentCollectionResult

logger = get_logger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

# All free, no API key required
FEAR_GREED_URL = "https://api.alternative.me/fng/"
BLOCKCHAIN_STATS_URL = "https://api.blockchain.info/stats"
BLOCKCHAIN_MEMPOOL_URL = "https://api.blockchain.info/charts/mempool-count?timespan=1days&format=json"
MEMPOOL_FEES_URL = "https://mempool.space/api/v1/fees/recommended"
MEMPOOL_STATS_URL = "https://mempool.space/api/mempool"
COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"


class SentimentCollector:
    """Collects market sentiment + on-chain data from free public APIs."""

    def _create_session(self) -> aiohttp.ClientSession:
        connector = aiohttp.TCPConnector(
            resolver=aiohttp.resolver.ThreadedResolver()
        )
        return aiohttp.ClientSession(connector=connector, timeout=REQUEST_TIMEOUT)

    async def collect(self) -> SentimentCollectionResult:
        """Collect all available sentiment and on-chain data."""
        async with self._create_session() as session:
            fg_index, fg_label = await self._fetch_fear_greed(session)
            on_chain = await self._fetch_on_chain(session)

            return SentimentCollectionResult(
                fear_greed_index=fg_index,
                fear_greed_label=fg_label,
                on_chain=on_chain,
                source="alternative.me+blockchain.com+mempool.space+coingecko",
                collected_at=datetime.now(timezone.utc),
            )

    async def _fetch_fear_greed(
        self, session: aiohttp.ClientSession
    ) -> tuple[int | None, str | None]:
        try:
            async with session.get(FEAR_GREED_URL) as resp:
                if resp.status != 200:
                    logger.warning("fear_greed_http_error", status=resp.status)
                    return None, None
                data = await resp.json()
                fg_data = data.get("data", [{}])[0]
                index_value = int(fg_data.get("value", 0))
                label = fg_data.get("value_classification", "unknown")
                logger.info(
                    "fear_greed_collected",
                    index=index_value,
                    label=label,
                )
                return index_value, label
        except Exception as e:
            logger.warning("fear_greed_fetch_failed", error=str(e))
            return None, None

    async def _fetch_on_chain(
        self, session: aiohttp.ClientSession
    ) -> OnChainData:
        """Fetch on-chain data from 3 free sources in sequence (rate limit safe)."""
        data = OnChainData()

        # 1. Blockchain.com — hash rate, difficulty, tx count
        await self._fetch_blockchain_stats(session, data)

        # 2. Mempool.space — fees, mempool vsize
        await self._fetch_mempool_data(session, data)

        # 3. CoinGecko — global market data
        await self._fetch_coingecko_global(session, data)

        logger.info(
            "on_chain_collected",
            hash_rate=data.hash_rate,
            mempool_fee_fast=data.mempool_fee_fast,
            btc_dominance=data.btc_dominance,
        )
        return data

    async def _fetch_blockchain_stats(
        self, session: aiohttp.ClientSession, data: OnChainData
    ) -> None:
        """Blockchain.com /stats — free, no key, rate limit ~5/sec."""
        try:
            async with session.get(BLOCKCHAIN_STATS_URL) as resp:
                if resp.status != 200:
                    logger.warning("blockchain_stats_http_error", status=resp.status)
                    return
                stats = await resp.json()
                data.hash_rate = stats.get("hash_rate", 0) / 1e9  # Convert to TH/s
                data.difficulty = stats.get("difficulty")
                data.tx_count_24h = stats.get("n_tx")
                data.mempool_size = stats.get("n_tx_unconfirmed")
                data.avg_block_size = stats.get("blocks_size")
        except Exception as e:
            logger.warning("blockchain_stats_failed", error=str(e))

    async def _fetch_mempool_data(
        self, session: aiohttp.ClientSession, data: OnChainData
    ) -> None:
        """Mempool.space /fees + /mempool — free, no key."""
        try:
            # Fee estimates
            async with session.get(MEMPOOL_FEES_URL) as resp:
                if resp.status == 200:
                    fees = await resp.json()
                    data.mempool_fee_fast = fees.get("fastestFee")
                    data.mempool_fee_medium = fees.get("halfHourFee")
                    data.mempool_fee_slow = fees.get("hourFee")

            # Mempool size
            async with session.get(MEMPOOL_STATS_URL) as resp:
                if resp.status == 200:
                    mempool = await resp.json()
                    vsize = mempool.get("vsize", 0)
                    data.mempool_vsize = vsize / 1_000_000  # Convert to MB
        except Exception as e:
            logger.warning("mempool_data_failed", error=str(e))

    async def _fetch_coingecko_global(
        self, session: aiohttp.ClientSession, data: OnChainData
    ) -> None:
        """CoinGecko /global — free, no key, rate limit ~10-30/min."""
        try:
            async with session.get(COINGECKO_GLOBAL_URL) as resp:
                if resp.status != 200:
                    logger.warning("coingecko_http_error", status=resp.status)
                    return
                result = await resp.json()
                global_data = result.get("data", {})
                market_cap_pct = global_data.get("market_cap_percentage", {})
                data.btc_dominance = market_cap_pct.get("btc")
                data.total_market_cap_usd = global_data.get(
                    "total_market_cap", {}
                ).get("usd")
                data.total_volume_24h_usd = global_data.get(
                    "total_volume", {}
                ).get("usd")
        except Exception as e:
            logger.warning("coingecko_global_failed", error=str(e))
