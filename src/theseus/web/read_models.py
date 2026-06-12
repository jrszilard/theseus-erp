from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from theseus.planks.maker.insights import MakerInsights
from theseus.planks.maker.service import MakerService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def list_designs_for_board(session: AsyncSession) -> list[dict[str, Any]]:
    """Each design with the formats it spans and total units sold across its variations."""
    rows = (await session.execute(text(
        "SELECT id, title, slug, status FROM maker_design ORDER BY created_at DESC"
    ))).mappings().all()
    designs: list[dict[str, Any]] = []
    for r in rows:
        did = r["id"]
        formats = (await session.execute(text(
            "SELECT DISTINCT f.name FROM maker_product p "
            "JOIN maker_format f ON f.id = p.format_id "
            "WHERE p.design_id = :d ORDER BY f.name"
        ), {"d": did})).scalars().all()
        sold = (await session.execute(text(
            "SELECT COALESCE(SUM(s.quantity), 0) FROM maker_sale s WHERE s.variation_id IN ("
            "  SELECT v.id FROM maker_variation v "
            "  JOIN maker_product_version pv ON pv.id = v.product_version_id "
            "  JOIN maker_product p ON p.id = pv.product_id WHERE p.design_id = :d)"
        ), {"d": did})).scalar()
        designs.append({
            "id": str(did), "title": r["title"], "slug": r["slug"], "status": r["status"],
            "formats": list(formats), "units_sold": float(sold or 0),
        })
    return designs


async def get_design_detail(session: AsyncSession, design_id: uuid.UUID) -> dict[str, Any] | None:
    design = (await session.execute(text(
        "SELECT id, title, slug, status FROM maker_design WHERE id = :d"
    ), {"d": design_id})).mappings().one_or_none()
    if design is None:
        return None

    svc = MakerService(session=session)
    products = (await session.execute(text(
        "SELECT p.id AS product_id, p.name AS product_name, f.name AS format_name "
        "FROM maker_product p LEFT JOIN maker_format f ON f.id = p.format_id "
        "WHERE p.design_id = :d ORDER BY f.name"
    ), {"d": design_id})).mappings().all()

    product_views: list[dict[str, Any]] = []
    for p in products:
        versions = (await session.execute(text(
            "SELECT id, number, status FROM maker_product_version "
            "WHERE product_id = :p ORDER BY number"
        ), {"p": p["product_id"]})).mappings().all()
        version_views: list[dict[str, Any]] = []
        for ver in versions:
            variations = (await session.execute(text(
                "SELECT id, sku, base_price FROM maker_variation "
                "WHERE product_version_id = :v ORDER BY sku"
            ), {"v": ver["id"]})).mappings().all()
            var_views: list[dict[str, Any]] = []
            for v in variations:
                vid = v["id"]
                cogs = await svc.unit_cogs(vid)
                on_hand = await svc.variation_on_hand(vid)
                price = float(v["base_price"] or 0)
                sold = (await session.execute(text(
                    "SELECT COALESCE(SUM(quantity),0) FROM maker_sale WHERE variation_id = :v"
                ), {"v": vid})).scalar()
                profit = price - cogs
                margin = (profit / price * 100) if price else 0
                var_views.append({
                    "id": str(vid), "sku": v["sku"], "price": price, "cost": cogs,
                    "profit": profit, "margin": margin,
                    "sold": float(sold or 0), "on_hand": on_hand,
                })
            version_views.append({"id": str(ver["id"]), "number": ver["number"],
                                  "status": ver["status"], "variations": var_views})
        product_views.append({"id": str(p["product_id"]), "name": p["product_name"],
                              "format": p["format_name"], "versions": version_views})

    channels = (await session.execute(text(
        "SELECT c.name AS channel, COALESCE(SUM(s.quantity),0) AS units "
        "FROM maker_sale s JOIN maker_channel c ON c.id = s.channel_id "
        "WHERE s.variation_id IN ("
        "  SELECT v.id FROM maker_variation v "
        "  JOIN maker_product_version pv ON pv.id = v.product_version_id "
        "  JOIN maker_product p ON p.id = pv.product_id WHERE p.design_id = :d) "
        "GROUP BY c.name ORDER BY units DESC"
    ), {"d": design_id})).mappings().all()

    insights = MakerInsights(session=session)
    make_more = await insights.make_more(design_id)
    promote = await insights.promotion_candidates(design_id)
    version_rows: list[dict[str, Any]] = []
    for pv in product_views:
        version_rows.append({"product": pv["name"],
                             "versions": await insights.version_compare(uuid.UUID(pv["id"]))})

    return {
        "id": str(design["id"]), "title": design["title"], "status": design["status"],
        "products": product_views,
        "channels": [{"label": c["channel"], "value": float(c["units"])} for c in channels],
        "make_more": make_more,
        "promote": promote,
        "version_compare": version_rows,
    }


