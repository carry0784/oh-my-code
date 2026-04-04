from abc import ABC, abstractmethod
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        self.last_usage: dict[str, int] = {}
        if provider == "anthropic":
            self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.model = "claude-sonnet-4-20250514"
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = "gpt-4-turbo-preview"

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        pass

    async def _call_llm(self, prompt: str) -> str:
        self.last_usage = {}
        try:
            if self.provider == "anthropic":
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                if hasattr(response, "usage") and response.usage:
                    self.last_usage = {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    }
                return response.content[0].text
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                )
                if hasattr(response, "usage") and response.usage:
                    self.last_usage = {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                    }
                return response.choices[0].message.content
        except Exception as e:
            logger.error("LLM call failed", provider=self.provider, error=str(e))
            raise

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        pass
