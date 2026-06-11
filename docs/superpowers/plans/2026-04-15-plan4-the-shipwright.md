# Plan 4: The Shipwright (AI Engine) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Shipwright AI engine — the natural language interface that lets users interact with Theseus through conversation. Focus on Operator mode (daily-use CRUD operations via natural language) with the foundation for future modes (Architect, Analyst, Mentor).

**Architecture:** The Shipwright is an agent loop: user message → context assembly → LLM call (via LiteLLM) → tool calls → execute tools against Keel → feed results back → final response. Tools bridge natural language to typed Keel operations. Conversations are persisted in PostgreSQL for multi-turn interactions.

**Tech Stack:** LiteLLM (provider-agnostic LLM gateway), Pydantic v2 (tool schemas + validation), PostgreSQL (conversation storage), FastAPI (chat endpoint).

**Prerequisite:** Plans 1-2 complete. 79 tests passing. Three Planks operational with CRUD, events, and Knowledge Graph.

**Scope for this plan:**
- Full LLM Gateway (replace skeleton)
- Tool definitions and execution for Operator mode
- Context assembly (4-layer system prompt)
- Agent loop with multi-turn tool calling
- Conversation persistence
- Chat API endpoint
- Integration tests with mock LLM

**Deferred to future plans:**
- Architect mode (Blueprint generation from conversation)
- Analyst mode (reporting queries)
- Mentor mode (onboarding guidance)
- Streaming responses / WebSocket
- Quality-aware model routing

---

## File Structure (new files)

```
src/theseus/
  shipwright/
    __init__.py
    engine.py                   # Core agent loop + conversation orchestration
    context.py                  # 4-layer context assembly (system prompt builder)
    tools/
      __init__.py
      definitions.py            # Tool schemas as Pydantic models + OpenAI-format JSON
      executor.py               # Maps tool names to Keel operations, executes them
    conversation/
      __init__.py
      models.py                 # Conversation + Message SQLAlchemy + Pydantic models
      store.py                  # Conversation persistence (save/load)
  keel/
    llm_gateway/
      gateway.py                # REPLACE: full LiteLLM integration
  api/routes/
    shipwright.py               # Chat API endpoint
tests/
  shipwright/
    __init__.py
    test_gateway.py             # LLM Gateway tests (with mock)
    test_tools.py               # Tool definitions + execution tests
    test_context.py             # Context assembly tests
    test_engine.py              # Agent loop tests (with mock LLM)
    test_conversation.py        # Conversation persistence tests
  api/
    test_shipwright_api.py      # Chat endpoint tests
```

---

## Task 1: LLM Gateway — Full LiteLLM Integration

Replace the skeleton with actual LiteLLM calls. Support async completion with tool calling.

**Files:**
- Replace: `src/theseus/keel/llm_gateway/gateway.py`
- Modify: `src/theseus/keel/llm_gateway/protocols.py`
- Create: `tests/shipwright/__init__.py`
- Create: `tests/shipwright/test_gateway.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/shipwright/test_gateway.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/shipwright/test_gateway.py -v
```

- [ ] **Step 3: Update the protocol**

```python
# src/theseus/keel/llm_gateway/protocols.py
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
```

- [ ] **Step 4: Implement the full gateway**

```python
# src/theseus/keel/llm_gateway/gateway.py
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
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/shipwright/test_gateway.py -v
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: full LLM Gateway with LiteLLM integration

Replace skeleton with actual LiteLLM acompletion calls. Supports any
provider (OpenAI, Anthropic, Ollama, etc.) via unified interface.
Handles tool calls extraction, graceful degradation when unconfigured,
and error handling. Constructor accepts explicit provider/model/key
or falls back to settings.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Tool Definitions

Define the tools the Shipwright can call — Pydantic models that generate OpenAI-compatible tool schemas.

**Files:**
- Create: `src/theseus/shipwright/__init__.py`
- Create: `src/theseus/shipwright/tools/__init__.py`
- Create: `src/theseus/shipwright/tools/definitions.py`
- Create: `tests/shipwright/test_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/shipwright/test_tools.py
import pytest

from theseus.shipwright.tools.definitions import (
    CreateEntityTool,
    QueryEntitiesTool,
    GetEntityTool,
    UpdateEntityTool,
    GetStockLevelTool,
    SearchContactsTool,
    get_operator_tools,
)


