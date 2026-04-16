from __future__ import annotations

from typing import Any, Protocol


class LLMGatewayProtocol(Protocol):
    """Protocol for provider-agnostic LLM interaction."""

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Send messages to the LLM and return the response.

        Returns a dict with keys:
        - content: str | None — the text response
        - tool_calls: list[dict] — any tool calls the model wants to make
        - configured: bool — whether the gateway has an LLM configured
        - error: str | None — error message if the call failed
        """
        ...

    def is_configured(self) -> bool: ...
