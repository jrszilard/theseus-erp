from __future__ import annotations
from typing import Any, Protocol


class LLMGatewayProtocol(Protocol):
    async def complete(self, *, messages: list[dict[str, str]], model: str | None = None,
                       tools: list[dict[str, Any]] | None = None, temperature: float = 0.7) -> dict[str, Any]: ...
    def is_configured(self) -> bool: ...
