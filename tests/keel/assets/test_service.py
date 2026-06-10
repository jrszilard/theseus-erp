from __future__ import annotations

import io

import pytest
from PIL import Image

from theseus.keel.assets.service import AssetService
from theseus.keel.assets.storage import LocalStorageBackend
from theseus.keel.event_store.store import PostgresEventStore


@pytest.fixture
def asset_service(db_session, tmp_path) -> AssetService:
    return AssetService(
        session=db_session,
        storage=LocalStorageBackend(root=str(tmp_path)),
    )


@pytest.mark.asyncio
async def test_upload_creates_asset_with_v1_and_stores_bytes(asset_service) -> None:
    record = await asset_service.upload(
        filename="loon.svg", content_type="image/svg+xml",
        data=b"<svg/>", kind="cut-file",
    )
    assert record.kind == "cut-file"
    assert len(record.versions) == 1
    assert record.versions[0].version == 1
    stored = await asset_service._storage.get(record.versions[0].storage_key)
    assert stored == b"<svg/>"


@pytest.mark.asyncio
async def test_add_version_increments_and_keeps_history(asset_service) -> None:
    record = await asset_service.upload(
        filename="loon.svg", content_type="image/svg+xml", data=b"v1", kind="cut-file",
    )
    updated = await asset_service.add_version(
        asset_id=record.id, filename="loon.svg", content_type="image/svg+xml",
        data=b"v2", note="tweaked outline",
    )
    versions = sorted(v.version for v in updated.versions)
    assert versions == [1, 2]


@pytest.mark.asyncio
async def test_presigned_url_points_at_current_version(asset_service) -> None:
    record = await asset_service.upload(
        filename="a.png", content_type="image/png", data=b"img", kind="mockup",
    )
    url = await asset_service.presigned_url(record.id)
    assert record.versions[0].storage_key in url


@pytest.mark.asyncio
async def test_upload_emits_event(asset_service, db_session) -> None:
    record = await asset_service.upload(
        filename="x.png", content_type="image/png", data=b"img", kind="mockup",
    )
    store = PostgresEventStore(session=db_session)
    events = await store.get_events_for_entity("Asset", record.id)
    assert any(e.event_type == "assets.Asset.uploaded" for e in events)


@pytest.mark.asyncio
async def test_presigned_url_unknown_version_raises_valueerror(asset_service) -> None:
    record = await asset_service.upload(
        filename="a.png", content_type="image/png", data=b"img", kind="mockup",
    )
    with pytest.raises(ValueError):
        await asset_service.presigned_url(record.id, version=99)


@pytest.mark.asyncio
async def test_image_upload_gets_thumbnail(asset_service) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (400, 400), "red").save(buf, format="PNG")
    record = await asset_service.upload(
        filename="art.png", content_type="image/png", data=buf.getvalue(), kind="source-art",
    )
    assert record.versions[0].thumbnail_key is not None


@pytest.mark.asyncio
async def test_svg_upload_has_no_thumbnail(asset_service) -> None:
    record = await asset_service.upload(
        filename="cut.svg", content_type="image/svg+xml", data=b"<svg/>", kind="cut-file",
    )
    assert record.versions[0].thumbnail_key is None
