import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_create_entity(self, db_session: AsyncSession) -> None:
        from theseus.api.dependencies import set_registry
        from theseus.keel.blueprint_engine.parser import BlueprintFileParser
        from theseus.keel.blueprint_engine.registry import BlueprintRegistry
        from pathlib import Path
        PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"
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

        from theseus.shipwright.tools.executor import ToolExecutor
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
        from theseus.api.dependencies import set_registry
        from theseus.keel.blueprint_engine.parser import BlueprintFileParser
        from theseus.keel.blueprint_engine.registry import BlueprintRegistry
        from pathlib import Path
        PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"
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

        from theseus.shipwright.tools.executor import ToolExecutor
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
        from theseus.api.dependencies import set_registry
        from theseus.keel.blueprint_engine.parser import BlueprintFileParser
        from theseus.keel.blueprint_engine.registry import BlueprintRegistry
        from pathlib import Path
        PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"
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

        from theseus.shipwright.tools.executor import ToolExecutor
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
        from theseus.shipwright.tools.executor import ToolExecutor
        executor = ToolExecutor(session=db_session)
        result = await executor.execute(
            tool_name="nonexistent_tool",
            arguments={},
        )
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_handles_errors(self, db_session: AsyncSession) -> None:
        from theseus.api.dependencies import set_registry
        from theseus.keel.blueprint_engine.parser import BlueprintFileParser
        from theseus.keel.blueprint_engine.registry import BlueprintRegistry
        from pathlib import Path
        PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"
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

        from theseus.shipwright.tools.executor import ToolExecutor
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