async def get_bom_view(session: AsyncSession, variation_id: uuid.UUID) -> dict[str, Any] | None:
    v = (await session.execute(text(
        "SELECT id, sku, base_price, recipe_id FROM maker_variation WHERE id = :v"
    ), {"v": variation_id})).mappings().one_or_none()
    if v is None:
        return None
    svc = MakerService(session=session)

    lines: list[dict[str, Any]] = []
    labor: dict[str, Any] = {"minutes": 0.0, "rate": 0.0, "cost": 0.0}
    if v["recipe_id"] is not None:
        recipe = (await session.execute(text(
            "SELECT labor_minutes, labor_rate_per_hour FROM maker_recipe WHERE id = :r"
        ), {"r": v["recipe_id"]})).mappings().one()
        lm = float(recipe["labor_minutes"] or 0)
        lr = float(recipe["labor_rate_per_hour"] or 0)
        labor = {"minutes": lm, "rate": lr, "cost": lm / 60 * lr}
        line_rows = (await session.execute(text(
            "SELECT rl.material_id, rl.qty_per_unit, si.name AS material, si.reorder_point "
            "FROM maker_recipe_line rl JOIN inventory_stock_item si ON si.id = rl.material_id "
            "WHERE rl.recipe_id = :r"
        ), {"r": v["recipe_id"]})).mappings().all()
        for ln in line_rows:
            stock = await svc._inventory.get_stock_level(ln["material_id"])
            wac = await svc.weighted_average_cost(ln["material_id"])
            qpu = float(ln["qty_per_unit"])
            lines.append({
                "material": ln["material"], "material_id": str(ln["material_id"]),
                "qty_per_unit": qpu, "in_stock": stock, "wac": wac, "line_cost": qpu * wac,
                "reorder_point": float(ln["reorder_point"] or 0),
                "low": stock <= float(ln["reorder_point"] or 0),
            })

    cogs = await svc.unit_cogs(variation_id)
    buildable = await svc.buildable_now(variation_id)
    price = float(v["base_price"] or 0)
    profit = price - cogs
    def _stock_ratio(x: dict[str, Any]) -> float:
        return (x["in_stock"] / x["qty_per_unit"]) if x["qty_per_unit"] else float("inf")

    limiting = min(lines, key=_stock_ratio)["material"] if lines else None

    fg = (await session.execute(text(
        "SELECT si.id, si.reorder_point FROM maker_variation v "
        "JOIN inventory_stock_item si ON si.id = v.finished_stock_id WHERE v.id = :v"
    ), {"v": variation_id})).mappings().one_or_none()

    return {
        "variation_id": str(variation_id), "sku": v["sku"], "lines": lines, "labor": labor,
        "cogs": cogs, "buildable": buildable, "limiting_material": limiting,
        "price": price, "profit": profit,
        "margin": (profit / price * 100) if price else 0,
        "finished_stock_id": str(fg["id"]) if fg else "",
        "finished_reorder_point": float(fg["reorder_point"] or 0) if fg else 0,
    }


async def list_markets(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await session.execute(text(
        "SELECT me.id, me.name, me.event_date, me.location, me.booth_fee, "
        "  COALESCE(SUM(s.quantity * s.unit_price), 0) AS gross "
        "FROM maker_market_event me LEFT JOIN maker_sale s ON s.market_event_id = me.id "
        "GROUP BY me.id ORDER BY me.event_date DESC"
    ))).mappings().all()
    return [{"id": str(r["id"]), "name": r["name"], "date": str(r["event_date"]),
             "location": r["location"], "booth_fee": float(r["booth_fee"] or 0),
             "gross": float(r["gross"] or 0)} for r in rows]


async def search_designs(session: AsyncSession, q: str) -> list[dict[str, Any]]:
    rows = (await session.execute(text(
        "SELECT id, title FROM maker_design WHERE title ILIKE :q ORDER BY title LIMIT 10"
    ), {"q": f"%{q}%"})).mappings().all()
    return [{"id": str(r["id"]), "title": r["title"]} for r in rows]


async def get_market_day(
        session: AsyncSession, market_event_id: uuid.UUID) -> dict[str, Any] | None:
    me = (await session.execute(text(
        "SELECT id, name, event_date, location, booth_fee FROM maker_market_event WHERE id = :m"
    ), {"m": market_event_id})).mappings().one_or_none()
    if me is None:
        return None
    svc = MakerService(session=session)
    sales = (await session.execute(text(
        "SELECT s.id, s.quantity, s.unit_price, s.variation_id, v.sku "
        "FROM maker_sale s JOIN maker_variation v ON v.id = s.variation_id "
        "WHERE s.market_event_id = :m ORDER BY s.sale_date"
    ), {"m": market_event_id})).mappings().all()
    lines, gross, cogs_total = [], 0.0, 0.0
    for s in sales:
        qty, up = float(s["quantity"]), float(s["unit_price"])
        gross += qty * up
        cogs_total += qty * await svc.unit_cogs(s["variation_id"])
        lines.append({"sku": s["sku"], "qty": qty, "price": up, "total": qty * up})
    booth = float(me["booth_fee"] or 0)
    variations = (await session.execute(text(
        "SELECT v.id, v.sku, v.base_price FROM maker_variation v ORDER BY v.sku"
    ))).mappings().all()
    return {
        "id": str(me["id"]), "name": me["name"], "date": str(me["event_date"]),
        "location": me["location"], "booth_fee": booth, "lines": lines,
        "gross": gross, "take_home": gross - booth, "cogs": cogs_total,
        "true_profit": gross - booth - cogs_total,
        "variations": [{"id": str(v["id"]), "label": v["sku"], "price": float(v["base_price"] or 0)}
                       for v in variations],
    }
