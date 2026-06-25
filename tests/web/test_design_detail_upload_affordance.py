import pytest


@pytest.mark.asyncio
async def test_design_detail_shows_upload_affordance(client, maker_seed):
    resp = await client.get(f"/designs/{maker_seed['design_id']}")
    assert resp.status_code == 200
    body = resp.text
    # per-group add form posts to the generic entity route (raw dotted ref in the path)
    assert 'hx-post="/entities/maker.Design/' in body
    assert "+ Add" in body
    # the DOM id sanitizes the dot in the ref so "#"-selectors parse (maker.Design -> maker-Design)
    assert 'id="file-group-maker-Design-' in body
