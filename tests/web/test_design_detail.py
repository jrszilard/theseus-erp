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


@pytest.mark.asyncio
async def test_promote_route_stale_version_returns_409(client, maker_seed) -> None:
    import uuid as _uuid
    did = maker_seed["design_id"]
    resp = await client.post(f"/designs/{did}/versions/{_uuid.uuid4()}/promote")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_design_detail_renders_design_and_version_file_strips(
    client, db_session, maker_seed, tmp_path
):
    import uuid

    from sqlalchemy import text

    from theseus.keel.assets.service import AssetService
    from theseus.keel.assets.storage import LocalStorageBackend

    svc = AssetService(
        session=db_session, storage=LocalStorageBackend(root=str(tmp_path))
    )
    art = await svc.upload(
        filename="loon.png", content_type="image/png", data=b"\x89PNG", kind="art"
    )
    cut = await svc.upload(
        filename="loon_cut.svg",
        content_type="image/svg+xml",
        data=b"<svg/>",
        kind="cut-file",
    )
    await db_session.execute(
        text(
            "INSERT INTO maker_design_source_art"
            " (id, maker_design_id, asset_id, sort_order) VALUES (:j,:e,:a,0)"
        ),
        {"j": str(uuid.uuid4()), "e": maker_seed["design_id"], "a": str(art.id)},
    )
    await db_session.execute(
        text(
            "INSERT INTO maker_product_version_production_files"
            " (id, maker_product_version_id, asset_id, sort_order) VALUES (:j,:e,:a,0)"
        ),
        {"j": str(uuid.uuid4()), "e": maker_seed["version_id"], "a": str(cut.id)},
    )
    await db_session.commit()

    resp = await client.get(f"/designs/{maker_seed['design_id']}")
    assert resp.status_code == 200
    body = resp.text
    assert "Design files" in body
    assert "Source art" in body                 # group label from ui hint
    assert "loon.png" in body                    # design-level chip
    assert "Files · v" in body                   # versioned strip heading
    assert "loon_cut.svg" in body                # version-level chip
    assert 'class="file-chip"' in body
    assert f'/api/v1/assets/raw/{art.versions[0].storage_key}' in body
    # non-previewable svg chip carries a download hint; previewable png does not
    assert "download" in body
    assert body.count(" download") == 1


def test_file_strip_macro_is_field_agnostic():
    """Render the macro directly with a synthetic custom group — no field names baked in."""
    from theseus.web.templating import templates
    env = templates.env
    tmpl = env.from_string(
        "{% import 'maker.html' as mk %}{{ mk.file_strip('Custom', groups) }}"
    )
    html = tmpl.render(groups=[{
        "field_name": "weird_custom_field", "label": "Weird Custom Field", "group_icon": "🧪",
        "files": [{"url": "/api/v1/assets/raw/k/1/x.bin", "filename": "x.bin",
                   "icon": "📎", "previewable": False, "content_type": "application/octet-stream"}],
    }])
    assert "Custom" in html
    assert "Weird Custom Field" in html
    assert "x.bin" in html
    assert "/api/v1/assets/raw/k/1/x.bin" in html
