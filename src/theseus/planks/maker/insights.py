from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from theseus.planks.maker.service import MakerService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MAKE_MORE_WINDOW_DAYS = 60


class MakerInsights:
    """Deterministic, read-only maker intelligence. No LLM.

    'Running low' = on_hand <= reorder_point.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._svc = MakerService(session=session)

    async def make_more(self, design_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await self._session.execute(text(
            "SELECT v.id, v.sku, si.reorder_point "
            "FROM maker_variation v "
            "JOIN maker_product_version pv ON pv.id = v.product_version_id "
            "JOIN maker_product p ON p.id = pv.product_id "
            "LEFT JOIN inventory_stock_item si ON si.id = v.finished_stock_id "
            "WHERE p.design_id = :d ORDER BY v.sku"
        ), {"d": design_id})).mappings().all()

        out: list[dict[str, Any]] = []
        for r in rows:
            on_hand = await self._svc.variation_on_hand(r["id"])
            reorder = float(r["reorder_point"] or 0)
            buildable = await self._svc.buildable_now(r["id"])
            sold = (await self._session.execute(text(
                "SELECT COALESCE(SUM(quantity),0) FROM maker_sale "
                "WHERE variation_id = :v AND sale_date >= now() - make_interval(days => :w)"
            ), {"v": r["id"], "w": MAKE_MORE_WINDOW_DAYS})).scalar()
            sold_60d = float(sold or 0)
            running_low = on_hand <= reorder
            if not running_low and sold_60d == 0:
                continue
            out.append({
                "variation_id": str(r["id"]), "label": r["sku"], "on_hand": on_hand,
                "reorder_point": reorder, "buildable_now": buildable, "sold_60d": sold_60d,
                "running_low": running_low,
                "nudge": (
                    f"{r['sku']}: {on_hand:g} on hand"
                    + (" (running low)" if running_low else "")
                    + f" · sold {sold_60d:g} in {MAKE_MORE_WINDOW_DAYS}d"
                    + f" · {buildable} buildable"
                ),
            })
        out.sort(key=lambda x: (not x["running_low"], -x["sold_60d"]))
        return out

    async def restock(self, warehouse_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        rows = (await self._session.execute(text(
            "SELECT id, name, reorder_point FROM inventory_stock_item "
            "WHERE category = 'raw_material' AND is_active = true ORDER BY name"
        ))).mappings().all()
        out: list[dict[str, Any]] = []
        for r in rows:
            on_hand = await self._svc._inventory.get_stock_level(r["id"])
            reorder = float(r["reorder_point"] or 0)
            if on_hand > reorder:
                continue
            out.append({"material_id": str(r["id"]), "name": r["name"], "on_hand": on_hand,
                        "reorder_point": reorder,
                        "nudge": f"{r['name']}: {on_hand:g} on hand (reorder at {reorder:g})"})
        return out

    async def version_compare(self, product_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await self._session.execute(text(
            "SELECT pv.id, pv.number, pv.status, "
            "COALESCE(SUM(s.quantity),0) AS units, "
            "COALESCE(SUM(s.quantity * s.unit_price),0) AS revenue "
            "FROM maker_product_version pv "
            "LEFT JOIN maker_variation v ON v.product_version_id = pv.id "
            "LEFT JOIN maker_sale s ON s.variation_id = v.id "
            "WHERE pv.product_id = :p GROUP BY pv.id, pv.number, pv.status ORDER BY pv.number"
        ), {"p": product_id})).mappings().all()
        return [{"version_id": str(r["id"]), "number": r["number"], "status": r["status"],
                 "units": float(r["units"]), "revenue": float(r["revenue"])} for r in rows]
