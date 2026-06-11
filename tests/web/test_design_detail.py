import uuid

import pytest


@pytest.mark.asyncio
async def test_seed_has_draft_version_and_prior_sales(client, db_session, maker_seed) -> None:
    from sqlalchemy import text
    assert "draft_version_id" in maker_seed
    drafts = (await db_session.execute(text(
        "SELECT COUNT(*) FROM maker_product_version WHERE status = 'draft'"))).scalar()
    assert drafts >= 1


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


@pytest.mark.asyncio
async def test_design_detail_shows_make_more_nudge(client, db_session, maker_seed) -> None:
    # the seed's 8x10 has sales in 60d -> a make-more nudge appears in the sidebar
    resp = await client.get(f"/designs/{maker_seed['design_id']}")
    assert resp.status_code == 200
    assert "Shipwright" in resp.text
    # "buildable" appears ONLY in the make_more nudge on this page (the variation table
    # says "sold · on hand", not "buildable") — so this proves the sidebar insight rendered.
    assert "buildable" in resp.text.lower()
    # the inert Plan-3 placeholder must be gone now that real insights render
    assert "later update" not in resp.text.lower()


@pytest.mark.asyncio
async def test_promote_route_flips_version(client, db_session, maker_seed) -> None:
    from sqlalchemy import text
    did, draft = maker_seed["design_id"], maker_seed["draft_version_id"]
    resp = await client.post(f"/designs/{did}/versions/{draft}/promote", follow_redirects=True)
    assert resp.status_code == 200
    status = (await db_session.execute(text(
        "SELECT status FROM maker_product_version WHERE id = :v"), {"v": draft})).scalar()
    assert status == "current"


@pytest.mark.asyncio
async def test_design_detail_shows_sales_by_version(client, maker_seed) -> None:
    resp = await client.get(f"/designs/{maker_seed['design_id']}")
    assert "by version" in resp.text.lower()
