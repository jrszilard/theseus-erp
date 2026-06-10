from __future__ import annotations

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
