import uuid

import pytest

from theseus.planks.maker.service import MakerService


@pytest.mark.asyncio
async def test_create_material_makes_raw_material_stock_item(db_session) -> None:
    svc = MakerService(session=db_session)
    material = await svc.create_material(sku="MAT-CARD-8x10", name="Cardstock 8x10", unit="sheet")
    assert material["category"] == "raw_material"
    assert material["sku"] == "MAT-CARD-8x10"
    assert "id" in material


@pytest.mark.asyncio
async def test_create_variation_wires_fks(db_session) -> None:
    svc = MakerService(session=db_session)
    finished = await svc.create_finished_good(sku="FG-LOON-8x10", name="Loon Print 8x10")
    recipe = await svc.create_recipe(labor_minutes=10, labor_rate_per_hour=30)
    variation = await svc.create_variation(
        sku="VAR-LOON-8x10", base_price=24.00,
        finished_stock_id=uuid.UUID(finished["id"]),
        recipe_id=uuid.UUID(recipe["id"]),
    )
    assert variation["sku"] == "VAR-LOON-8x10"
    assert variation["finished_stock_id"] == finished["id"]
    assert variation["recipe_id"] == recipe["id"]


@pytest.mark.asyncio
async def test_add_recipe_line_links_material(db_session) -> None:
    svc = MakerService(session=db_session)
    material = await svc.create_material(sku="MAT-INK-1", name="Ink", unit="ml")
    recipe = await svc.create_recipe(labor_minutes=0, labor_rate_per_hour=0)
    line = await svc.add_recipe_line(
        recipe_id=uuid.UUID(recipe["id"]),
        material_id=uuid.UUID(material["id"]),
        qty_per_unit=2.5,
    )
    assert line["material_id"] == material["id"]
    assert line["qty_per_unit"] == 2.5


@pytest.mark.asyncio
async def test_create_recipe_emits_event_with_id(db_session) -> None:
    from theseus.keel.event_store.store import PostgresEventStore

    svc = MakerService(session=db_session)
    recipe = await svc.create_recipe(labor_minutes=5, labor_rate_per_hour=20)
    store = PostgresEventStore(session=db_session)
    events = await store.get_events_by_type("maker.Recipe.created")
    assert any(e.data.get("id") == recipe["id"] for e in events)
