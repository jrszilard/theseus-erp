from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.inventory.service import InventoryService

if TYPE_CHECKING:
    from datetime import datetime

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

    async def create_material(self, *, sku: str, name: str, unit: str = "each",
                              reorder_point: float = 0) -> dict[str, Any]:
        """A material is an inventory StockItem with category 'raw_material'."""
        return await self._inventory.create_stock_item(
            sku=sku, name=name, category="raw_material",
            unit_of_measure=unit, reorder_point=reorder_point,
        )

    async def create_finished_good(
        self, *, sku: str, name: str, unit: str = "each", reorder_point: float = 0
    ) -> dict[str, Any]:
        """A variation's sellable stock is an inventory StockItem with category 'finished_good'."""
        return await self._inventory.create_stock_item(
            sku=sku, name=name, category="finished_good",
            unit_of_measure=unit, reorder_point=reorder_point,
        )

    async def set_reorder_point(self, stock_item_id: uuid.UUID, value: float) -> dict[str, Any]:
        """Update the reorder_point for a stock item (material or finished good)."""
        await self._session.execute(
            text("UPDATE inventory_stock_item SET reorder_point = :r WHERE id = :i"),
            {"r": value, "i": stock_item_id},
        )
        await self._session.flush()
        return {"id": str(stock_item_id), "reorder_point": value}

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

    # ---- material purchases + weighted-average cost (event-sourced) ----

    async def record_material_purchase(
        self, *, material_id: uuid.UUID, quantity: float, unit_cost: float, warehouse_id: uuid.UUID
    ) -> dict[str, Any]:
        """Record buying a lot of a material: emit a purchase event (cost basis) and
        a 'received' inventory movement (on-hand bump)."""
        # entity_id is the material (an event stream per material), not a per-lot id — this is
        # what weighted_average_cost folds over. Do not change to a per-purchase uuid.
        await emit_entity_event(
            store=self._store, action="recorded", plank="maker", entity="MaterialPurchase",
            entity_id=material_id,
            data={"material_id": str(material_id), "quantity": quantity, "unit_cost": unit_cost},
        )
        await self._inventory.record_movement(
            stock_item_id=material_id, warehouse_id=warehouse_id,
            movement_type="received", quantity=quantity, reference="material-purchase",
        )
        await self._session.flush()
        return {"material_id": str(material_id), "quantity": quantity, "unit_cost": unit_cost}

    async def weighted_average_cost(self, material_id: uuid.UUID) -> float:
        """Weighted-average unit cost = sum(qty x unit_cost) / sum(qty) over all purchase lots.

        v1 definition: averages ALL historical purchase lots and does not decay or reset as
        stock is consumed by production. Returns 0.0 when the material has no recorded purchases.
        """
        # Direct query: PostgresEventStore can't filter by event_type AND entity_id in one call.
        query = text(
            "SELECT data FROM events "
            "WHERE event_type = 'maker.MaterialPurchase.recorded' AND entity_id = :mid"
        )
        result = await self._session.execute(query, {"mid": material_id})
        total_qty = Decimal("0")
        total_cost = Decimal("0")
        for row in result.mappings().all():
            data = row["data"]
            qty = Decimal(str(data["quantity"]))
            cost = Decimal(str(data["unit_cost"]))
            total_qty += qty
            total_cost += qty * cost
        if total_qty == 0:
            return 0.0
        return float(total_cost / total_qty)

    # ---- internal helpers ----

    async def _get_variation_row(self, variation_id: uuid.UUID) -> Any:
        """Fetch a variation's recipe_id + finished_stock_id, or None if it doesn't exist."""
        result = await self._session.execute(
            text("SELECT recipe_id, finished_stock_id FROM maker_variation WHERE id = :id"),
            {"id": variation_id},
        )
        return result.mappings().one_or_none()

    # ---- costing ----

    async def unit_cogs(self, variation_id: uuid.UUID) -> float:
        """COGS for one unit = sum(line.qty_per_unit x wac(material)) + labor cost.

        Labor cost = (labor_minutes / 60) x labor_rate_per_hour. Returns 0.0 when the
        variation has no recipe attached.
        """
        var_row = await self._get_variation_row(variation_id)
        if var_row is None or var_row["recipe_id"] is None:
            return 0.0
        recipe_id = var_row["recipe_id"]

        recipe = await self._session.execute(
            text("SELECT labor_minutes, labor_rate_per_hour FROM maker_recipe WHERE id = :id"),
            {"id": recipe_id},
        )
        recipe_row = recipe.mappings().one()
        labor_minutes = Decimal(str(recipe_row["labor_minutes"] or 0))
        labor_rate = Decimal(str(recipe_row["labor_rate_per_hour"] or 0))
        labor_cost = (labor_minutes / Decimal("60")) * labor_rate

        lines = await self._session.execute(
            text("SELECT material_id, qty_per_unit FROM maker_recipe_line WHERE recipe_id = :rid"),
            {"rid": recipe_id},
        )
        material_cost = Decimal("0")
        # One WAC query per line. Fine at maker scale (few lines); batch if recipes grow large.
        for line in lines.mappings().all():
            wac = Decimal(str(await self.weighted_average_cost(line["material_id"])))
            material_cost += Decimal(str(line["qty_per_unit"])) * wac

        return float(material_cost + labor_cost)

    async def buildable_now(self, variation_id: uuid.UUID) -> int:
        """How many units can be made right now = min over recipe lines of
        floor(material on-hand / qty_per_unit). 0 if no recipe or no lines."""
        var_row = await self._get_variation_row(variation_id)
        if var_row is None or var_row["recipe_id"] is None:
            return 0

        lines = await self._session.execute(
            text("SELECT material_id, qty_per_unit FROM maker_recipe_line WHERE recipe_id = :rid"),
            {"rid": var_row["recipe_id"]},
        )
        line_rows = lines.mappings().all()
        if not line_rows:
            return 0

        buildable: int | None = None
        for line in line_rows:
            per_unit = Decimal(str(line["qty_per_unit"]))
            if per_unit <= 0:
                continue
            stock = Decimal(str(await self._inventory.get_stock_level(line["material_id"])))
            possible = int(stock // per_unit)
            buildable = possible if buildable is None else min(buildable, possible)
        return buildable if buildable is not None else 0

    # ---- production ----

    async def variation_on_hand(self, variation_id: uuid.UUID) -> float:
        """Finished-good stock for a variation = stock level of its finished_stock item."""
        var_row = await self._get_variation_row(variation_id)
        if var_row is None or var_row["finished_stock_id"] is None:
            return 0.0
        return await self._inventory.get_stock_level(var_row["finished_stock_id"])

    async def run_production(
        self, *, variation_id: uuid.UUID, quantity: float, warehouse_id: uuid.UUID
    ) -> dict[str, Any]:
        """Make `quantity` units: snapshot unit COGS, consume each material, add finished
        stock, and write an immutable production-run record. Does not block on shortage —
        callers use buildable_now() as the advisory guard."""
        var_row = await self._get_variation_row(variation_id)
        if var_row is None:
            msg = f"Variation {variation_id} not found"
            raise ValueError(msg)

        unit_cogs = await self.unit_cogs(variation_id)
        total_cogs = unit_cogs * quantity

        # Consume materials (negative 'adjusted' movements).
        if var_row["recipe_id"] is not None:
            lines = await self._session.execute(
                text(
                    "SELECT material_id, qty_per_unit FROM maker_recipe_line"
                    " WHERE recipe_id = :rid"
                ),
                {"rid": var_row["recipe_id"]},
            )
            for line in lines.mappings().all():
                consumed = float(line["qty_per_unit"]) * quantity
                await self._inventory.record_movement(
                    stock_item_id=line["material_id"], warehouse_id=warehouse_id,
                    movement_type="adjusted", quantity=-consumed, reference="production-run",
                )

        # Add finished stock (positive 'received' movement).
        if var_row["finished_stock_id"] is not None:
            await self._inventory.record_movement(
                stock_item_id=var_row["finished_stock_id"], warehouse_id=warehouse_id,
                movement_type="received", quantity=quantity, reference="production-run",
            )

        run_id = uuid.uuid4()
        params = {
            "id": run_id, "variation_id": variation_id, "quantity": quantity,
            "unit_cogs_snapshot": unit_cogs, "total_cogs": total_cogs,
        }
        query = text(
            "INSERT INTO maker_production_run "
            "(id, variation_id, quantity, unit_cogs_snapshot, total_cogs, run_date) "
            "VALUES (:id, :variation_id, :quantity, :unit_cogs_snapshot, :total_cogs, now()) "
            "RETURNING *"
        )
        result = await self._session.execute(query, params)
        await emit_entity_event(
            store=self._store, action="recorded", plank="maker", entity="ProductionRun",
            entity_id=run_id,
            data={"variation_id": str(variation_id), "quantity": quantity,
                  "unit_cogs_snapshot": unit_cogs, "total_cogs": total_cogs},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def record_sale(
        self, *, variation_id: uuid.UUID, channel_id: uuid.UUID,
        quantity: float, unit_price: float, source: str,
        market_event_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        sale_date: datetime | None = None,
    ) -> dict[str, Any]:
        """The single sale write-path: validate, compute channel fees, append the
        maker_sale row, decrement finished stock (no oversell block — reality wins),
        and emit a Sale audit event. flush(); the caller commits."""
        var_row = await self._get_variation_row(variation_id)
        if var_row is None:
            msg = f"Variation {variation_id} not found"
            raise ValueError(msg)
        ch = (await self._session.execute(
            text("SELECT fee_percent, fee_fixed FROM maker_channel WHERE id = :c"),
            {"c": channel_id},
        )).mappings().one_or_none()
        if ch is None:
            msg = f"Channel {channel_id} not found"
            raise ValueError(msg)

        gross = quantity * unit_price
        fees = float(round(
            Decimal(str(ch["fee_percent"] or 0)) / 100 * Decimal(str(gross))
            + Decimal(str(ch["fee_fixed"] or 0)), 4))

        sale_id = uuid.uuid4()
        result = await self._session.execute(text(
            "INSERT INTO maker_sale (id, quantity, unit_price, fees, sale_date, source, "
            "variation_id, channel_id, market_event_id) "
            "VALUES (:i, :q, :p, :f, COALESCE(CAST(:d AS timestamptz), now()), :src, :v, :c, :m) "
            "RETURNING *"
        ), {"i": sale_id, "q": quantity, "p": unit_price, "f": fees, "d": sale_date,
            "src": source, "v": variation_id, "c": channel_id, "m": market_event_id})

        if var_row["finished_stock_id"] is not None:
            wh = warehouse_id or (await self._session.execute(
                text("SELECT id FROM inventory_warehouse ORDER BY created_at LIMIT 1")
            )).scalar()
            if wh is not None:
                await self._inventory.record_movement(
                    stock_item_id=var_row["finished_stock_id"], warehouse_id=wh,
                    movement_type="adjusted", quantity=-quantity, reference="sale",
                )

        await emit_entity_event(
            store=self._store, action="recorded", plank="maker", entity="Sale",
            entity_id=sale_id,
            data={"variation_id": str(variation_id), "channel_id": str(channel_id),
                  "quantity": quantity, "unit_price": unit_price, "fees": fees, "source": source},
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
