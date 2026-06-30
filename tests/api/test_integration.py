import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from theseus.config import settings
from theseus.planks.maker.service import MakerService

TOKEN = "test-integration-token-1234567890"
AUTH = {"Authorization": f"Bearer {TOKEN}"}

DESIGN_TITLE = "Integration Test Design"


@pytest.fixture
def _token(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_token", TOKEN)


@pytest_asyncio.fixture(loop_scope="session")
async def int_graph(db_session):
    """A minimal, uniquely-named maker graph built on db_session with flush() only.

    The `client` fixture overrides get_session to yield this same db_session, so the
    endpoint sees these flushed-but-uncommitted rows; db_session rolls back at teardown.
    Fully isolated and order-independent — unlike maker_seed, this never commits, so it
    can't leak into (or be mutated by) other tests.
    """
    svc = MakerService(session=db_session)

    # Finished good with positive on-hand (so available is True).
    wh = await svc._inventory.create_warehouse(name="Integration WH", code="INT-WH")
    wid = uuid.UUID(wh["id"])
    fg = await svc.create_finished_good(sku="INT-FG", name="Integration Finished Good")
    fg_id = uuid.UUID(fg["id"])
    await svc._inventory.record_movement(
        stock_item_id=fg_id, warehouse_id=wid,
        movement_type="received", quantity=7, reference="int-seed",
    )

    # design -> product -> current version (+ draft version)
    fmt_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO maker_format (id, name, default_unit) VALUES (:i,:n,'each')"),
        {"i": fmt_id, "n": "Integration Format"},
    )
    design_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO maker_design (id, title, slug, status) VALUES (:i,:t,:s,'released')"),
        {"i": design_id, "t": DESIGN_TITLE, "s": "integration-test-design"},
    )
    product_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO maker_product (id, name, design_id, format_id) VALUES (:i,:n,:d,:f)"),
        {"i": product_id, "n": "Integration Product", "d": design_id, "f": fmt_id},
    )
    current_version_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO maker_product_version (id, number, status, product_id) "
             "VALUES (:i,1,'current',:p)"),
        {"i": current_version_id, "p": product_id},
    )
    draft_version_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO maker_product_version (id, number, status, product_id) "
             "VALUES (:i,2,'draft',:p)"),
        {"i": draft_version_id, "p": product_id},
    )

    # current-version variation (sellable) and draft-version variation (excluded)
    await svc.create_variation(
        sku="INT-CUR", base_price=20.0,
        finished_stock_id=fg_id, product_version_id=current_version_id,
    )
    await svc.create_variation(
        sku="INT-DRAFT", base_price=9.0, product_version_id=draft_version_id,
    )
    await db_session.flush()
    return {"design_id": str(design_id), "current_sku": "INT-CUR", "draft_sku": "INT-DRAFT"}


@pytest.mark.asyncio
async def test_products_401_without_token(client, _token):
    resp = await client.get("/api/v1/integration/products")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_products_503_when_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "integration_api_token", "")
    resp = await client.get("/api/v1/integration/products", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_products_lists_current_excludes_draft(client, int_graph, _token):
    resp = await client.get("/api/v1/integration/products", headers=AUTH)
    assert resp.status_code == 200
    products = resp.json()["products"]
    skus = {p["sku"] for p in products}
    assert "INT-CUR" in skus           # current-version variation
    assert "INT-DRAFT" not in skus     # draft version excluded

    p = next(p for p in products if p["sku"] == "INT-CUR")
    assert set(p) == {"sku", "name", "price", "on_hand", "available"}
    assert isinstance(p["price"], float) and isinstance(p["on_hand"], float)
    assert p["available"] == (p["on_hand"] > 0)
    assert p["name"] == DESIGN_TITLE   # name = design title


@pytest.mark.asyncio
async def test_product_by_sku_and_404(client, int_graph, _token):
    ok = await client.get("/api/v1/integration/products/INT-CUR", headers=AUTH)
    assert ok.status_code == 200 and ok.json()["sku"] == "INT-CUR"
    missing = await client.get("/api/v1/integration/products/NOPE", headers=AUTH)
    assert missing.status_code == 404
