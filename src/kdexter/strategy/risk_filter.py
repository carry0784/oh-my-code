"""
Risk Filter -- L3 Security & Isolation integration for Strategy Pipeline
K-Dexter AOS v4

Validates signals against risk constraints before position sizing.
Part of the L4~L8 pipeline, enforced at L3 (B1 tier).

Checks:
  1. Account drawdown limit
  2. Per-position exposure limit
  3. Total portfolio exposure limit
  4. Forbidden symbols/exchanges
  5. Signal expiry (TTL)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from kdexter.strategy.signal import Signal, SignalStatus


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

@dataclass
class RiskLimits:
    """Portfolio-level risk constraints."""
    max_drawdown_pct: float = 0.10         # max 10% drawdown
    max_position_pct: float = 0.10         # max 10% per position
    max_portfolio_exposure_pct: float = 0.50  # max 50% total exposure
    max_daily_trades: int = 50             # rate limit
    forbidden_symbols: list[str] = field(default_factory=list)
    forbidden_exchanges: list[str] = field(default_factory=list)


@dataclass
class AccountState:
    """Current account state for risk calculations."""
    total_equity: float = 0.0
    available_balance: float = 0.0
    current_drawdown_pct: float = 0.0      # current drawdown from peak
    open_position_count: int = 0
    total_exposure_pct: float = 0.0        # sum of all positions / equity
    daily_trade_count: int = 0


@dataclass
class RiskCheckResult:
    """Result of risk filtering a signal."""
    passed: bool
    signal_id: str
    checks_run: int
    checks_passed: int
    rejection_reason: Optional[str] = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------ #
# Risk Filter
# ------------------------------------------------------------------ #

class RiskFilter:
    """
    L3 Risk Filter for the strategy pipeline.

    Validates each signal against portfolio risk constraints.
    Signals that fail are marked RISK_REJECTED with a reason.

    Usage:
        rf = RiskFilter(limits=RiskLimits(max_drawdown_pct=0.10))
        result = rf.check(signal, account_state)
        if result.passed:
            # proceed to position sizing
    """

    def __init__(self, limits: Optional[RiskLimits] = None) -> None:
        self._limits = limits or RiskLimits()
        self._history: list[RiskCheckResult] = []

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    @limits.setter
    def limits(self, value: RiskLimits) -> None:
        self._limits = value

    def check(self, signal: Signal, account: AccountState) -> RiskCheckResult:
        """
        Run all risk checks on a signal. Mutates signal status on rejection.

        Args:
            signal: the trading signal to validate
            account: current account state

        Returns:
            RiskCheckResult with pass/fail and reason
        """
        checks_run = 0
        checks_passed = 0

        # 1. Signal expiry
        checks_run += 1
        if signal.is_expired:
            signal.mark_expired()
            return self._fail(signal, checks_run, checks_passed,
                              "Signal expired (TTL exceeded)")
        checks_passed += 1

        # 2. Forbidden symbol
        checks_run += 1
        if signal.symbol in self._limits.forbidden_symbols:
            signal.reject(f"Forbidden symbol: {signal.symbol}")
            return self._fail(signal, checks_run, checks_passed,
                              f"Forbidden symbol: {signal.symbol}")
        checks_passed += 1

        # 3. Forbidden exchange
        checks_run += 1
        if signal.exchange in self._limits.forbidden_exchanges:
            signal.reject(f"Forbidden exchange: {signal.exchange}")
            return self._fail(signal, checks_run, checks_passed,
                              f"Forbidden exchange: {signal.exchange}")
        checks_passed += 1

        # 4. Drawdown limit
        checks_run += 1
        if account.current_drawdown_pct >= self._limits.max_drawdown_pct:
            signal.reject("Account drawdown limit reached")
            return self._fail(signal, checks_run, checks_passed,
                              f"Drawdown {account.current_drawdown_pct:.2%} "
                              f">= limit {self._limits.max_drawdown_pct:.2%}")
        checks_passed += 1

        # 5. Per-position exposure
        checks_run += 1
        if signal.max_position_pct > self._limits.max_position_pct:
            signal.reject("Position size exceeds limit")
            return self._fail(signal, checks_run, checks_passed,
                              f"Position {signal.max_position_pct:.2%} "
                              f"> limit {self._limits.max_position_pct:.2%}")
        checks_passed += 1

        # 6. Total portfolio exposure
        checks_run += 1
        if account.total_exposure_pct >= self._limits.max_portfolio_exposure_pct:
            signal.reject("Portfolio exposure limit reached")
            return self._fail(signal, checks_run, checks_passed,
                              f"Portfolio exposure {account.total_exposure_pct:.2%} "
                              f">= limit {self._limits.max_portfolio_exposure_pct:.2%}")
        checks_passed += 1

        # 7. Daily trade count
        checks_run += 1
        if account.daily_trade_count >= self._limits.max_daily_trades:
            signal.reject("Daily trade limit reached")
            return self._fail(signal, checks_run, checks_passed,
                              f"Daily trades {account.daily_trade_count} "
                              f">= limit {self._limits.max_daily_trades}")
        checks_passed += 1

        # All passed
        signal.approve_risk()
        result = RiskCheckResult(
            passed=True,
            signal_id=signal.signal_id,
            checks_run=checks_run,
            checks_passed=checks_passed,
        )
        self._history.append(result)
        return result

    def _fail(self, signal: Signal, checks_run: int, checks_passed: int,
              reason: str) -> RiskCheckResult:
        result = RiskCheckResult(
            passed=False,
            signal_id=signal.signal_id,
            checks_run=checks_run,
            checks_passed=checks_passed,
            rejection_reason=reason,
        )
        self._history.append(result)
        return result

    def history(self) -> list[RiskCheckResult]:
        return list(self._history)

    def pass_rate(self) -> float:
        """Return percentage of signals that passed risk check."""
        if not self._history:
            return 0.0
        return sum(1 for r in self._history if r.passed) / len(self._history)
