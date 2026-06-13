import uuid

import pytest

import theseus.web.routes as _routes


@pytest.mark.asyncio
async def test_board_shows_welcome_when_empty(client, monkeypatch) -> None:
    """When the board read-model returns no designs, the welcome panel renders.

    Uses monkeypatch to avoid mutating the shared DB seed graph.
    """

    async def _empty(session):
        return []

    monkeypatch.setattr(_routes.read_models, "list_designs_for_board", _empty)

    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Welcome to Maker Edition" in resp.text
    assert 'name="title"' in resp.text


@pytest.mark.asyncio
async def test_create_design_route_creates_and_redirects(client, db_session) -> None:
    from sqlalchemy import text

    title = f"Welcome Loon {uuid.uuid4().hex[:6]}"
    resp = await client.post("/designs", data={"title": title}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/designs/")

    row = (await db_session.execute(
        text("SELECT status FROM maker_design WHERE title = :t"), {"t": title}
    )).scalar()
    assert row == "idea"


@pytest.mark.asyncio
async def test_create_design_rejects_blank_title(client) -> None:
    resp = await client.post("/designs", data={"title": "  "}, follow_redirects=False)
    assert resp.status_code == 422
