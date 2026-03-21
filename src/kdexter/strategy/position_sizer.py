"""
Position Sizer -- L8 Execution Cell sub-component
K-Dexter AOS v4

Calculates position quantity from a risk-approved signal and account state.

Sizing methods:
  1. Fixed fraction: risk a fixed % of equity per trade
  2. Kelly criterion: optimal fraction based on win rate and payoff ratio
  3. Fixed quantity: use a pre-set quantity (simplest)

Default: fixed fraction (most common for crypto/stock trading).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from kdexter.strategy.signal import Signal, SignalStatus
from kdexter.strategy.risk_filter import AccountState


class SizingMethod(Enum):
    FIXED_FRACTION = "FIXED_FRACTION"
    KELLY = "KELLY"
    FIXED_QUANTITY = "FIXED_QUANTITY"


@dataclass
class SizingParams:
    """Configuration for position sizing."""
    method: SizingMethod = SizingMethod.FIXED_FRACTION
    fixed_fraction_pct: float = 0.02   # risk 2% of equity
    kelly_win_rate: float = 0.55       # historical win rate
    kelly_payoff_ratio: float = 1.5    # avg_win / avg_loss
    kelly_fraction: float = 0.25       # fraction of Kelly to use (quarter-Kelly)
    fixed_quantity: float = 0.0        # for FIXED_QUANTITY method
    min_quantity: float = 0.0          # minimum order size
    max_quantity: float = float("inf") # maximum order size


@dataclass
class SizingResult:
    """Result of position sizing calculation."""
    signal_id: str
    quantity: float
    method_used: SizingMethod
    risk_amount: float       # $ amount risked
    notional_value: float    # total position value
    sized: bool = True
    rejection_reason: Optional[str] = None


class PositionSizer:
    """
    Calculates position quantity from signal + account state.

    Usage:
        sizer = PositionSizer(SizingParams(method=SizingMethod.FIXED_FRACTION))
        result = sizer.size(signal, account)
        if result.sized:
            signal.set_size(result.quantity)
    """

    def __init__(self, params: Optional[SizingParams] = None) -> None:
        self._params = params or SizingParams()

    @property
    def params(self) -> SizingParams:
        return self._params

    def size(self, signal: Signal, account: AccountState) -> SizingResult:
        """
        Calculate position size for a risk-approved signal.

        Args:
            signal: must be in RISK_APPROVED status
            account: current account state

        Returns:
            SizingResult with quantity
        """
        if signal.status != SignalStatus.RISK_APPROVED:
            return SizingResult(
                signal_id=signal.signal_id,
                quantity=0.0,
                method_used=self._params.method,
                risk_amount=0.0,
                notional_value=0.0,
                sized=False,
                rejection_reason=f"Signal not risk-approved (status={signal.status.value})",
            )

        if self._params.method == SizingMethod.FIXED_FRACTION:
            qty, risk_amt = self._fixed_fraction(signal, account)
        elif self._params.method == SizingMethod.KELLY:
            qty, risk_amt = self._kelly(signal, account)
        elif self._params.method == SizingMethod.FIXED_QUANTITY:
            qty = self._params.fixed_quantity
            risk_amt = qty * abs(signal.entry_price - signal.stop_loss) if (
                signal.entry_price and signal.stop_loss
            ) else 0.0
        else:
            qty, risk_amt = 0.0, 0.0

        # Clamp
        qty = max(self._params.min_quantity, min(self._params.max_quantity, qty))

        # Notional value
        price = signal.entry_price or 0.0
        notional = qty * price

        if qty <= 0:
            return SizingResult(
                signal_id=signal.signal_id,
                quantity=0.0,
                method_used=self._params.method,
                risk_amount=0.0,
                notional_value=0.0,
                sized=False,
                rejection_reason="Calculated quantity is zero",
            )

        signal.set_size(qty)
        return SizingResult(
            signal_id=signal.signal_id,
            quantity=qty,
            method_used=self._params.method,
            risk_amount=round(risk_amt, 4),
            notional_value=round(notional, 4),
        )

    def _fixed_fraction(self, signal: Signal, account: AccountState) -> tuple[float, float]:
        """
        Fixed fraction: risk X% of equity.
        quantity = (equity * risk_pct) / risk_per_unit
        """
        equity = account.total_equity
        if equity <= 0:
            return 0.0, 0.0

        risk_amount = equity * self._params.fixed_fraction_pct

        # Risk per unit = distance from entry to stop loss
        if signal.entry_price and signal.stop_loss and signal.entry_price != signal.stop_loss:
            risk_per_unit = abs(signal.entry_price - signal.stop_loss)
            qty = risk_amount / risk_per_unit
        elif signal.entry_price and signal.entry_price > 0:
            # No stop loss -- use max_risk_pct as fraction of entry price
            risk_per_unit = signal.entry_price * signal.max_risk_pct
            qty = risk_amount / risk_per_unit if risk_per_unit > 0 else 0.0
        else:
            qty = 0.0

        return qty, risk_amount

    def _kelly(self, signal: Signal, account: AccountState) -> tuple[float, float]:
        """
        Kelly criterion: f* = (p*b - q) / b
        where p=win_rate, q=1-p, b=payoff_ratio
        Use fraction_of_kelly for practical sizing (quarter-Kelly default).
        """
        p = self._params.kelly_win_rate
        b = self._params.kelly_payoff_ratio
        q = 1.0 - p

        kelly_f = (p * b - q) / b if b > 0 else 0.0
        kelly_f = max(0.0, kelly_f)  # never negative

        practical_f = kelly_f * self._params.kelly_fraction
        risk_amount = account.total_equity * practical_f

        if signal.entry_price and signal.stop_loss and signal.entry_price != signal.stop_loss:
            risk_per_unit = abs(signal.entry_price - signal.stop_loss)
            qty = risk_amount / risk_per_unit
        elif signal.entry_price and signal.entry_price > 0:
            qty = risk_amount / signal.entry_price
        else:
            qty = 0.0

        return qty, risk_amount
