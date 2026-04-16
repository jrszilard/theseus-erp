"""End-to-end Shipwright test: natural language → tool calls → database changes.

Uses a mock LLM to simulate the conversation, but the tool execution
and database operations are real.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.api.dependencies import set_registry
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.event_store.store import PostgresEventStore
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
                    pass
    set_registry(registry)
    return registry


class TestShipwrightEndToEnd:
    @pytest.mark.asyncio
    async def test_create_contact_via_shipwright(self, db_session: AsyncSession) -> None:
        """Simulate: user says 'Create a customer contact for Acme Corp'
        → LLM returns create_entity tool call
        → tool executes against real DB
        → LLM summarizes result
        → contact exists in database
        """
        registry = _setup_registry()

        call_count = 0
        async def mock_complete(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": None, "configured": True, "error": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "name": "create_entity",
                        "arguments": {
                            "plank": "contacts", "entity": "Contact",
                            "data": {"name": "Acme Corp", "contact_type": "customer",
                                     "email": "info@acme.com"},
                        },
                    }],
                }
            return {
                "content": "Done! I've created Acme Corp as a customer contact.",
                "tool_calls": [], "configured": True, "error": None,
            }

        gateway = MagicMock()
        gateway.is_configured.return_value = True
        gateway.complete = AsyncMock(side_effect=mock_complete)

        engine = ShipwrightEngine(
            session=db_session, gateway=gateway, registry=registry,
            username="test_user", role="helmsman", plank_scopes=[],
        )

        response = await engine.chat("Create a customer contact for Acme Corp with email info@acme.com")
        assert "Acme Corp" in response["message"]
        assert len(response["tool_calls_executed"]) == 1
        assert response["tool_calls_executed"][0]["success"] is True

        # Verify the contact actually exists in the database
        result = await db_session.execute(
            text("SELECT * FROM contacts_contact WHERE name = 'Acme Corp'")
        )
        row = result.mappings().one_or_none()
        assert row is not None
        assert row["email"] == "info@acme.com"
        assert row["contact_type"] == "customer"

        # Verify event was emitted
        store = PostgresEventStore(session=db_session)
        events = await store.get_events_by_type("contacts.Contact.created")
        acme_events = [e for e in events if e.data.get("name") == "Acme Corp"]
        assert len(acme_events) >= 1

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, db_session: AsyncSession) -> None:
        """Simulate a multi-turn conversation where the user creates then queries."""
        registry = _setup_registry()

        call_count = 0
        async def mock_complete(**kwargs):
            nonlocal call_count
            call_count += 1
            messages = kwargs.get("messages", [])
            last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)

            if call_count == 1:
                # First turn: create a contact
                return {
                    "content": None, "configured": True, "error": None,
                    "tool_calls": [{
                        "id": "call_1", "name": "create_entity",
                        "arguments": {"plank": "contacts", "entity": "Contact",
                                      "data": {"name": "Multi Turn Corp", "contact_type": "supplier"}},
                    }],
                }
            elif call_count == 2:
                return {
                    "content": "Created Multi Turn Corp as a supplier.",
                    "tool_calls": [], "configured": True, "error": None,
                }
            elif call_count == 3:
                # Second turn: search contacts
                return {
                    "content": None, "configured": True, "error": None,
                    "tool_calls": [{
                        "id": "call_2", "name": "search_contacts",
                        "arguments": {"name_contains": "Multi Turn"},
                    }],
                }
            else:
                return {
                    "content": "I found Multi Turn Corp — a supplier contact.",
                    "tool_calls": [], "configured": True, "error": None,
                }

        gateway = MagicMock()
        gateway.is_configured.return_value = True
        gateway.complete = AsyncMock(side_effect=mock_complete)

        engine = ShipwrightEngine(
            session=db_session, gateway=gateway, registry=registry,
            username="test_user", role="helmsman", plank_scopes=[],
        )

        # Turn 1: create
        r1 = await engine.chat("Create a supplier contact called Multi Turn Corp")
        assert r1["tool_calls_executed"][0]["success"] is True
        conv_id = r1["conversation_id"]

        # Turn 2: search (same conversation)
        r2 = await engine.chat("Find that contact", conversation_id=uuid.UUID(conv_id))
        assert r2["conversation_id"] == conv_id
        assert any(tc["tool"] == "search_contacts" for tc in r2["tool_calls_executed"])
