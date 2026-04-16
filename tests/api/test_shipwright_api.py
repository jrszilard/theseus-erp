from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


class TestShipwrightAPI:
    @pytest.mark.asyncio
    async def test_chat_endpoint_returns_response(self, client: AsyncClient) -> None:
        """Test the chat endpoint with a mock LLM that returns a text response."""
        mock_gateway = MagicMock()
        mock_gateway.is_configured.return_value = True

        async def mock_complete(**kwargs):
            return {"content": "Hello from the Shipwright!", "tool_calls": [], "configured": True, "error": None}
        mock_gateway.complete = AsyncMock(side_effect=mock_complete)

        with patch("theseus.api.routes.shipwright._get_gateway", return_value=mock_gateway):
            response = await client.post(
                "/api/v1/shipwright/chat",
                json={"message": "Hello"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Hello from the Shipwright!"
            assert "conversation_id" in data

    @pytest.mark.asyncio
    async def test_chat_without_llm_configured(self, client: AsyncClient) -> None:
        mock_gateway = MagicMock()
        mock_gateway.is_configured.return_value = False

        with patch("theseus.api.routes.shipwright._get_gateway", return_value=mock_gateway):
            response = await client.post(
                "/api/v1/shipwright/chat",
                json={"message": "Hello"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "not configured" in data["message"].lower() or "no ai" in data["message"].lower()
