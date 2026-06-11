import uuid

import pytest


@pytest.mark.asyncio
async def test_design_detail_shows_variation_metrics(client, maker_seed) -> None:
    resp = await client.get(f"/designs/{maker_seed['design_id']}")
    assert resp.status_code == 200
    body = resp.text
    assert "Loon on Blue Lake" in body
    assert "Print" in body                 # the format
    assert "v1" in body                    # version badge (per-format, no global tab)
    assert "8x10" in body                  # the variation
    assert "BOM" in body                   # BOM link on the variation row
    assert "$25.00" in body                # base price renders


@pytest.mark.asyncio
async def test_design_detail_404_for_unknown(client) -> None:
    resp = await client.get(f"/designs/{uuid.uuid4()}")
    assert resp.status_code == 404
