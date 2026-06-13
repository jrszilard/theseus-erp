import uuid

import pytest_asyncio
from sqlalchemy import text

from theseus.planks.maker.service import MakerService


@pytest_asyncio.fixture(loop_scope="session")
async def maker_seed(db_session):
    """A small but complete maker graph (idempotent)."""
    async def _scalar(sql: str, **params):
        return (await db_session.execute(text(sql), params)).scalar()

    existing = await _scalar("SELECT id FROM maker_design WHERE slug = 'loon'")
    if existing is not None:
        version_id = await _scalar(
            "SELECT pv.id FROM maker_product_version pv "
            "JOIN maker_product p ON p.id = pv.product_id "
            "WHERE p.design_id = :d AND pv.status = 'current'",
            d=existing,
        )
        return {
            "design_id": str(existing),
            "product_id": str(
                await _scalar("SELECT id FROM maker_product WHERE design_id = :d", d=existing)
            ),
            "version_id": str(version_id),
            "variation_id": str(
                await _scalar("SELECT id FROM maker_variation WHERE sku = '8x10'")
            ),
            "material_id": str(
                await _scalar("SELECT id FROM inventory_stock_item WHERE sku = 'SEED-CARD'")
            ),
            "channel_id": str(
                await _scalar("SELECT id FROM maker_channel WHERE name = 'Etsy'")
            ),
            "market_event_id": str(
                await _scalar(
                    "SELECT id FROM maker_market_event WHERE name = 'May Lakeside Fair'"
                )
            ),
            "warehouse_id": str(
                await _scalar("SELECT id FROM inventory_warehouse WHERE code = 'SEED-STUDIO'")
            ),
            "draft_version_id": str(await _scalar(
                "SELECT id FROM maker_product_version WHERE status='draft' "
                "AND product_id=(SELECT id FROM maker_product WHERE design_id=:d)", d=existing)),
        }

    svc = MakerService(session=db_session)

    wh = await svc._inventory.create_warehouse(name="Studio", code="SEED-STUDIO")
    wid = uuid.UUID(wh["id"])

    card = await svc.create_material(sku="SEED-CARD", name="Cardstock 8x10", unit="sheet")
    card_id = uuid.UUID(card["id"])
    await svc.record_material_purchase(
        material_id=card_id, quantity=100, unit_cost=0.42, warehouse_id=wid
    )

    fmt_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO maker_format (id, name, default_unit) VALUES (:i,:n,'each')"),
        {"i": fmt_id, "n": "Print"},
    )

    ch_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO maker_channel (id, name, fee_percent, fee_fixed, is_active) "
            "VALUES (:i,'Etsy',6.5,0.20,true)"
        ),
        {"i": ch_id},
    )

    design_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO maker_design (id, title, slug, status) "
            "VALUES (:i,'Loon on Blue Lake','loon',:s)"
        ),
        {"i": design_id, "s": "released"},
    )
    product_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO maker_product (id, name, design_id, format_id) "
            "VALUES (:i,'Loon Print',:d,:f)"
        ),
        {"i": product_id, "d": design_id, "f": fmt_id},
    )
    version_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO maker_product_version (id, number, status, product_id) "
            "VALUES (:i,1,'current',:p)"
        ),
        {"i": version_id, "p": product_id},
    )

    recipe = await svc.create_recipe(labor_minutes=15, labor_rate_per_hour=15.44)
    await svc.add_recipe_line(
        recipe_id=uuid.UUID(recipe["id"]), material_id=card_id, qty_per_unit=1
    )
    finished = await svc.create_finished_good(sku="SEED-FG-8x10", name="Loon Print 8x10")
    var = await svc.create_variation(
        sku="8x10",
        base_price=25.0,
        recipe_id=uuid.UUID(recipe["id"]),
        finished_stock_id=uuid.UUID(finished["id"]),
        product_version_id=version_id,
    )
    var_id = uuid.UUID(var["id"])
    await svc.run_production(variation_id=var_id, quantity=20, warehouse_id=wid)
    await db_session.execute(
        text(
            "INSERT INTO maker_sale (id, quantity, unit_price, fees, sale_date, source, "
            "variation_id, channel_id) VALUES (:i,18,25.0,0,now(),'manual',:v,:c)"
        ),
        {"i": uuid.uuid4(), "v": var_id, "c": ch_id},
    )
    me_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO maker_market_event (id, name, event_date, location, booth_fee) "
            "VALUES (:i,'May Lakeside Fair', current_date, 'Lakeside', 45)"
        ),
        {"i": me_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO maker_sale (id, quantity, unit_price, fees, sale_date, source, "
            "variation_id, channel_id, market_event_id) "
            "VALUES (:i,3,25.0,0,now(),'manual',:v,:c,:m)"
        ),
        {"i": uuid.uuid4(), "v": var_id, "c": ch_id, "m": me_id},
    )

    draft_version_id = uuid.uuid4()
    await db_session.execute(text(
        "INSERT INTO maker_product_version (id, number, status, product_id) "
        "VALUES (:i, 2, 'draft', :p)"), {"i": draft_version_id, "p": product_id})
    await svc.set_reorder_point(uuid.UUID(finished["id"]), 5)
    await db_session.flush()
    return {
        "design_id": str(design_id),
        "product_id": str(product_id),
        "version_id": str(version_id),
        "variation_id": str(var_id),
        "material_id": str(card_id),
        "channel_id": str(ch_id),
        "market_event_id": str(me_id),
        "warehouse_id": str(wid),
        "draft_version_id": str(draft_version_id),
    }
