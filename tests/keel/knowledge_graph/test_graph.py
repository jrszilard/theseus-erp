import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph


@pytest.fixture
def graph(db_session: AsyncSession) -> PostgresKnowledgeGraph:
    return PostgresKnowledgeGraph(session=db_session)


class TestPostgresKnowledgeGraph:
    @pytest.mark.asyncio
    async def test_register_entity_type(self, graph: PostgresKnowledgeGraph) -> None:
        node = await graph.register_entity_type(plank="inventory", entity="StockItem", description="A trackable inventory item")
        assert node.plank == "inventory"
        assert node.entity == "StockItem"
        assert node.full_name == "inventory.StockItem"

    @pytest.mark.asyncio
    async def test_register_relationship_type(self, graph: PostgresKnowledgeGraph) -> None:
        await graph.register_entity_type("inventory", "StockItem", "Item")
        await graph.register_entity_type("contacts", "Contact", "Contact")
        edge = await graph.register_relationship_type(source="inventory.StockItem", target="contacts.Contact", relation_name="suppliers", relation_type="many_to_many")
        assert edge.source_full_name == "inventory.StockItem"
        assert edge.target_full_name == "contacts.Contact"

    @pytest.mark.asyncio
    async def test_get_entity_type(self, graph: PostgresKnowledgeGraph) -> None:
        await graph.register_entity_type("test", "Widget", "A widget")
        result = await graph.get_entity_type("test.Widget")
        assert result is not None
        assert result.entity == "Widget"

    @pytest.mark.asyncio
    async def test_get_related_types(self, graph: PostgresKnowledgeGraph) -> None:
        await graph.register_entity_type("inventory", "StockItem", "Item")
        await graph.register_entity_type("contacts", "Contact", "Contact")
        await graph.register_entity_type("invoicing", "InvoiceLine", "Line")
        await graph.register_relationship_type("inventory.StockItem", "contacts.Contact", "suppliers", "many_to_many")
        await graph.register_relationship_type("invoicing.InvoiceLine", "inventory.StockItem", "product", "many_to_one")
        related = await graph.get_related_types("inventory.StockItem")
        related_names = {r.full_name for r in related}
        assert "contacts.Contact" in related_names
        assert "invoicing.InvoiceLine" in related_names

    @pytest.mark.asyncio
    async def test_get_types_by_plank(self, graph: PostgresKnowledgeGraph) -> None:
        await graph.register_entity_type("inventory", "StockItem", "Item")
        await graph.register_entity_type("inventory", "Warehouse", "Warehouse")
        await graph.register_entity_type("contacts", "Contact", "Contact")
        types = await graph.get_types_by_plank("inventory")
        names = {t.entity for t in types}
        assert names == {"StockItem", "Warehouse"}
