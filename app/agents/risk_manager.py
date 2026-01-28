import json
from typing import Any

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RiskManagerAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return f"""You are a risk management agent for a trading system. Your role is to:

1. Evaluate portfolio risk exposure
2. Calculate appropriate position sizes
3. Enforce risk limits (max {settings.risk_limit_percent}% per trade)
4. Monitor correlation between positions
5. Suggest hedging strategies when needed

Max position size: ${settings.max_position_size_usd}
Risk limit per trade: {settings.risk_limit_percent}%

Respond with JSON containing:
- approved: boolean
- position_size: float (adjusted quantity)
- risk_score: float (0-1, where 1 is highest risk)
- warnings: list of strings
- reasoning: string"""

    async def evaluate_risk(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None,
        current_positions: list[dict],
        account_balance: float,
    ) -> dict[str, Any]:
        prompt = f"""Evaluate risk for this proposed trade:

Symbol: {symbol}
Side: {side}
Quantity: {quantity}
Entry Price: {entry_price}
Stop Loss: {stop_loss}
Position Value: ${quantity * entry_price:.2f}

Current Portfolio:
{json.dumps(current_positions, indent=2)}

Account Balance: ${account_balance:.2f}

Assess the risk and provide position sizing recommendations."""

        try:
            response = await self._call_llm(prompt)
            result = json.loads(response)
            logger.info(
                "Risk evaluation complete",
                symbol=symbol,
                approved=result.get("approved"),
                risk_score=result.get("risk_score"),
            )
            return result
        except json.JSONDecodeError:
            return {
                "approved": False,
                "position_size": 0,
                "risk_score": 1.0,
                "warnings": ["Could not parse risk assessment"],
                "reasoning": response,
            }

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.evaluate_risk(
            symbol=context.get("symbol", ""),
            side=context.get("side", ""),
            quantity=context.get("quantity", 0),
            entry_price=context.get("entry_price", 0),
            stop_loss=context.get("stop_loss"),
            current_positions=context.get("current_positions", []),
            account_balance=context.get("account_balance", 0),
        )
