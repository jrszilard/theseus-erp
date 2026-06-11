from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

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

    return {
        "id": str(design["id"]), "title": design["title"], "status": design["status"],
        "products": product_views,
        "channels": [{"label": c["channel"], "value": float(c["units"])} for c in channels],
    }
