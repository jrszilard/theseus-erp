import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from theseus.keel.llm_gateway.gateway import LLMGateway


class TestLLMGateway:
    def test_is_configured_false_by_default(self) -> None:
        gw = LLMGateway()
        assert gw.is_configured() is False

    def test_is_configured_true_with_settings(self) -> None:
        gw = LLMGateway(provider="openai", model="gpt-4o", api_key="sk-test")
        assert gw.is_configured() is True

    @pytest.mark.asyncio
    async def test_complete_returns_empty_when_not_configured(self) -> None:
        gw = LLMGateway()
        result = await gw.complete(messages=[{"role": "user", "content": "hello"}])
        assert result["content"] == ""
        assert result["configured"] is False
        assert result["tool_calls"] == []

    @pytest.mark.asyncio
    async def test_complete_calls_litellm(self) -> None:
        gw = LLMGateway(provider="openai", model="gpt-4o", api_key="sk-test")

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Hello! How can I help?"
        mock_message.tool_calls = None
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        with patch("theseus.keel.llm_gateway.gateway.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.return_value = mock_response
            result = await gw.complete(
                messages=[{"role": "user", "content": "hello"}],
            )
            assert result["content"] == "Hello! How can I help?"
            assert result["tool_calls"] == []
            mock_acomp.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_returns_tool_calls(self) -> None:
        gw = LLMGateway(provider="openai", model="gpt-4o", api_key="sk-test")

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "create_entity"
        mock_tool_call.function.arguments = json.dumps({"plank": "contacts", "entity": "Contact", "data": {"name": "Acme"}})

        mock_message = MagicMock()
        mock_message.content = None
        mock_message.tool_calls = [mock_tool_call]

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("theseus.keel.llm_gateway.gateway.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.return_value = mock_response
            result = await gw.complete(
                messages=[{"role": "user", "content": "create a contact named Acme"}],
                tools=[{"type": "function", "function": {"name": "create_entity"}}],
            )
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["id"] == "call_123"
            assert result["tool_calls"][0]["name"] == "create_entity"

    @pytest.mark.asyncio
    async def test_complete_handles_error_gracefully(self) -> None:
        gw = LLMGateway(provider="openai", model="gpt-4o", api_key="sk-bad")

        with patch("theseus.keel.llm_gateway.gateway.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.side_effect = Exception("API error")
            result = await gw.complete(
                messages=[{"role": "user", "content": "hello"}],
            )
            assert result["error"] is not None
            assert "API error" in result["error"]
