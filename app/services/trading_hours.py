"""Trading Hours Guard — market open/closed determination.

Phase 6B-2 of CR-048.  Provides:
  - Market profile definitions (crypto_247, kr_equity_regular, us_equity_regular)
  - Stateless is_open() check with reason_code
  - No holiday calendar (placeholder for future expansion)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


# ── Market Profiles ──────────────────────────────────────────────────


class MarketProfile(str, Enum):
    """Predefined market time profiles."""

    CRYPTO_247 = "crypto_247"
    KR_EQUITY_REGULAR = "kr_equity_regular"
    US_EQUITY_REGULAR = "us_equity_regular"


class MarketStatus(str, Enum):
    """Result of a trading hours check."""

    OPEN = "open"
    CLOSED = "closed"


class ClosedReason(str, Enum):
    """Why the market is closed."""

    MARKET_OPEN = "market_open"  # not actually closed
    OUTSIDE_HOURS = "outside_hours"
    WEEKEND = "weekend"
    UNKNOWN_PROFILE = "unknown_profile"


# ── Timezone offsets (no pytz dependency) ────────────────────────────

KST = timezone(timedelta(hours=9))  # UTC+9
EST = timezone(timedelta(hours=-5))  # UTC-5 (Eastern Standard)
EDT = timezone(timedelta(hours=-4))  # UTC-4 (Eastern Daylight)


# ── Market Hours Check Result ────────────────────────────────────────


@dataclass
class TradingHoursResult:
    """Outcome of a trading hours check."""

    is_open: bool
    market: str  # profile name
    status: MarketStatus
    reason_code: str  # ClosedReason value
    checked_at: datetime  # UTC


# ── Guard Implementation ─────────────────────────────────────────────


# KR equity regular hours: Mon-Fri 09:00-15:30 KST
_KR_OPEN = time(9, 0)
_KR_CLOSE = time(15, 30)

# US equity regular hours: Mon-Fri 09:30-16:00 Eastern
_US_OPEN = time(9, 30)
_US_CLOSE = time(16, 0)


def _is_us_dst(dt_utc: datetime) -> bool:
    """Approximate US DST check (second Sunday of March to first Sunday of November).

    Good enough for trading hours; not a full timezone library.
    """
    year = dt_utc.year
    # Second Sunday of March
    march_1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    dst_start_day = 14 - march_1.weekday()  # weekday: Mon=0 .. Sun=6
    if dst_start_day <= 7:
        dst_start_day += 7
    dst_start = datetime(year, 3, dst_start_day, 7, 0, tzinfo=timezone.utc)  # 2am EST = 7am UTC

    # First Sunday of November
    nov_1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    dst_end_day = 7 - nov_1.weekday()
    if dst_end_day == 0:
        dst_end_day = 7
    dst_end = datetime(year, 11, dst_end_day, 6, 0, tzinfo=timezone.utc)  # 2am EDT = 6am UTC

    return dst_start <= dt_utc < dst_end


class TradingHoursGuard:
    """Stateless guard that checks whether a market is currently open.

    Uses market_profile strings to determine the applicable schedule.
    """

    # Profile → asset_class mapping for convenience
    ASSET_CLASS_PROFILES: dict[str, MarketProfile] = {
        "CRYPTO": MarketProfile.CRYPTO_247,
        "KR_STOCK": MarketProfile.KR_EQUITY_REGULAR,
        "US_STOCK": MarketProfile.US_EQUITY_REGULAR,
    }

    def check(
        self,
        market_profile: str | MarketProfile,
        *,
        now: datetime | None = None,
    ) -> TradingHoursResult:
        """Check if the given market is currently open.

        Args:
            market_profile: One of MarketProfile values or asset class string.
            now: Override current time (UTC). Defaults to utcnow.

        Returns:
            TradingHoursResult with is_open, status, and reason_code.
        """
        now_utc = now or datetime.now(timezone.utc)

        # Resolve asset class shorthand to profile
        if isinstance(market_profile, str) and market_profile in self.ASSET_CLASS_PROFILES:
            profile = self.ASSET_CLASS_PROFILES[market_profile]
        elif isinstance(market_profile, MarketProfile):
            profile = market_profile
        elif isinstance(market_profile, str):
            try:
                profile = MarketProfile(market_profile)
            except ValueError:
                return TradingHoursResult(
                    is_open=False,
                    market=market_profile,
                    status=MarketStatus.CLOSED,
                    reason_code=ClosedReason.UNKNOWN_PROFILE.value,
                    checked_at=now_utc,
                )
        else:
            return TradingHoursResult(
                is_open=False,
                market=str(market_profile),
                status=MarketStatus.CLOSED,
                reason_code=ClosedReason.UNKNOWN_PROFILE.value,
                checked_at=now_utc,
            )

        if profile == MarketProfile.CRYPTO_247:
            return self._check_crypto(now_utc)
        elif profile == MarketProfile.KR_EQUITY_REGULAR:
            return self._check_kr_equity(now_utc)
        elif profile == MarketProfile.US_EQUITY_REGULAR:
            return self._check_us_equity(now_utc)
        else:
            return TradingHoursResult(
                is_open=False,
                market=profile.value,
                status=MarketStatus.CLOSED,
                reason_code=ClosedReason.UNKNOWN_PROFILE.value,
                checked_at=now_utc,
            )

    def check_by_asset_class(
        self,
        asset_class: str,
        *,
        now: datetime | None = None,
    ) -> TradingHoursResult:
        """Convenience: check using asset class name (CRYPTO, KR_STOCK, US_STOCK)."""
        return self.check(asset_class, now=now)

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _check_crypto(now_utc: datetime) -> TradingHoursResult:
        """Crypto is always open."""
        return TradingHoursResult(
            is_open=True,
            market=MarketProfile.CRYPTO_247.value,
            status=MarketStatus.OPEN,
            reason_code=ClosedReason.MARKET_OPEN.value,
            checked_at=now_utc,
        )

    @staticmethod
    def _check_kr_equity(now_utc: datetime) -> TradingHoursResult:
        """KR equity: Mon-Fri 09:00-15:30 KST."""
        kst_now = now_utc.astimezone(KST)
        market = MarketProfile.KR_EQUITY_REGULAR.value

        # Weekend check (Mon=0 .. Sun=6)
        if kst_now.weekday() >= 5:
            return TradingHoursResult(
                is_open=False,
                market=market,
                status=MarketStatus.CLOSED,
                reason_code=ClosedReason.WEEKEND.value,
                checked_at=now_utc,
            )

        # Hours check
        local_time = kst_now.time()
        if _KR_OPEN <= local_time < _KR_CLOSE:
            return TradingHoursResult(
                is_open=True,
                market=market,
                status=MarketStatus.OPEN,
                reason_code=ClosedReason.MARKET_OPEN.value,
                checked_at=now_utc,
            )

        return TradingHoursResult(
            is_open=False,
            market=market,
            status=MarketStatus.CLOSED,
            reason_code=ClosedReason.OUTSIDE_HOURS.value,
            checked_at=now_utc,
        )

    @staticmethod
    def _check_us_equity(now_utc: datetime) -> TradingHoursResult:
        """US equity: Mon-Fri 09:30-16:00 Eastern (EST/EDT auto-detected)."""
        tz = EDT if _is_us_dst(now_utc) else EST
        eastern_now = now_utc.astimezone(tz)
        market = MarketProfile.US_EQUITY_REGULAR.value

        # Weekend check
        if eastern_now.weekday() >= 5:
            return TradingHoursResult(
                is_open=False,
                market=market,
                status=MarketStatus.CLOSED,
                reason_code=ClosedReason.WEEKEND.value,
                checked_at=now_utc,
            )

        # Hours check
        local_time = eastern_now.time()
        if _US_OPEN <= local_time < _US_CLOSE:
            return TradingHoursResult(
                is_open=True,
                market=market,
                status=MarketStatus.OPEN,
                reason_code=ClosedReason.MARKET_OPEN.value,
                checked_at=now_utc,
            )

        return TradingHoursResult(
            is_open=False,
            market=market,
            status=MarketStatus.CLOSED,
            reason_code=ClosedReason.OUTSIDE_HOURS.value,
            checked_at=now_utc,
        )
