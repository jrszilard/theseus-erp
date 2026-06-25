import uuid

import pytest
from sqlalchemy import text

from theseus.keel.assets.storage import LocalStorageBackend


@pytest.fixture(autouse=True)
def _web_local_storage(monkeypatch, tmp_path):
    """Force the web routes to use local-filesystem storage (no MinIO in tests)."""
    from theseus.web import routes as web_routes

    backend = LocalStorageBackend(root=str(tmp_path))
    monkeypatch.setattr(web_routes, "_get_storage", lambda: backend)
    return backend


async def _source_art_count(db_session, design_id, filename):
    # filename-scoped (not a blanket COUNT) so route-committed rows from sibling tests
    # in this session don't make the assertion flaky.
    return (await db_session.execute(text(
        "SELECT COUNT(*) FROM maker_design_source_art j JOIN assets a ON a.id = j.asset_id "
        "WHERE j.maker_design_id = :d AND a.filename = :f"),
        {"d": design_id, "f": filename})).scalar()


@pytest.mark.asyncio
async def test_upload_attaches_and_returns_chip(client, db_session, maker_seed):
    did = maker_seed["design_id"]
    resp = await client.post(
        f"/entities/maker.Design/{did}/files/source_art",
        files={"files": ("up-loon.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 200
    assert "up-loon.png" in resp.text
    assert await _source_art_count(db_session, did, "up-loon.png") == 1


@pytest.mark.asyncio
async def test_upload_multiple_files_in_one_post(client, db_session, maker_seed):
    did = maker_seed["design_id"]
    resp = await client.post(
        f"/entities/maker.Design/{did}/files/source_art",
        files=[
            ("files", ("multi-a.png", b"\x89PNG", "image/png")),
            ("files", ("multi-b.jpg", b"\xff\xd8", "image/jpeg")),
        ],
    )
    assert resp.status_code == 200
    assert "multi-a.png" in resp.text and "multi-b.jpg" in resp.text
    assert await _source_art_count(db_session, did, "multi-a.png") == 1
    assert await _source_art_count(db_session, did, "multi-b.jpg") == 1


@pytest.mark.asyncio
async def test_upload_over_cap_rejected(client, db_session, maker_seed, monkeypatch):
    from theseus.config import settings
    monkeypatch.setattr(settings, "max_upload_bytes", 4)
    did = maker_seed["design_id"]
    resp = await client.post(
        f"/entities/maker.Design/{did}/files/source_art",
        files={"files": ("toobig.png", b"\x89PNG-too-long", "image/png")},
    )
    assert resp.status_code == 200
    assert "too large" in resp.text.lower()
    assert await _source_art_count(db_session, did, "toobig.png") == 0


@pytest.mark.asyncio
async def test_unknown_ref_is_404(client, maker_seed):
    resp = await client.post(
        f"/entities/maker.Nope/{uuid.uuid4()}/files/source_art",
        files={"files": ("x.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unknown_field_is_404(client, maker_seed):
    did = maker_seed["design_id"]
    resp = await client.post(
        f"/entities/maker.Design/{did}/files/not_a_field",
        files={"files": ("x.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detach_removes_chip_keeps_asset(client, db_session, maker_seed):
    did = maker_seed["design_id"]
    await client.post(
        f"/entities/maker.Design/{did}/files/source_art",
        files={"files": ("det-loon.png", b"\x89PNG", "image/png")},
    )
    asset_id = (await db_session.execute(text(
        "SELECT j.asset_id FROM maker_design_source_art j JOIN assets a ON a.id = j.asset_id "
        "WHERE j.maker_design_id = :d AND a.filename = 'det-loon.png'"),
        {"d": did})).scalar()
    resp = await client.post(
        f"/entities/maker.Design/{did}/files/source_art/detach/{asset_id}")
    assert resp.status_code == 200
    assert "det-loon.png" not in resp.text
    assert await _source_art_count(db_session, did, "det-loon.png") == 0
    still = (await db_session.execute(text(
        "SELECT 1 FROM assets WHERE id = :a"), {"a": str(asset_id)})).scalar()
    assert still == 1   # detach-only


@pytest.mark.asyncio
async def test_unknown_entity_is_404(client, maker_seed):
    resp = await client.post(
        f"/entities/maker.Design/{uuid.uuid4()}/files/source_art",
        files={"files": ("x.png", b"\x89PNG", "image/png")},
    )
    assert resp.status_code == 404
