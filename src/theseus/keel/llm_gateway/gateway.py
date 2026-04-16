from __future__ import annotations

import json
import logging
import os
from typing import Any

from litellm import acompletion

from theseus.config import settings

logger = logging.getLogger(__name__)


class LLMGateway:
    """Provider-agnostic LLM gateway using LiteLLM.

    Supports any provider LiteLLM supports: OpenAI, Anthropic, Ollama, etc.
    Falls back gracefully when no LLM is configured.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._provider = provider or settings.llm_provider
        self._model = model or settings.llm_model
        self._api_key = api_key or settings.llm_api_key

    def is_configured(self) -> bool:
        return bool(self._provider and self._model and self._api_key)

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        if not self.is_configured():
            logger.warning("LLM Gateway not configured — returning empty response")
            return {"content": "", "tool_calls": [], "configured": False, "error": None}

        try:
            # Set the API key in environment for LiteLLM
            os.environ[f"{self._provider.upper()}_API_KEY"] = self._api_key

            # Build the model string for LiteLLM
            model_str = self._build_model_string()

            kwargs: dict[str, Any] = {
                "model": model_str,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools

            response = await acompletion(**kwargs)

            message = response.choices[0].message
            content = message.content or ""
            tool_calls = self._extract_tool_calls(message)

            return {
                "content": content,
                "tool_calls": tool_calls,
                "configured": True,
                "error": None,
            }

        except Exception as e:
            logger.error("LLM Gateway error: %s", str(e))
            return {
                "content": "",
                "tool_calls": [],
                "configured": True,
                "error": str(e),
            }

    def _build_model_string(self) -> str:
        """Build the LiteLLM model string from provider + model.

        LiteLLM uses format like 'openai/gpt-4o', 'anthropic/claude-3-opus',
        'ollama/llama3', etc.
        """
        if "/" in self._model:
            return self._model
        return f"{self._provider}/{self._model}"

    def _extract_tool_calls(self, message: Any) -> list[dict[str, Any]]:
        """Extract tool calls from the LLM response message."""
        if not hasattr(message, "tool_calls") or not message.tool_calls:
            return []

        calls: list[dict[str, Any]] = []
        for tc in message.tool_calls:
            args = tc.function.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}

            calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": args,
            })
        return calls
