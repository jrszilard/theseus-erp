import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.inventory.service import InventoryService


class TestInventoryService:
    @pytest.mark.asyncio
    async def test_create_stock_item(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(
            sku="STEEL-001",
            name="Steel Sheet 4x8",
            category="raw_material",
        )
        assert item["sku"] == "STEEL-001"
        assert item["name"] == "Steel Sheet 4x8"
        assert "id" in item

    @pytest.mark.asyncio
    async def test_create_warehouse(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        wh = await svc.create_warehouse(name="Main Warehouse", code="WH-01")
        assert wh["name"] == "Main Warehouse"
        assert wh["code"] == "WH-01"

    @pytest.mark.asyncio
    async def test_record_stock_movement(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(sku="BOLT-100", name="Bolts", category="component")
        wh = await svc.create_warehouse(name="Test WH", code="TWH-01")

        movement = await svc.record_movement(
            stock_item_id=uuid.UUID(item["id"]),
            warehouse_id=uuid.UUID(wh["id"]),
            movement_type="received",
            quantity=100,
            reference="PO-001",
        )
        assert movement["movement_type"] == "received"
        assert float(movement["quantity"]) == 100

    @pytest.mark.asyncio
    async def test_movement_emits_event(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(sku="NUT-200", name="Nuts", category="component")
        wh = await svc.create_warehouse(name="Event WH", code="EWH-01")

        await svc.record_movement(
            stock_item_id=uuid.UUID(item["id"]),
            warehouse_id=uuid.UUID(wh["id"]),
            movement_type="received",
            quantity=50,
        )

        store = PostgresEventStore(session=db_session)
        events = await store.get_events_by_type("inventory.StockMovement.created")
        assert len(events) >= 1
        latest = events[-1]
        assert float(latest.data["quantity"]) == 50

    @pytest.mark.asyncio
    async def test_compute_stock_level(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(sku="WASHER-300", name="Washers", category="component")
        wh = await svc.create_warehouse(name="Stock WH", code="SWH-01")

        item_id = uuid.UUID(item["id"])
        wh_id = uuid.UUID(wh["id"])

        # Receive 100
        await svc.record_movement(
            stock_item_id=item_id, warehouse_id=wh_id,
            movement_type="received", quantity=100,
        )
        # Ship 30
        await svc.record_movement(
            stock_item_id=item_id, warehouse_id=wh_id,
            movement_type="shipped", quantity=-30,
        )
        # Adjust +5
        await svc.record_movement(
            stock_item_id=item_id, warehouse_id=wh_id,
            movement_type="adjusted", quantity=5,
        )

        level = await svc.get_stock_level(item_id)
        assert level == 75  # 100 - 30 + 5

    @pytest.mark.asyncio
    async def test_stock_level_zero_when_no_movements(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(sku="EMPTY-001", name="Empty Item", category="finished_good")
        level = await svc.get_stock_level(uuid.UUID(item["id"]))
        assert level == 0
