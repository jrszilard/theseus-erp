from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

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
