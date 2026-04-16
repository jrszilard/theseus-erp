from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore


class InventoryService:
    """Domain service for the Inventory Plank.

    Stock levels are event-sourced: computed by summing StockMovement quantities
    rather than stored as a static field.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresEventStore(session=session)

    async def create_stock_item(
        self,
        *,
        sku: str,
        name: str,
        category: str,
        unit_of_measure: str = "each",
        reorder_point: float = 0,
    ) -> dict[str, Any]:
        item_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": item_id, "sku": sku, "name": name, "category": category,
            "unit_of_measure": unit_of_measure, "reorder_point": reorder_point,
            "is_active": True,
        }
        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO inventory_stock_item ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="inventory",
            entity="StockItem", entity_id=item_id,
            data={k: str(v) if isinstance(v, uuid.UUID) else v for k, v in params.items()},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def create_warehouse(self, *, name: str, code: str, address: str | None = None) -> dict[str, Any]:
        wh_id = uuid.uuid4()
        params: dict[str, Any] = {"id": wh_id, "name": name, "code": code, "is_active": True}
        if address is not None:
            params["address"] = address
        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO inventory_warehouse ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="inventory",
            entity="Warehouse", entity_id=wh_id,
            data={k: str(v) if isinstance(v, uuid.UUID) else v for k, v in params.items()},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def record_movement(
        self,
        *,
        stock_item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        movement_type: str,
        quantity: float,
        reference: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        movement_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": movement_id, "stock_item_id": stock_item_id,
            "warehouse_id": warehouse_id, "movement_type": movement_type,
            "quantity": quantity,
        }
        if reference is not None:
            params["reference"] = reference
        if notes is not None:
            params["notes"] = notes

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO inventory_stock_movement ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="inventory",
            entity="StockMovement", entity_id=movement_id,
            data={"stock_item_id": str(stock_item_id), "warehouse_id": str(warehouse_id),
                  "movement_type": movement_type, "quantity": quantity,
                  "reference": reference},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def get_stock_level(self, stock_item_id: uuid.UUID) -> float:
        """Compute current stock level by summing all movement quantities.

        This is the event-sourced approach: stock level is derived from
        movements rather than stored as a mutable counter.
        """
        query = text(
            "SELECT COALESCE(SUM(quantity), 0) as total "
            "FROM inventory_stock_movement WHERE stock_item_id = :item_id"
        )
        result = await self._session.execute(query, {"item_id": stock_item_id})
        row = result.mappings().one()
        total = row["total"]
        return float(total) if total else 0.0


def _row_to_dict(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result