class TestToolDefinitions:
    def test_create_entity_tool_schema(self) -> None:
        schema = CreateEntityTool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "create_entity"
        assert "plank" in schema["function"]["parameters"]["properties"]
        assert "entity" in schema["function"]["parameters"]["properties"]
        assert "data" in schema["function"]["parameters"]["properties"]

    def test_query_entities_tool_schema(self) -> None:
        schema = QueryEntitiesTool.to_openai_schema()
        assert schema["function"]["name"] == "query_entities"
        assert "plank" in schema["function"]["parameters"]["properties"]

    def test_get_entity_tool_schema(self) -> None:
        schema = GetEntityTool.to_openai_schema()
        assert schema["function"]["name"] == "get_entity"
        assert "entity_id" in schema["function"]["parameters"]["properties"]

    def test_update_entity_tool_schema(self) -> None:
        schema = UpdateEntityTool.to_openai_schema()
        assert schema["function"]["name"] == "update_entity"

    def test_get_stock_level_tool_schema(self) -> None:
        schema = GetStockLevelTool.to_openai_schema()
        assert schema["function"]["name"] == "get_stock_level"
        assert "stock_item_id" in schema["function"]["parameters"]["properties"]

    def test_search_contacts_tool_schema(self) -> None:
        schema = SearchContactsTool.to_openai_schema()
        assert schema["function"]["name"] == "search_contacts"

    def test_get_operator_tools_returns_all(self) -> None:
        tools = get_operator_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 6
        names = {t["function"]["name"] for t in tools}
        assert "create_entity" in names
        assert "query_entities" in names
        assert "get_stock_level" in names
        assert "search_contacts" in names

    def test_tool_schemas_are_valid_openai_format(self) -> None:
        for tool in get_operator_tools():
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
            assert tool["function"]["parameters"]["type"] == "object"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/shipwright/test_tools.py -v
