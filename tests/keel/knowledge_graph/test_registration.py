from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.knowledge_graph.registration import register_blueprints_in_graph

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "blueprints" / "_test"


class TestRegisterBlueprintsInGraph:
    @pytest.mark.asyncio
    async def test_registers_entity_types(self, db_session: AsyncSession) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for bp in parser.parse_directory(FIXTURES_DIR):
            registry.register(bp)

        graph = PostgresKnowledgeGraph(session=db_session)
        await register_blueprints_in_graph(registry, graph)

        widget = await graph.get_entity_type("test.Widget")
        assert widget is not None
        assert widget.entity == "Widget"

        order = await graph.get_entity_type("test.WidgetOrder")
        assert order is not None
        assert order.entity == "WidgetOrder"

    @pytest.mark.asyncio
    async def test_registers_relationships(self, db_session: AsyncSession) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for bp in parser.parse_directory(FIXTURES_DIR):
            registry.register(bp)

        graph = PostgresKnowledgeGraph(session=db_session)
        await register_blueprints_in_graph(registry, graph)

        # WidgetOrder has relations to test.Widget and contacts.Contact
        related = await graph.get_related_types("test.WidgetOrder")
        related_names = {r.full_name for r in related}
        # test.Widget should be registered and connected
        assert "test.Widget" in related_names

    @pytest.mark.asyncio
    async def test_idempotent_registration(self, db_session: AsyncSession) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for bp in parser.parse_directory(FIXTURES_DIR):
            registry.register(bp)

        graph = PostgresKnowledgeGraph(session=db_session)
        await register_blueprints_in_graph(registry, graph)
        # Run again — should not raise
        await register_blueprints_in_graph(registry, graph)

        widget = await graph.get_entity_type("test.Widget")
        assert widget is not None
