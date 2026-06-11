from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.inventory.service import InventoryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MakerService:
    """Domain service for the Maker Plank: entity create-helpers + costing + production.

    House style: async session injected; raw parametrized SQL; flush (not commit) so the
    caller controls the transaction; events emitted via emit_entity_event.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresEventStore(session=session)
        self._inventory = InventoryService(session=session)

    # ---- entity create-helpers (FK-aware; the generic router cannot set FKs) ----

    async def create_material(self, *, sku: str, name: str, unit: str = "each") -> dict[str, Any]:
        """A material is an inventory StockItem with category 'raw_material'."""
        return await self._inventory.create_stock_item(
            sku=sku, name=name, category="raw_material", unit_of_measure=unit,
        )

    async def create_finished_good(
        self, *, sku: str, name: str, unit: str = "each"
    ) -> dict[str, Any]:
        """A variation's sellable stock is an inventory StockItem with category 'finished_good'."""
        return await self._inventory.create_stock_item(
            sku=sku, name=name, category="finished_good", unit_of_measure=unit,
        )

    async def create_recipe(
        self, *, labor_minutes: float = 0, labor_rate_per_hour: float = 0
    ) -> dict[str, Any]:
        recipe_id = uuid.uuid4()
        params = {
            "id": recipe_id,
            "labor_minutes": labor_minutes,
            "labor_rate_per_hour": labor_rate_per_hour,
        }
        query = text(
            "INSERT INTO maker_recipe (id, labor_minutes, labor_rate_per_hour) "
            "VALUES (:id, :labor_minutes, :labor_rate_per_hour) RETURNING *"
        )
        result = await self._session.execute(query, params)
        await emit_entity_event(
            store=self._store, action="created", plank="maker", entity="Recipe",
            entity_id=recipe_id,
            data={
                "id": str(recipe_id),
                "labor_minutes": labor_minutes,
                "labor_rate_per_hour": labor_rate_per_hour,
            },
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def add_recipe_line(
        self, *, recipe_id: uuid.UUID, material_id: uuid.UUID, qty_per_unit: float
    ) -> dict[str, Any]:
        line_id = uuid.uuid4()
        params = {
            "id": line_id,
            "recipe_id": recipe_id,
            "material_id": material_id,
            "qty_per_unit": qty_per_unit,
        }
        query = text(
            "INSERT INTO maker_recipe_line (id, recipe_id, material_id, qty_per_unit) "
            "VALUES (:id, :recipe_id, :material_id, :qty_per_unit) RETURNING *"
        )
        result = await self._session.execute(query, params)
        await emit_entity_event(
            store=self._store, action="created", plank="maker", entity="RecipeLine",
            entity_id=line_id,
            data={
                "recipe_id": str(recipe_id),
                "material_id": str(material_id),
                "qty_per_unit": qty_per_unit,
            },
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def create_variation(
        self, *, sku: str, base_price: float,
        finished_stock_id: uuid.UUID | None = None,
        recipe_id: uuid.UUID | None = None,
        product_version_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        var_id = uuid.uuid4()
        params: dict[str, Any] = {"id": var_id, "sku": sku, "base_price": base_price}
        if finished_stock_id is not None:
            params["finished_stock_id"] = finished_stock_id
        if recipe_id is not None:
            params["recipe_id"] = recipe_id
        if product_version_id is not None:
            params["product_version_id"] = product_version_id
        col_names = ", ".join(params)
        col_params = ", ".join(f":{k}" for k in params)
        query = text(f"INSERT INTO maker_variation ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)
        await emit_entity_event(
            store=self._store, action="created", plank="maker", entity="Variation",
            entity_id=var_id,
            data={k: str(v) if isinstance(v, uuid.UUID) else v for k, v in params.items()},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())


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
