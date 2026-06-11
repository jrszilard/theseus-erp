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
