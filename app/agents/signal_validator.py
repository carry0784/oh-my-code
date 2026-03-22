import json
from typing import Any

from app.agents.base import BaseAgent
from app.models.signal import Signal
from app.core.logging import get_logger

logger = get_logger(__name__)


class SignalValidatorAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """You are a trading signal validation agent. Your role is to analyze trading signals
and determine if they should be executed based on:

1. Technical analysis validity (support/resistance, trend alignment)
2. Risk/reward ratio (minimum 1:2 preferred)
3. Market conditions and volatility
4. Position sizing appropriateness

Respond with a JSON object containing:
- approved: boolean
- confidence: float (0-1)
- reasoning: string (brief explanation)
- suggested_adjustments: object (optional modifications to stop_loss, take_profit, or position_size)

Be conservative - only approve signals with clear edge and proper risk management."""

    async def validate(self, signal: Signal) -> dict[str, Any]:
        prompt = f"""Analyze this trading signal:

Symbol: {signal.symbol}
Exchange: {signal.exchange}
Type: {signal.signal_type.value}
Entry Price: {signal.entry_price}
Stop Loss: {signal.stop_loss}
Take Profit: {signal.take_profit}
Source Confidence: {signal.confidence}
Metadata: {json.dumps(signal.signal_metadata)}

Evaluate the signal quality and provide your assessment."""

        try:
            response = await self._call_llm(prompt)
            result = json.loads(response)
            logger.info(
                "Signal validated by agent",
                signal_id=signal.id,
                approved=result.get("approved"),
            )
            return result
        except json.JSONDecodeError:
            logger.warning("Agent response not valid JSON, parsing manually")
            return {
                "approved": False,
                "confidence": 0.0,
                "reasoning": response,
            }

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        signal = context.get("signal")
        if not signal:
            return {"success": False, "error": "No signal provided"}
        return await self.validate(signal)
