"""Phase 3 merge point: all three Planks connected via Knowledge Graph.

This is the critical test of Theseus's interconnectivity thesis.
An invoice references a contact (customer) and inventory items (products).
The Knowledge Graph should show all these connections.
"""
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.event_store.store import PostgresEventStore
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.knowledge_graph.registration import register_blueprints_in_graph
from theseus.planks.contacts.service import ContactService
from theseus.planks.inventory.service import InventoryService
from theseus.planks.invoicing.service import InvoicingService

PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"


class TestCrossPlankIntegration:
    @pytest.mark.asyncio
    async def test_full_business_flow(self, db_session: AsyncSession) -> None:
        """Simulate a real business flow: create a customer, receive inventory,
        create an invoice with line items referencing inventory, record payment."""

        contacts = ContactService(session=db_session)
        inventory = InventoryService(session=db_session)
        invoicing = InvoicingService(session=db_session)

        # 1. Create a customer
        customer = await contacts.create_contact(
            name="BuildRight Manufacturing",
            contact_type="customer",
            email="orders@buildright.com",
        )
        customer_id = uuid.UUID(customer["id"])

        # 2. Create inventory items and receive stock
        brackets = await inventory.create_stock_item(
            sku="BRK-001", name="Steel Bracket", category="finished_good",
        )
        coating = await inventory.create_stock_item(
            sku="SVC-COAT", name="Powder Coating Service", category="consumable",
        )
        wh = await inventory.create_warehouse(name="Main Warehouse", code="MAIN")

        brackets_id = uuid.UUID(brackets["id"])
        await inventory.record_movement(
            stock_item_id=brackets_id,
            warehouse_id=uuid.UUID(wh["id"]),
            movement_type="received",
            quantity=500,
            reference="PO-100",
        )

        # 3. Create an invoice
        invoice = await invoicing.create_invoice(
            invoice_number="INV-100",
            customer_id=customer_id,
            issue_date=date(2026, 4, 15),
            due_date=date(2026, 5, 15),
        )
        invoice_id = uuid.UUID(invoice["id"])

        # 4. Add line items (referencing inventory products)
        await invoicing.add_line_item(
            invoice_id=invoice_id,
            description="Steel Brackets x200",
            quantity=200,
            unit_price=4.50,
            product_id=brackets_id,
        )
        await invoicing.add_line_item(
            invoice_id=invoice_id,
            description="Powder Coating",
            quantity=1,
            unit_price=150.00,
            product_id=uuid.UUID(coating["id"]),
        )

        # 5. Compute totals
        totaled = await invoicing.compute_totals(invoice_id, tax_rate=0.07)
        assert float(totaled["subtotal"]) == 1050.0  # 200*4.50 + 150
        assert float(totaled["total"]) == 1123.5  # 1050 + 73.5

        # 6. Record payment
        await invoicing.record_payment(
            invoice_id=invoice_id,
            amount=1123.50,
            payment_date=date(2026, 4, 20),
            payment_method="bank_transfer",
            reference="TXN-9999",
        )

        # 7. Record the shipment (stock goes out)
        await inventory.record_movement(
            stock_item_id=brackets_id,
            warehouse_id=uuid.UUID(wh["id"]),
            movement_type="shipped",
            quantity=-200,
            reference="INV-100",
        )

        # 8. Verify stock level reflects the shipment
        stock_level = await inventory.get_stock_level(brackets_id)
        assert stock_level == 300  # 500 received - 200 shipped

        # 9. Verify the event trail tells the full story
        store = PostgresEventStore(session=db_session)
        all_events = await store.get_events_by_type("invoicing.Invoice.created")
        assert any(e.data.get("invoice_number") == "INV-100" for e in all_events)

        payment_events = await store.get_events_by_type("invoicing.Payment.created")
        assert any(float(e.data.get("amount", 0)) == 1123.5 for e in payment_events)

    @pytest.mark.asyncio
    async def test_knowledge_graph_shows_cross_plank_connections(
        self, db_session: AsyncSession
    ) -> None:
        """Verify the Knowledge Graph registers cross-Plank relationships."""

        # Register all Plank Blueprints in the graph
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for plank_dir in sorted(PLANKS_DIR.iterdir()):
            bp_dir = plank_dir / "blueprints"
            if bp_dir.is_dir():
                for bp in parser.parse_directory(bp_dir):
                    registry.register(bp)

        graph = PostgresKnowledgeGraph(session=db_session)
        await register_blueprints_in_graph(registry, graph)

        # Verify entity types are registered
        contact = await graph.get_entity_type("contacts.Contact")
        assert contact is not None

        stock_item = await graph.get_entity_type("inventory.StockItem")
        assert stock_item is not None

        invoice = await graph.get_entity_type("invoicing.Invoice")
        assert invoice is not None

        # Verify cross-Plank relationships
        # Invoice -> Contact (via customer relation)
        invoice_related = await graph.get_related_types("invoicing.Invoice")
        invoice_related_names = {r.full_name for r in invoice_related}
        assert "contacts.Contact" in invoice_related_names

        # InvoiceLine -> StockItem (via product relation)
        line_related = await graph.get_related_types("invoicing.InvoiceLine")
        line_related_names = {r.full_name for r in line_related}
        assert "inventory.StockItem" in line_related_names
        assert "invoicing.Invoice" in line_related_names

        # StockMovement -> StockItem and Warehouse
        movement_related = await graph.get_related_types("inventory.StockMovement")
        movement_related_names = {r.full_name for r in movement_related}
        assert "inventory.StockItem" in movement_related_names
        assert "inventory.Warehouse" in movement_related_names
