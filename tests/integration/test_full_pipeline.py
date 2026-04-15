"""End-to-end integration test: Blueprint -> Schema -> Entity -> Event -> Graph."""
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.event_store.store import PostgresEventStore
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.schema_engine.generator import SchemaGenerator

FIXTURES_DIR = Path(__file__).parent.parent.parent / "blueprints" / "_test"


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_blueprint_to_entity_to_event_to_graph(self, db_session: AsyncSession) -> None:
        parser = BlueprintFileParser()
        bp = parser.parse_file(FIXTURES_DIR / "simple-entity.blueprint.yaml")
        assert bp.entity == "Widget"

        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        assert table.name == "test_widget"

        graph = PostgresKnowledgeGraph(session=db_session)
        node = await graph.register_entity_type(plank=bp.plank, entity=bp.entity, description=bp.description)
        assert node.full_name == "test.Widget"

        entity_id = uuid.uuid4()
        await db_session.execute(text(
            "INSERT INTO test_widget (id, name, color, weight, is_active) "
            "VALUES (:id, :name, :color, :weight, :is_active)"),
            {"id": entity_id, "name": "Integration Widget", "color": "red", "weight": 2.5, "is_active": True})

        event_store = PostgresEventStore(session=db_session)
        event = await event_store.append(event_type="test.WidgetCreated", entity_type="Widget",
            entity_id=entity_id, actor_type="user", actor_id=uuid.uuid4(),
            data={"name": "Integration Widget", "color": "red", "weight": 2.5})
        assert event.event_type == "test.WidgetCreated"

        events = await event_store.get_events_for_entity("Widget", entity_id)
        assert len(events) == 1
        assert events[0].data["name"] == "Integration Widget"

        graph_node = await graph.get_entity_type("test.Widget")
        assert graph_node is not None

    @pytest.mark.asyncio
    async def test_cross_plank_relationship_in_graph(self, db_session: AsyncSession) -> None:
        graph = PostgresKnowledgeGraph(session=db_session)
        await graph.register_entity_type("inventory", "StockItem", "An inventory item")
        await graph.register_entity_type("contacts", "Contact", "A business contact")
        edge = await graph.register_relationship_type(
            source="inventory.StockItem", target="contacts.Contact",
            relation_name="suppliers", relation_type="many_to_many")
        assert edge.relation_name == "suppliers"

        stock_related = await graph.get_related_types("inventory.StockItem")
        assert any(r.full_name == "contacts.Contact" for r in stock_related)
        contact_related = await graph.get_related_types("contacts.Contact")
        assert any(r.full_name == "inventory.StockItem" for r in contact_related)
