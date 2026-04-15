from __future__ import annotations
import logging
from typing import Any
from theseus.config import settings

logger = logging.getLogger(__name__)


class LLMGateway:
    def is_configured(self) -> bool:
        return bool(settings.llm_provider and settings.llm_model and settings.llm_api_key)

    async def complete(self, *, messages: list[dict[str, str]], model: str | None = None,
                       tools: list[dict[str, Any]] | None = None, temperature: float = 0.7) -> dict[str, Any]:
        if not self.is_configured():
            logger.warning("LLM Gateway not configured — returning empty response")
            return {"content": "", "tool_calls": [], "configured": False}
        raise NotImplementedError("Full LLM Gateway implementation is in Plan 4 (Shipwright)")
