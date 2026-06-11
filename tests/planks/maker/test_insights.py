import uuid

import pytest
from sqlalchemy import text

from theseus.planks.maker.insights import MakerInsights
from theseus.planks.maker.service import MakerService


async def _design_with_variation(db_session, *, on_hand, reorder, sold):
    """A design→product→version→variation with finished stock, a reorder point, and N sales."""
    svc = MakerService(session=db_session)
    wh = await svc._inventory.create_warehouse(name="W", code=f"INS-{uuid.uuid4().hex[:6]}")
    wid = uuid.UUID(wh["id"])
    fg = await svc.create_finished_good(
        sku=f"INS-FG-{uuid.uuid4().hex[:6]}", name="FG", reorder_point=reorder
    )
    design_id, product_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    fmt_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO maker_format (id,name,default_unit) VALUES (:i,'F','each')"),
        {"i": fmt_id},
    )
    await db_session.execute(
        text("INSERT INTO maker_design (id,title,slug,status) VALUES (:i,'D',:s,'released')"),
        {"i": design_id, "s": f"d{uuid.uuid4().hex[:6]}"},
    )
    await db_session.execute(
        text("INSERT INTO maker_product (id,name,design_id,format_id) VALUES (:i,'P',:d,:f)"),
        {"i": product_id, "d": design_id, "f": fmt_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO maker_product_version (id,number,status,product_id)"
            " VALUES (:i,1,'current',:p)"
        ),
        {"i": version_id, "p": product_id},
    )
    var = await svc.create_variation(
        sku="INS-8x10", base_price=25.0,
        finished_stock_id=uuid.UUID(fg["id"]),
        product_version_id=version_id,
    )
    vid = uuid.UUID(var["id"])
    await svc.run_production(variation_id=vid, quantity=on_hand, warehouse_id=wid)
    ch_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO maker_channel (id,name,fee_percent,fee_fixed,is_active)"
            " VALUES (:i,'C',0,0,true)"
        ),
        {"i": ch_id},
    )
    for _ in range(int(sold)):
        await svc.record_sale(
            variation_id=vid, channel_id=ch_id, quantity=1,
            unit_price=25.0, source="manual", warehouse_id=wid,
        )
    await db_session.flush()
    return design_id, vid


@pytest.mark.asyncio
async def test_make_more_flags_running_low(db_session) -> None:
    # produced 10, sold 8 -> on_hand 2, reorder 3 -> running low
    design_id, vid = await _design_with_variation(db_session, on_hand=10, reorder=3, sold=8)
    rows = await MakerInsights(session=db_session).make_more(design_id)
    row = next(r for r in rows if r["variation_id"] == str(vid))
    assert row["running_low"] is True
    assert row["on_hand"] == 2
    assert row["sold_60d"] == 8


@pytest.mark.asyncio
async def test_make_more_skips_healthy_unsold(db_session) -> None:
    # produced 50, sold 0, reorder 0 -> not low, no velocity -> not surfaced
    design_id, vid = await _design_with_variation(db_session, on_hand=50, reorder=0, sold=0)
    rows = await MakerInsights(session=db_session).make_more(design_id)
    assert all(r["variation_id"] != str(vid) for r in rows)


@pytest.mark.asyncio
async def test_restock_flags_material_at_or_below_reorder(db_session) -> None:
    svc = MakerService(session=db_session)
    wh = await svc._inventory.create_warehouse(name="W", code=f"RS-{uuid.uuid4().hex[:6]}")
    mat = await svc.create_material(sku=f"RS-{uuid.uuid4().hex[:6]}", name="Card", reorder_point=10)
    await svc.record_material_purchase(material_id=uuid.UUID(mat["id"]), quantity=8,
                                       unit_cost=1.0, warehouse_id=uuid.UUID(wh["id"]))
    rows = await MakerInsights(session=db_session).restock()
    assert any(r["material_id"] == mat["id"] and r["on_hand"] == 8 for r in rows)


@pytest.mark.asyncio
async def test_version_compare_sums_units_and_revenue(db_session) -> None:
    design_id, _vid = await _design_with_variation(db_session, on_hand=10, reorder=0, sold=3)
    product_id = (await db_session.execute(text(
        "SELECT p.id FROM maker_product p JOIN maker_design d ON d.id = p.design_id WHERE d.id = :d"
    ), {"d": design_id})).scalar()
    rows = await MakerInsights(session=db_session).version_compare(product_id)
    assert rows[0]["units"] == 3.0
    assert rows[0]["revenue"] == 75.0  # 3 x 25


@pytest.mark.asyncio
async def test_version_compare_zero_sales_returns_zero(db_session) -> None:
    design_id, _ = await _design_with_variation(db_session, on_hand=5, reorder=0, sold=0)
    product_id = (await db_session.execute(text(
        "SELECT id FROM maker_product WHERE design_id = :d"), {"d": design_id})).scalar()
    rows = await MakerInsights(session=db_session).version_compare(product_id)
    assert rows and rows[0]["units"] == 0.0 and rows[0]["revenue"] == 0.0