```

- [ ] **Step 3: Implement tool definitions**

```python
# src/theseus/shipwright/tools/definitions.py
"""Tool definitions for the Shipwright.

Each tool is a Pydantic model that validates arguments and generates
OpenAI-compatible function schemas for LLM consumption.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ShipwrightTool(BaseModel):
    """Base class for all Shipwright tools."""

    @classmethod
    def tool_name(cls) -> str:
        raise NotImplementedError

    @classmethod
    def tool_description(cls) -> str:
        raise NotImplementedError

    @classmethod
    def to_openai_schema(cls) -> dict[str, Any]:
        """Generate OpenAI-compatible tool schema from the Pydantic model."""
        schema = cls.model_json_schema()
        # Remove Pydantic metadata keys not needed by OpenAI
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": cls.tool_name(),
                "description": cls.tool_description(),
                "parameters": schema,
            },
        }


class CreateEntityTool(ShipwrightTool):
    """Create a new entity in any Plank."""
    plank: str = Field(description="The plank name (e.g., 'contacts', 'inventory', 'invoicing')")
    entity: str = Field(description="The entity type (e.g., 'Contact', 'StockItem', 'Invoice')")
    data: dict[str, Any] = Field(description="The entity data as key-value pairs")

    @classmethod
    def tool_name(cls) -> str:
        return "create_entity"

    @classmethod
    def tool_description(cls) -> str:
        return "Create a new entity record in the specified plank. Use this for creating contacts, inventory items, invoices, etc."


class QueryEntitiesTool(ShipwrightTool):
    """Query entities from any Plank."""
    plank: str = Field(description="The plank name")
    entity: str = Field(description="The entity type")
    filters: dict[str, Any] = Field(default_factory=dict, description="Optional filters as key-value pairs")

    @classmethod
    def tool_name(cls) -> str:
        return "query_entities"

    @classmethod
    def tool_description(cls) -> str:
        return "List or search entities in a plank. Returns matching records."


class GetEntityTool(ShipwrightTool):
    """Get a specific entity by ID."""
    plank: str = Field(description="The plank name")
    entity: str = Field(description="The entity type")
    entity_id: str = Field(description="The UUID of the entity to retrieve")

    @classmethod
    def tool_name(cls) -> str:
        return "get_entity"

    @classmethod
    def tool_description(cls) -> str:
        return "Get a specific entity by its ID. Returns the full record with all fields."


class UpdateEntityTool(ShipwrightTool):
    """Update an existing entity."""
    plank: str = Field(description="The plank name")
    entity: str = Field(description="The entity type")
    entity_id: str = Field(description="The UUID of the entity to update")
    data: dict[str, Any] = Field(description="The fields to update as key-value pairs")

    @classmethod
    def tool_name(cls) -> str:
        return "update_entity"

    @classmethod
    def tool_description(cls) -> str:
        return "Update fields on an existing entity. Only the provided fields are changed."


class GetStockLevelTool(ShipwrightTool):
    """Get the current stock level for an inventory item."""
    stock_item_id: str = Field(description="The UUID of the stock item")

    @classmethod
    def tool_name(cls) -> str:
        return "get_stock_level"

    @classmethod
    def tool_description(cls) -> str:
        return "Get the current stock level for an inventory item. Computed from movement history."


class SearchContactsTool(ShipwrightTool):
    """Search for contacts by name or type."""
    name_contains: str | None = Field(default=None, description="Search contacts whose name contains this text")
    contact_type: str | None = Field(default=None, description="Filter by contact type: customer, supplier, employee, other")

    @classmethod
    def tool_name(cls) -> str:
        return "search_contacts"

    @classmethod
    def tool_description(cls) -> str:
        return "Search for contacts by name and/or type. Returns matching contact records."


# Registry of all Operator tools
OPERATOR_TOOLS: list[type[ShipwrightTool]] = [
    CreateEntityTool,
    QueryEntitiesTool,
    GetEntityTool,
    UpdateEntityTool,
    GetStockLevelTool,
    SearchContactsTool,
]


def get_operator_tools() -> list[dict[str, Any]]:
    """Get all Operator tool schemas in OpenAI format."""
    return [tool.to_openai_schema() for tool in OPERATOR_TOOLS]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/shipwright/test_tools.py -v
```

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Shipwright tool definitions with OpenAI-compatible schemas

Pydantic-based tool definitions that auto-generate OpenAI function calling
schemas. Operator tools: create_entity, query_entities, get_entity,
update_entity, get_stock_level, search_contacts. Base ShipwrightTool class
provides to_openai_schema() for any tool.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Tool Executor

Map tool names to Keel operations. Execute tools against the real database.

**Files:**
- Create: `src/theseus/shipwright/tools/executor.py`
- Modify: `tests/shipwright/test_tools.py` (add executor tests)

- [ ] **Step 1: Add failing executor tests**

Append to `tests/shipwright/test_tools.py`:

```python
import uuid
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from theseus.shipwright.tools.executor import ToolExecutor


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_create_entity(self, db_session: AsyncSession) -> None:
        executor = ToolExecutor(session=db_session)
        result = await executor.execute(
            tool_name="create_entity",
            arguments={
                "plank": "contacts",
                "entity": "Contact",
                "data": {"name": "Tool Test Corp", "contact_type": "customer"},
            },
        )
        assert result["success"] is True
        assert result["data"]["name"] == "Tool Test Corp"
        assert "id" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_query_entities(self, db_session: AsyncSession) -> None:
        executor = ToolExecutor(session=db_session)
        # Create a contact first
        await executor.execute(
            tool_name="create_entity",
            arguments={
                "plank": "contacts",
                "entity": "Contact",
                "data": {"name": "Query Test Corp", "contact_type": "supplier"},
            },
        )
        result = await executor.execute(
            tool_name="query_entities",
            arguments={"plank": "contacts", "entity": "Contact"},
        )
        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) >= 1

    @pytest.mark.asyncio
    async def test_execute_search_contacts(self, db_session: AsyncSession) -> None:
        executor = ToolExecutor(session=db_session)
        await executor.execute(
            tool_name="create_entity",
            arguments={
                "plank": "contacts",
                "entity": "Contact",
                "data": {"name": "Searchable Inc", "contact_type": "customer"},
            },
        )
        result = await executor.execute(
            tool_name="search_contacts",
            arguments={"name_contains": "Searchable"},
        )
        assert result["success"] is True
        assert len(result["data"]) >= 1

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, db_session: AsyncSession) -> None:
        executor = ToolExecutor(session=db_session)
        result = await executor.execute(
            tool_name="nonexistent_tool",
            arguments={},
        )
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_handles_errors(self, db_session: AsyncSession) -> None:
        executor = ToolExecutor(session=db_session)
        result = await executor.execute(
            tool_name="get_entity",
            arguments={
                "plank": "contacts",
                "entity": "Contact",
                "entity_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert result["success"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/shipwright/test_tools.py::TestToolExecutor -v
```

- [ ] **Step 3: Implement the tool executor**

```python
# src/theseus/shipwright/tools/executor.py
"""Tool executor — bridges Shipwright tool calls to Keel operations."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.api.dependencies import get_blueprint, get_registry
from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.contacts.service import ContactService
from theseus.planks.inventory.service import InventoryService

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes Shipwright tool calls against the Keel and Plank services."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresEventStore(session=session)

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a named tool with the given arguments.

        Returns: {"success": bool, "data": Any, "error": str | None}
        """
        handler = self._get_handler(tool_name)
        if handler is None:
            return {"success": False, "data": None, "error": f"Unknown tool: {tool_name}"}

        try:
            data = await handler(arguments)
            return {"success": True, "data": data, "error": None}
        except Exception as e:
            logger.error("Tool execution error (%s): %s", tool_name, str(e))
            return {"success": False, "data": None, "error": str(e)}

    def _get_handler(self, tool_name: str):
        handlers = {
            "create_entity": self._create_entity,
            "query_entities": self._query_entities,
            "get_entity": self._get_entity,
            "update_entity": self._update_entity,
            "get_stock_level": self._get_stock_level,
            "search_contacts": self._search_contacts,
        }
        return handlers.get(tool_name)

    async def _create_entity(self, args: dict[str, Any]) -> dict[str, Any]:
        plank = args["plank"]
        entity = args["entity"]
        data = args["data"]

        bp = get_blueprint(plank, entity)
        entity_id = uuid.uuid4()

        # Filter to valid Blueprint fields
        valid_fields = set(bp.fields.keys())
        computed = {n for n, f in bp.fields.items() if f.computed}
        columns = {k: v for k, v in data.items() if k in valid_fields and k not in computed}
        columns["id"] = entity_id

        col_names = ", ".join(columns.keys())
        col_params = ", ".join(f":{k}" for k in columns.keys())
        query = text(f"INSERT INTO {bp.table_name} ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, columns)

        await emit_entity_event(
            store=self._store, action="created", plank=plank,
            entity=entity, entity_id=entity_id, data=data,
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def _query_entities(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        plank = args["plank"]
        entity = args["entity"]
        bp = get_blueprint(plank, entity)

        query = text(f"SELECT * FROM {bp.table_name} ORDER BY created_at DESC LIMIT 50")
        result = await self._session.execute(query)
        return [_row_to_dict(row) for row in result.mappings().all()]

    async def _get_entity(self, args: dict[str, Any]) -> dict[str, Any]:
        plank = args["plank"]
        entity = args["entity"]
        entity_id = args["entity_id"]
        bp = get_blueprint(plank, entity)

        query = text(f"SELECT * FROM {bp.table_name} WHERE id = :id")
        result = await self._session.execute(query, {"id": entity_id})
        row = result.mappings().one_or_none()
        if row is None:
            raise ValueError(f"{entity} with id {entity_id} not found")
        return _row_to_dict(row)

    async def _update_entity(self, args: dict[str, Any]) -> dict[str, Any]:
        plank = args["plank"]
        entity = args["entity"]
        entity_id = args["entity_id"]
        data = args["data"]
        bp = get_blueprint(plank, entity)

        valid_fields = set(bp.fields.keys())
        computed = {n for n, f in bp.fields.items() if f.computed}
        columns = {k: v for k, v in data.items() if k in valid_fields and k not in computed}

        set_clause = ", ".join(f"{k} = :{k}" for k in columns.keys())
        columns["id"] = entity_id
        query = text(
            f"UPDATE {bp.table_name} SET {set_clause}, updated_at = now() "
            f"WHERE id = :id RETURNING *"
        )
        result = await self._session.execute(query, columns)
        await emit_entity_event(
            store=self._store, action="updated", plank=plank,
            entity=entity, entity_id=uuid.UUID(entity_id), data=data,
        )
        await self._session.flush()
        row = result.mappings().one_or_none()
        if row is None:
            raise ValueError(f"{entity} with id {entity_id} not found")
        return _row_to_dict(row)

    async def _get_stock_level(self, args: dict[str, Any]) -> dict[str, Any]:
        svc = InventoryService(session=self._session)
        item_id = uuid.UUID(args["stock_item_id"])
        level = await svc.get_stock_level(item_id)
        return {"stock_item_id": args["stock_item_id"], "current_stock": level}

    async def _search_contacts(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        svc = ContactService(session=self._session)
        return await svc.search_contacts(
            name_contains=args.get("name_contains"),
            contact_type=args.get("contact_type"),
        )


def _row_to_dict(row: Any) -> dict[str, Any]:
    from decimal import Decimal
    from datetime import date, datetime
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/shipwright/test_tools.py -v
```

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Shipwright tool executor bridges AI to Keel operations

ToolExecutor maps tool names to Keel/Plank operations: create_entity,
query_entities, get_entity, update_entity, get_stock_level, search_contacts.
Each tool validates arguments, executes against the database, emits events,
and returns structured results. Error handling returns {success: false, error}
instead of throwing.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Context Assembly

Build the 4-layer system prompt that gives the Shipwright business context.

**Files:**
- Create: `src/theseus/shipwright/context.py`
- Create: `tests/shipwright/test_context.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/shipwright/test_context.py
import pytest

from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.shipwright.context import ContextBuilder

from pathlib import Path
PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"


class TestContextBuilder:
    def test_build_keel_context(self) -> None:
        builder = ContextBuilder()
        ctx = builder.build_keel_context()
        assert "Theseus ERP" in ctx
        assert "Shipwright" in ctx
        assert "Plank" in ctx

    def test_build_ship_context_includes_blueprints(self) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for plank_dir in sorted(PLANKS_DIR.iterdir()):
            bp_dir = plank_dir / "blueprints"
            if bp_dir.is_dir():
                for bp in parser.parse_directory(bp_dir):
                    registry.register(bp)

        builder = ContextBuilder(registry=registry)
        ctx = builder.build_ship_context()
        assert "contacts.Contact" in ctx
        assert "inventory.StockItem" in ctx
        assert "invoicing.Invoice" in ctx

    def test_build_crew_context(self) -> None:
        builder = ContextBuilder()
        ctx = builder.build_crew_context(
            username="maria",
            role="bosun",
            plank_scopes=["inventory", "manufacturing"],
        )
        assert "maria" in ctx
        assert "bosun" in ctx
        assert "inventory" in ctx

    def test_build_system_prompt_combines_all_layers(self) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for plank_dir in sorted(PLANKS_DIR.iterdir()):
            bp_dir = plank_dir / "blueprints"
            if bp_dir.is_dir():
                for bp in parser.parse_directory(bp_dir):
                    registry.register(bp)

        builder = ContextBuilder(registry=registry)
        prompt = builder.build_system_prompt(
            username="captain",
            role="helmsman",
            plank_scopes=[],
        )
        # Should contain all layers
        assert "Theseus ERP" in prompt
        assert "contacts.Contact" in prompt
        assert "captain" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/shipwright/test_context.py -v
```

- [ ] **Step 3: Implement context builder**

```python
# src/theseus/shipwright/context.py
"""Context assembly for the Shipwright.

