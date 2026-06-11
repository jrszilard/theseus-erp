import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_bom_shows_recipe_and_buildable(client, maker_seed) -> None:
    resp = await client.get(f"/bom/{maker_seed['variation_id']}")
    assert resp.status_code == 200
    body = resp.text
    assert "Cardstock 8x10" in body         # material line
    assert "buildable" in body.lower()       # buildable-now shown
    assert "Run" in body                     # production-run action


@pytest.mark.asyncio
async def test_production_run_partial_decrements_stock(client, db_session, maker_seed) -> None:
    vid = maker_seed["variation_id"]
    wid = maker_seed["warehouse_id"]
    resp = await client.post(f"/bom/{vid}/run", data={"quantity": "5", "warehouse_id": wid})
    assert resp.status_code == 200
    body = resp.text
    assert "buildable" in body.lower()
    runs = (await db_session.execute(text(
        "SELECT COUNT(*) FROM maker_production_run WHERE variation_id = :v"
    ), {"v": vid})).scalar()
    assert runs >= 2  # the seed's run + this one


@pytest.mark.asyncio
async def test_bom_404_for_unknown(client) -> None:
    import uuid
    resp = await client.get(f"/bom/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bom_sidebar_shows_restock_when_material_low(client, db_session, maker_seed) -> None:
    import uuid as _uuid

    from theseus.planks.maker.service import MakerService
    mat = maker_seed["material_id"]
    vid = maker_seed["variation_id"]
    # force the seed material below its reorder point
    svc = MakerService(session=db_session)
    await svc.set_reorder_point(_uuid.UUID(mat), 100000)
    await db_session.commit()
    resp = await client.get(f"/bom/{vid}")
    assert resp.status_code == 200
    assert "reorder at" in resp.text.lower()  # the restock nudge rendered in the sidebar


@pytest.mark.asyncio
async def test_set_reorder_updates_low_flag(client, db_session, maker_seed) -> None:
    from sqlalchemy import text
    mat = maker_seed["material_id"]
    vid = maker_seed["variation_id"]
    resp = await client.post(f"/bom/{vid}/reorder",
                             data={"stock_item_id": mat, "value": "9999"}, follow_redirects=True)
    assert resp.status_code == 200
    rp = (await db_session.execute(text(
        "SELECT reorder_point FROM inventory_stock_item WHERE id = :i"), {"i": mat})).scalar()
    assert float(rp) == 9999
