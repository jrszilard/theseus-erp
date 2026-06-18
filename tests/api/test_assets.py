from __future__ import annotations

import uuid

import pytest

from theseus.keel.assets.storage import LocalStorageBackend


@pytest.fixture(autouse=True)
def _local_storage(monkeypatch, tmp_path):
    """Force the assets routes to use local filesystem storage in tests."""
    from theseus.api.routes import assets as assets_routes

    backend = LocalStorageBackend(root=str(tmp_path))
    monkeypatch.setattr(assets_routes, "_get_storage", lambda: backend)
    return backend


@pytest.mark.asyncio
async def test_upload_returns_201_with_asset(client) -> None:
    resp = await client.post(
        "/api/v1/assets",
        files={"file": ("loon.svg", b"<svg/>", "image/svg+xml")},
        data={"kind": "cut-file"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "cut-file"
    assert body["filename"] == "loon.svg"
    assert len(body["versions"]) == 1


@pytest.mark.asyncio
async def test_get_asset_metadata(client) -> None:
    created = (
        await client.post(
            "/api/v1/assets",
            files={"file": ("a.png", b"img", "image/png")},
            data={"kind": "mockup"},
        )
    ).json()
    resp = await client.get(f"/api/v1/assets/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_asset_url(client) -> None:
    created = (
        await client.post(
            "/api/v1/assets",
            files={"file": ("a.png", b"img", "image/png")},
            data={"kind": "mockup"},
        )
    ).json()
    resp = await client.get(f"/api/v1/assets/{created['id']}/url")
    assert resp.status_code == 200
    assert "url" in resp.json()


@pytest.mark.asyncio
async def test_add_version_returns_201_with_two_versions(client) -> None:
    created = (
        await client.post(
            "/api/v1/assets",
            files={"file": ("a.svg", b"v1", "image/svg+xml")},
            data={"kind": "cut-file"},
        )
    ).json()
    resp = await client.post(
        f"/api/v1/assets/{created['id']}/versions",
        files={"file": ("a.svg", b"v2", "image/svg+xml")},
        data={"note": "v2"},
    )
    assert resp.status_code == 201
    assert len(resp.json()["versions"]) == 2


@pytest.mark.asyncio
async def test_add_version_unknown_asset_returns_404(client) -> None:
    resp = await client.post(
        f"/api/v1/assets/{uuid.uuid4()}/versions",
        files={"file": ("a.svg", b"x", "image/svg+xml")},
        data={"note": ""},
    )
    assert resp.status_code == 404


async def _upload(client, filename, data, content_type, kind="art"):
    resp = await client.post(
        "/api/v1/assets",
        files={"file": (filename, data, content_type)},
        data={"kind": kind},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_serve_raw_raster_is_inline_with_trusted_headers(client) -> None:
    body = await _upload(client, "art.png", b"\x89PNG\r\n\x1a\n", "image/png")
    key = body["versions"][0]["storage_key"]
    resp = await client.get(f"/api/v1/assets/raw/{key}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.headers["content-disposition"] == "inline"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.content == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_serve_raw_svg_is_attachment(client) -> None:
    body = await _upload(client, "loon.svg", b"<svg/>", "image/svg+xml", kind="cut-file")
    key = body["versions"][0]["storage_key"]
    resp = await client.get(f"/api/v1/assets/raw/{key}")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"] == 'attachment; filename="loon.svg"'
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["content-type"].startswith("image/svg+xml")


@pytest.mark.asyncio
async def test_serve_raw_unknown_key_404(client) -> None:
    resp = await client.get("/api/v1/assets/raw/does/not/exist.png")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_serve_raw_traversal_key_404(client) -> None:
    # No AssetVersion row matches a traversal key → 404 before storage is touched.
    resp = await client.get("/api/v1/assets/raw/../../etc/passwd")
    assert resp.status_code == 404
