from __future__ import annotations

import pytest

from theseus.keel.assets.storage import LocalStorageBackend


@pytest.mark.asyncio
async def test_put_then_get_roundtrips_bytes(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))
    await backend.put("abc/1/loon.svg", b"<svg/>", "image/svg+xml")
    assert await backend.get("abc/1/loon.svg") == b"<svg/>"


@pytest.mark.asyncio
async def test_presign_get_returns_url_containing_key(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))
    url = await backend.presign_get("abc/1/loon.svg", ttl=60)
    assert "abc/1/loon.svg" in url


@pytest.mark.asyncio
async def test_delete_removes_object(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))
    await backend.put("k/1/x.bin", b"data", "application/octet-stream")
    await backend.delete("k/1/x.bin")
    with pytest.raises(FileNotFoundError):
        await backend.get("k/1/x.bin")


@pytest.mark.asyncio
async def test_get_missing_key_raises(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        await backend.get("nope/1/missing.bin")
