import uuid

import pytest


@pytest.mark.asyncio
async def test_market_day_404_for_unknown(client) -> None:
    resp = await client.get(f"/markets/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_markets_list(client, maker_seed) -> None:
    resp = await client.get("/markets")
    assert resp.status_code == 200
    assert "May Lakeside Fair" in resp.text


@pytest.mark.asyncio
async def test_market_day_shows_pnl_and_capture(client, maker_seed) -> None:
    resp = await client.get(f"/markets/{maker_seed['market_event_id']}")
    assert resp.status_code == 200
    body = resp.text
    assert "May Lakeside Fair" in body
    assert "booth" in body.lower()           # booth fee in the P&L
    assert "take-home" in body.lower()        # booth-aware P&L line
    assert "tally" in body.lower()            # tap-to-tally grid present
    assert 'name="natural"' in body or "Shipwright" in body  # NL box renders (inert)


@pytest.mark.asyncio
async def test_manual_sale_appends_line(client, db_session, maker_seed) -> None:
    me = maker_seed["market_event_id"]
    vid = maker_seed["variation_id"]
    ch = maker_seed["channel_id"]
    resp = await client.post(
        f"/markets/{me}/sale",
        data={"variation_id": vid, "channel_id": ch, "quantity": "2", "unit_price": "25"},
    )
    assert resp.status_code == 200
    assert "2" in resp.text  # the new line's qty appears in the re-rendered lines partial


@pytest.mark.asyncio
async def test_tally_malformed_json_returns_422(client) -> None:
    """A malformed tally payload is client error, not a server crash (no partial write)."""
    resp = await client.post(
        f"/markets/{uuid.uuid4()}/tally",
        data={"session": "not-json{{{"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tally_well_formed_json_wrong_shape_returns_422(client) -> None:
    """Valid JSON but the wrong shape (bad uuid / missing keys) is also a 422."""
    resp = await client.post(
        f"/markets/{uuid.uuid4()}/tally",
        data={"session": '[{"variation_id": "not-a-uuid", "quantity": "1"}]'},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_sale_records_fees_and_decrements_stock(
    client, db_session, maker_seed
) -> None:
    import uuid as _uuid

    from sqlalchemy import text

    from theseus.planks.maker.service import MakerService

    me = maker_seed["market_event_id"]
    vid = maker_seed["variation_id"]
    ch = maker_seed["channel_id"]
    svc = MakerService(session=db_session)
    before = await svc.variation_on_hand(_uuid.UUID(vid))
    resp = await client.post(
        f"/markets/{me}/sale",
        data={"variation_id": vid, "channel_id": ch, "quantity": "2", "unit_price": "25"},
    )
    assert resp.status_code == 200
    after = await svc.variation_on_hand(_uuid.UUID(vid))
    assert after == before - 2
    fees = (await db_session.execute(text(
        "SELECT fees FROM maker_sale WHERE source='manual' ORDER BY sale_date DESC LIMIT 1"
    ))).scalar()
    assert float(fees) > 0  # channel fee computed, not the old hardcoded 0
