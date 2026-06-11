import json
from pathlib import Path

import pytest
from sqlalchemy import text


def test_maker_js_implements_behaviors() -> None:
    js = Path("hull-ui/shells/maker/static/maker.js").read_text()
    assert "data-cmdk" in js          # ⌘K open hook
    assert "tally" in js.lower()       # tap-to-tally
    assert "keydown" in js             # keyboard handling for ⌘K


@pytest.mark.asyncio
async def test_command_search_returns_matches(client, maker_seed) -> None:
    resp = await client.get("/search?q=loon")
    assert resp.status_code == 200
    assert "Loon on Blue Lake" in resp.text


@pytest.mark.asyncio
async def test_tally_commit_records_sales(client, db_session, maker_seed) -> None:
    me = maker_seed["market_event_id"]
    vid = maker_seed["variation_id"]
    ch = maker_seed["channel_id"]
    payload = json.dumps(
        [{"variation_id": vid, "channel_id": ch, "quantity": 4, "unit_price": 4.0}]
    )
    resp = await client.post(f"/markets/{me}/tally", data={"session": payload})
    assert resp.status_code == 200
    total = (await db_session.execute(text(
        "SELECT COALESCE(SUM(quantity),0) FROM maker_sale WHERE market_event_id = :m"
    ), {"m": me})).scalar()
    assert float(total) >= 4


@pytest.mark.asyncio
async def test_capture_parse_renders_confirm(client, db_session, maker_seed, monkeypatch) -> None:
    import theseus.web.routes as routes
    from theseus.planks.maker.capture import ParsedSaleLine

    async def fake_parse(text, variations, gateway):
        return [ParsedSaleLine(maker_seed["variation_id"], "8x10", 2.0, None)]
    monkeypatch.setattr(routes, "parse_sale_text", fake_parse)

    me = maker_seed["market_event_id"]
    resp = await client.post(f"/markets/{me}/capture/parse", data={"natural": "sold 2 8x10"})
    assert resp.status_code == 200
    assert "8x10" in resp.text
    assert "capture/commit" in resp.text  # the confirm form targets commit


@pytest.mark.asyncio
async def test_capture_commit_records_sales(client, db_session, maker_seed) -> None:
    import uuid as _uuid

    from theseus.planks.maker.service import MakerService
    me, vid = maker_seed["market_event_id"], maker_seed["variation_id"]
    svc = MakerService(session=db_session)
    before = await svc.variation_on_hand(_uuid.UUID(vid))
    payload = json.dumps([{"variation_id": vid, "quantity": 2, "unit_price": 25}])
    resp = await client.post(f"/markets/{me}/capture/commit", data={"lines": payload})
    assert resp.status_code == 200
    assert await svc.variation_on_hand(_uuid.UUID(vid)) == before - 2


@pytest.mark.asyncio
async def test_capture_commit_malformed_returns_422(client, maker_seed) -> None:
    me = maker_seed["market_event_id"]
    resp = await client.post(f"/markets/{me}/capture/commit", data={"lines": "not-json{{"})
    assert resp.status_code == 422