Builds the system prompt from 4 layers:
1. Keel Context (static) — what Theseus is and how it works
2. Ship Context (per-business) — what Blueprints/entities exist
3. Crew Context (per-user) — role, permissions, preferences
4. Voyage Context (per-session) — added dynamically during conversation
"""
from __future__ import annotations

from theseus.keel.blueprint_engine.registry import BlueprintRegistry


class ContextBuilder:
    """Builds the Shipwright's system prompt from layered context."""

    def __init__(self, registry: BlueprintRegistry | None = None) -> None:
        self._registry = registry

    def build_system_prompt(
        self,
        *,
        username: str,
        role: str,
        plank_scopes: list[str],
    ) -> str:
        """Build the complete system prompt combining all context layers."""
        sections = [
            self.build_keel_context(),
            self.build_ship_context(),
            self.build_crew_context(username=username, role=role, plank_scopes=plank_scopes),
        ]
        return "\n\n---\n\n".join(sections)

    def build_keel_context(self) -> str:
        """Layer 1: Static context about what Theseus is."""
        return """You are the Shipwright — the AI assistant for Theseus ERP.

Theseus ERP is an open-source, AI-first ERP for small manufacturing and trade businesses.
Named after the Ship of Theseus: every module (Plank) can be rebuilt, and no two
implementations are alike.

Your role is to help users manage their business operations through natural language.
You can create, query, and update records across all Planks (modules) in the system.

Key terminology:
- Plank = a module (e.g., contacts, inventory, invoicing)
- Blueprint = the YAML definition of an entity type
- Crew = users of the system
- Helmsman = admin, Bosun = department lead, Deckhand = daily user

When users ask you to do something, use the available tools to interact with the system.
Always confirm what you did after completing an action. Be concise and helpful."""

    def build_ship_context(self) -> str:
        """Layer 2: Per-business context — what entities exist."""
        if not self._registry:
            return "No Blueprints are currently loaded."

        lines = ["## Available Entity Types\n"]
        current_plank = ""
        for bp in sorted(self._registry.all(), key=lambda b: b.full_name):
            if bp.plank != current_plank:
                current_plank = bp.plank
                lines.append(f"\n### Plank: {bp.plank}")

            fields_summary = ", ".join(bp.fields.keys())
            lines.append(f"- **{bp.full_name}**: {bp.description}")
            lines.append(f"  Fields: {fields_summary}")

            if bp.relations:
                rels = [f"{name} -> {rel.target}" for name, rel in bp.relations.items()]
                lines.append(f"  Relations: {', '.join(rels)}")

        return "\n".join(lines)

    def build_crew_context(
        self,
        *,
        username: str,
        role: str,
        plank_scopes: list[str],
    ) -> str:
        """Layer 3: Per-user context — role and permissions."""
        lines = [f"## Current User\n"]
        lines.append(f"- Username: {username}")
        lines.append(f"- Role: {role}")

        if role == "helmsman":
            lines.append("- Access: Full access to all Planks")
        elif plank_scopes:
            lines.append(f"- Plank access: {', '.join(plank_scopes)}")
        else:
            lines.append("- Plank access: All Planks")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/shipwright/test_context.py -v
