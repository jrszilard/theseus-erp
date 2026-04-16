import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.api.dependencies import set_registry
from theseus.shipwright.engine import ShipwrightEngine

from pathlib import Path
PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"


def _setup_registry():
    parser = BlueprintFileParser()
    registry = BlueprintRegistry()
    for plank_dir in sorted(PLANKS_DIR.iterdir()):
        bp_dir = plank_dir / "blueprints"
        if bp_dir.is_dir():
            for bp in parser.parse_directory(bp_dir):
                try:
                    registry.register(bp)
                except ValueError:
                    pass  # already registered
    set_registry(registry)
    return registry


def _mock_llm_text_response(text: str):
    """Create a mock LLM gateway that returns a text response."""
    async def mock_complete(**kwargs):
        return {"content": text, "tool_calls": [], "configured": True, "error": None}
    gateway = MagicMock()
    gateway.is_configured.return_value = True
    gateway.complete = AsyncMock(side_effect=mock_complete)
    return gateway


def _mock_llm_tool_then_text(tool_name: str, tool_args: dict, final_text: str):
    """Create a mock LLM gateway that first returns a tool call, then a text response."""
    call_count = 0
    async def mock_complete(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "content": None,
                "tool_calls": [{"id": "call_1", "name": tool_name, "arguments": tool_args}],
                "configured": True, "error": None,
            }
        else:
            return {"content": final_text, "tool_calls": [], "configured": True, "error": None}
    gateway = MagicMock()
    gateway.is_configured.return_value = True
    gateway.complete = AsyncMock(side_effect=mock_complete)
    return gateway


class TestShipwrightEngine:
    @pytest.mark.asyncio
    async def test_simple_text_response(self, db_session: AsyncSession) -> None:
        registry = _setup_registry()
        gateway = _mock_llm_text_response("Hello! I'm the Shipwright.")

        engine = ShipwrightEngine(
            session=db_session, gateway=gateway, registry=registry,
            username="test_user", role="helmsman", plank_scopes=[],
        )
        response = await engine.chat("Hello")
        assert response["message"] == "Hello! I'm the Shipwright."
        assert response["tool_calls_executed"] == []

    @pytest.mark.asyncio
    async def test_tool_call_creates_entity(self, db_session: AsyncSession) -> None:
        registry = _setup_registry()
        gateway = _mock_llm_tool_then_text(
            tool_name="create_entity",
            tool_args={"plank": "contacts", "entity": "Contact",
                       "data": {"name": "AI Created Corp", "contact_type": "customer"}},
            final_text="I've created the contact 'AI Created Corp'.",
        )

        engine = ShipwrightEngine(
            session=db_session, gateway=gateway, registry=registry,
            username="test_user", role="helmsman", plank_scopes=[],
        )
        response = await engine.chat("Create a contact named AI Created Corp")
        assert "AI Created Corp" in response["message"]
        assert len(response["tool_calls_executed"]) == 1
        assert response["tool_calls_executed"][0]["tool"] == "create_entity"
        assert response["tool_calls_executed"][0]["success"] is True

    @pytest.mark.asyncio
    async def test_conversation_persists_messages(self, db_session: AsyncSession) -> None:
        registry = _setup_registry()
        gateway = _mock_llm_text_response("Hi there!")

        engine = ShipwrightEngine(
            session=db_session, gateway=gateway, registry=registry,
            username="test_user", role="helmsman", plank_scopes=[],
        )
        response = await engine.chat("Hello")
        assert response["conversation_id"] is not None

        # Second message in same conversation
        response2 = await engine.chat(
            "How are you?",
            conversation_id=uuid.UUID(response["conversation_id"]),
        )
        assert response2["conversation_id"] == response["conversation_id"]

    @pytest.mark.asyncio
    async def test_not_configured_returns_fallback(self, db_session: AsyncSession) -> None:
        registry = _setup_registry()
        gateway = MagicMock()
        gateway.is_configured.return_value = False

        engine = ShipwrightEngine(
            session=db_session, gateway=gateway, registry=registry,
            username="test_user", role="helmsman", plank_scopes=[],
        )
        response = await engine.chat("Hello")
        assert "not configured" in response["message"].lower() or "no AI" in response["message"].lower()
