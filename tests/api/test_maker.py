import uuid

import pytest

from theseus.planks.maker.service import MakerService


@pytest.mark.asyncio
async def test_material_cost_endpoint(client, db_session) -> None:
    svc = MakerService(session=db_session)
    wh = await svc._inventory.create_warehouse(name="ApiStudio", code="APISTUDIO")
    material = await svc.create_material(sku="API-MAT-1", name="Cardstock", unit="sheet")
    mid = material["id"]
    await svc.record_material_purchase(
        material_id=uuid.UUID(mid), quantity=100, unit_cost=0.25, warehouse_id=uuid.UUID(wh["id"]),
    )
    await db_session.commit()

    resp = await client.get(f"/api/v1/maker/materials/{mid}/cost")
    assert resp.status_code == 200
    assert resp.json()["weighted_average_cost"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_production_run_endpoint(client, db_session) -> None:
    svc = MakerService(session=db_session)
    wh = await svc._inventory.create_warehouse(name="ApiStudio2", code="APISTUDIO2")
    wid = wh["id"]
    card = await svc.create_material(sku="API-MAT-2", name="Cardstock", unit="sheet")
    await svc.record_material_purchase(
        material_id=uuid.UUID(card["id"]), quantity=50, unit_cost=0.20, warehouse_id=uuid.UUID(wid),
    )
    finished = await svc.create_finished_good(sku="API-FG-2", name="Print")
    recipe = await svc.create_recipe()
    await svc.add_recipe_line(
        recipe_id=uuid.UUID(recipe["id"]), material_id=uuid.UUID(card["id"]), qty_per_unit=2,
    )
    variation = await svc.create_variation(
        sku="API-VAR-2", base_price=10.0, recipe_id=uuid.UUID(recipe["id"]),
        finished_stock_id=uuid.UUID(finished["id"]),
    )
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/maker/variations/{variation['id']}/production-runs",
        json={"quantity": 5, "warehouse_id": wid},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["quantity"] == 5.0
    assert body["total_cogs"] == pytest.approx(2.00)  # 5 * (2 * 0.20)

    on_hand = await client.get(f"/api/v1/maker/variations/{variation['id']}/on-hand")
    assert on_hand.json()["on_hand"] == 5.0


@pytest.mark.asyncio
async def test_purchase_endpoint_via_http(client, db_session) -> None:
    svc = MakerService(session=db_session)
    wh = await svc._inventory.create_warehouse(name="ApiStudioP", code="APISTUDIOP")
    material = await svc.create_material(sku="API-MAT-P", name="Cardstock", unit="sheet")
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/maker/materials/{material['id']}/purchases",
        json={"quantity": 40, "unit_cost": 0.15, "warehouse_id": wh["id"]},
    )
    assert resp.status_code == 201
    cost = await client.get(f"/api/v1/maker/materials/{material['id']}/cost")
    assert cost.json()["weighted_average_cost"] == pytest.approx(0.15)


@pytest.mark.asyncio
async def test_production_run_unknown_variation_returns_404(client) -> None:
    bogus = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/maker/variations/{bogus}/production-runs",
        json={"quantity": 1, "warehouse_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_purchase_endpoint_missing_field_returns_422(client) -> None:
    material = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/maker/materials/{material}/purchases",
        json={"quantity": 40},  # missing unit_cost + warehouse_id
    )
    assert resp.status_code == 422