```

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Shipwright context assembly with 4-layer system prompt

ContextBuilder constructs the Shipwright's system prompt from layered
context: Keel (what Theseus is), Ship (what entities exist from Blueprints),
Crew (current user's role and permissions). Voyage layer added dynamically
during conversation. Ship context auto-generates entity summaries from
the BlueprintRegistry.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Conversation Persistence

Store conversations and messages in PostgreSQL for multi-turn interactions.

**Files:**
- Create: `src/theseus/shipwright/conversation/__init__.py`
- Create: `src/theseus/shipwright/conversation/models.py`
- Create: `src/theseus/shipwright/conversation/store.py`
- Create: `tests/shipwright/test_conversation.py`
- Modify: `alembic/env.py` — add conversation model imports

- [ ] **Step 1: Write the failing test**

```python
# tests/shipwright/test_conversation.py
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.shipwright.conversation.store import ConversationStore


class TestConversationStore:
    @pytest.mark.asyncio
    async def test_create_conversation(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        assert conv.id is not None
        assert len(conv.messages) == 0

    @pytest.mark.asyncio
    async def test_add_message(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        msg = await store.add_message(
            conversation_id=conv.id,
            role="user",
            content="Hello Shipwright",
        )
        assert msg.role == "user"
        assert msg.content == "Hello Shipwright"

    @pytest.mark.asyncio
    async def test_add_assistant_message_with_tool_calls(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        msg = await store.add_message(
            conversation_id=conv.id,
            role="assistant",
            content=None,
            tool_calls=[{"id": "call_1", "name": "create_entity", "arguments": {"plank": "contacts"}}],
        )
        assert msg.role == "assistant"
        assert len(msg.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_add_tool_result_message(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        msg = await store.add_message(
            conversation_id=conv.id,
            role="tool",
            content='{"success": true}',
            tool_call_id="call_1",
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_1"

    @pytest.mark.asyncio
    async def test_get_messages(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        await store.add_message(conv.id, "user", "Hello")
        await store.add_message(conv.id, "assistant", "Hi there!")
        await store.add_message(conv.id, "user", "Create a contact")

        messages = await store.get_messages(conv.id)
        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[2].content == "Create a contact"

    @pytest.mark.asyncio
    async def test_get_messages_as_llm_format(self, db_session: AsyncSession) -> None:
        store = ConversationStore(session=db_session)
        conv = await store.create_conversation(crew_member_id=uuid.uuid4())
        await store.add_message(conv.id, "user", "Hello")
        await store.add_message(conv.id, "assistant", "Hi!")

        llm_messages = await store.get_messages_for_llm(conv.id)
        assert llm_messages == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/shipwright/test_conversation.py -v
```

- [ ] **Step 3: Implement conversation models**

```python
# src/theseus/shipwright/conversation/models.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from theseus.database import Base


class Conversation(Base):
    """A conversation between a Crew member and the Shipwright."""
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crew_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Message(Base):
    """A message in a Shipwright conversation."""
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, tool, system
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConversationRecord(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    crew_member_id: uuid.UUID
    messages: list[MessageRecord] = Field(default_factory=list)


class MessageRecord(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str | None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


# Fix forward reference
ConversationRecord.model_rebuild()
```

- [ ] **Step 4: Implement conversation store**

```python
# src/theseus/shipwright/conversation/store.py
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.shipwright.conversation.models import (
    Conversation,
    ConversationRecord,
    Message,
    MessageRecord,
)


class ConversationStore:
    """Persists Shipwright conversations and messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(self, crew_member_id: uuid.UUID) -> ConversationRecord:
        conv = Conversation(crew_member_id=crew_member_id)
        self._session.add(conv)
        await self._session.flush()
        return ConversationRecord(
            id=conv.id,
            crew_member_id=conv.crew_member_id,
            messages=[],
        )

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
    ) -> MessageRecord:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
        )
        self._session.add(msg)
        await self._session.flush()
        return MessageRecord.model_validate(msg)

    async def get_messages(self, conversation_id: uuid.UUID) -> list[MessageRecord]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [MessageRecord.model_validate(m) for m in result.scalars().all()]

    async def get_messages_for_llm(self, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
        """Get messages formatted for LLM consumption (OpenAI message format)."""
        messages = await self.get_messages(conversation_id)
        llm_msgs: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                entry["content"] = msg.content
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            llm_msgs.append(entry)
        return llm_msgs
```

- [ ] **Step 5: Update alembic/env.py to import conversation models**

Add to the model imports section in `alembic/env.py`:
```python
import theseus.shipwright.conversation.models  # noqa: F401
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/shipwright/test_conversation.py -v
```

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Shipwright conversation persistence in PostgreSQL

Conversation and Message models for storing Shipwright chat history.
ConversationStore handles creation, message appending (user, assistant,
tool roles), retrieval, and LLM-format export. Messages support tool_calls
(assistant requesting tool use) and tool_call_id (tool results).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Shipwright Engine — Core Agent Loop

The heart of the Shipwright: orchestrates context → LLM → tools → response.

**Files:**
- Create: `src/theseus/shipwright/engine.py`
- Create: `tests/shipwright/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/shipwright/test_engine.py
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
            conversation_id=response["conversation_id"],
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/shipwright/test_engine.py -v
```

- [ ] **Step 3: Implement the Shipwright engine**

```python
# src/theseus/shipwright/engine.py
"""The Shipwright engine — core agent loop for AI-powered ERP interaction.

Orchestrates: context assembly → LLM call → tool execution → response.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.llm_gateway.gateway import LLMGateway
from theseus.shipwright.context import ContextBuilder
from theseus.shipwright.conversation.store import ConversationStore
from theseus.shipwright.tools.definitions import get_operator_tools
from theseus.shipwright.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # Prevent infinite tool-calling loops


class ShipwrightEngine:
    """The Shipwright — Theseus ERP's AI assistant.

    Handles conversation management, context assembly, LLM interaction,
    and tool execution in an agent loop.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        gateway: LLMGateway,
        registry: BlueprintRegistry,
        username: str,
        role: str,
        plank_scopes: list[str],
    ) -> None:
        self._session = session
        self._gateway = gateway
        self._registry = registry
        self._conversation_store = ConversationStore(session=session)
        self._tool_executor = ToolExecutor(session=session)
        self._context_builder = ContextBuilder(registry=registry)
        self._username = username
        self._role = role
        self._plank_scopes = plank_scopes

    async def chat(
        self,
        user_message: str,
        conversation_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Process a user message and return the Shipwright's response.

        Returns:
            {
                "message": str — the Shipwright's text response,
                "conversation_id": str — UUID of the conversation,
                "tool_calls_executed": list — tools that were called and their results,
            }
        """
        # Check if LLM is configured
        if not self._gateway.is_configured():
            return {
                "message": "The Shipwright is not configured — no AI provider is set up. "
                           "You can still use the traditional UI to manage your data.",
                "conversation_id": None,
                "tool_calls_executed": [],
            }

        # Get or create conversation
        if conversation_id is None:
            conv = await self._conversation_store.create_conversation(
                crew_member_id=uuid.uuid4(),  # TODO: use actual crew member ID from auth
            )
            conversation_id = conv.id

        # Save user message
        await self._conversation_store.add_message(conversation_id, "user", user_message)

        # Build system prompt
        system_prompt = self._context_builder.build_system_prompt(
            username=self._username,
            role=self._role,
            plank_scopes=self._plank_scopes,
        )

        # Get conversation history
        history = await self._conversation_store.get_messages_for_llm(conversation_id)

        # Build messages for LLM
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *history,
        ]

        # Agent loop: LLM → tool calls → execute → feed back → repeat
        tools = get_operator_tools()
        tool_calls_executed: list[dict[str, Any]] = []

        for _round in range(MAX_TOOL_ROUNDS):
            response = await self._gateway.complete(
                messages=messages,
                tools=tools,
                temperature=0.3,
            )

            if response.get("error"):
                logger.error("LLM error: %s", response["error"])
                final_message = "I encountered an error processing your request. Please try again."
                break

            # If no tool calls, we have the final response
            if not response["tool_calls"]:
                final_message = response["content"] or ""
                break

            # Execute tool calls
            # Add assistant message with tool calls to history
            assistant_msg = {"role": "assistant", "content": response["content"], "tool_calls": []}
            for tc in response["tool_calls"]:
                assistant_msg["tool_calls"].append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                })
            messages.append(assistant_msg)

            # Save assistant message with tool calls
            await self._conversation_store.add_message(
                conversation_id, "assistant", response["content"],
                tool_calls=response["tool_calls"],
            )

            # Execute each tool and add results
            for tc in response["tool_calls"]:
                result = await self._tool_executor.execute(tc["name"], tc["arguments"])
                tool_calls_executed.append({
                    "tool": tc["name"],
                    "arguments": tc["arguments"],
                    "success": result["success"],
                    "result": result["data"] if result["success"] else result["error"],
                })

                # Add tool result to messages
                tool_result_content = json.dumps(result, default=str)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result_content,
                })

                # Save tool result message
                await self._conversation_store.add_message(
                    conversation_id, "tool", tool_result_content,
                    tool_call_id=tc["id"],
                )
        else:
            final_message = "I've reached the maximum number of tool calls for this request."

        # Save the final assistant response
        await self._conversation_store.add_message(conversation_id, "assistant", final_message)

        await self._session.flush()

        return {
            "message": final_message,
            "conversation_id": str(conversation_id),
            "tool_calls_executed": tool_calls_executed,
        }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/shipwright/test_engine.py -v
```

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Shipwright engine with agent loop and conversation management

Core agent loop: context assembly → LLM call → tool execution → feed
results back → final response. Supports multi-turn conversations with
persistent history. MAX_TOOL_ROUNDS prevents infinite loops. Graceful
fallback when LLM not configured. Conversation and messages persisted
in PostgreSQL via ConversationStore.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Chat API Endpoint

REST endpoint for Shipwright conversations.

**Files:**
- Create: `src/theseus/api/routes/shipwright.py`
- Create: `tests/api/test_shipwright_api.py`
- Modify: `src/theseus/main.py` — include shipwright router

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_shipwright_api.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/api/test_shipwright_api.py -v
```

- [ ] **Step 3: Implement the chat endpoint**

```python
# src/theseus/api/routes/shipwright.py
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.api.dependencies import get_registry
from theseus.database import get_session
from theseus.keel.llm_gateway.gateway import LLMGateway
from theseus.shipwright.engine import ShipwrightEngine

router = APIRouter(prefix="/api/v1/shipwright", tags=["shipwright"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str | None
    tool_calls_executed: list[dict[str, Any]] = Field(default_factory=list)


def _get_gateway() -> LLMGateway:
    """Get the LLM gateway. Separated for test mocking."""
    return LLMGateway()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    gateway = _get_gateway()
    registry = get_registry()

    conv_id = uuid.UUID(request.conversation_id) if request.conversation_id else None

    engine = ShipwrightEngine(
        session=session,
        gateway=gateway,
        registry=registry,
        username="default_user",  # TODO: get from auth token
        role="helmsman",
        plank_scopes=[],
    )

    result = await engine.chat(request.message, conversation_id=conv_id)
    return ChatResponse(**result)
```

- [ ] **Step 4: Add shipwright router to main.py**

Add to `src/theseus/main.py`:
```python
from theseus.api.routes import entities, health, shipwright

# In create_app():
app.include_router(shipwright.router)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_shipwright_api.py -v
pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Shipwright chat API endpoint

POST /api/v1/shipwright/chat accepts a message and optional conversation_id,
returns the Shipwright's response with any tool calls executed. Uses
ShipwrightEngine for the agent loop. Gateway is injectable for testing.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Integration Test — Shipwright End-to-End

Full conversation test with mock LLM: user asks to create data, Shipwright calls tools, data appears in database.

**Files:**
- Create: `tests/integration/test_shipwright_e2e.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/integration/test_shipwright_e2e.py
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
```

- [ ] **Step 2: Run the integration test**

```bash
pytest tests/integration/test_shipwright_e2e.py -v
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Shipwright end-to-end integration tests

Full conversation tests with mock LLM: user asks to create a contact →
Shipwright calls create_entity tool → contact exists in database → event
emitted. Multi-turn test: create then search in same conversation with
persisted history. Validates the complete pipeline from natural language
to database changes.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Summary

After Plan 4, the following is operational:

| Component | Status |
|-----------|--------|
| LLM Gateway | Full LiteLLM integration, any provider |
| Tool Definitions | 6 Operator tools with OpenAI-compatible schemas |
| Tool Executor | Bridges AI tool calls to Keel/Plank operations |
| Context Assembly | 4-layer system prompt from Blueprints + user role |
| Conversation Persistence | PostgreSQL-backed conversation + message history |
| Shipwright Engine | Agent loop with multi-turn tool calling |
| Chat API | POST /api/v1/shipwright/chat |
| Integration Tests | Full natural language → database change verification |

**The Shipwright can now:**
- Receive natural language requests
- Assemble business context from Blueprints
- Call the LLM with tool definitions
- Execute tool calls against real database
- Persist multi-turn conversations
- Return structured responses with tool execution details

**Deferred to future plans:**
- Architect mode (Blueprint generation from conversation)
- Analyst mode (reporting and analytics queries)
- Mentor mode (user onboarding and training)
- Streaming responses / WebSocket
- Quality-aware model routing (strong model for complex, fast for simple)
- Auth integration (get user from JWT instead of hardcoded)

**Next:** Plan 5 (Adaptive Interface + Hull design system) or Plan 6 (The Drydock migration engine).
