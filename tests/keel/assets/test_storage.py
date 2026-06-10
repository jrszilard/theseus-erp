from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from theseus.keel.assets.storage import LocalStorageBackend, MinioStorageBackend


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


@pytest.mark.asyncio
async def test_minio_put_calls_client_put_object() -> None:
    client = MagicMock()
    backend = MinioStorageBackend(
        endpoint="http://x", access_key="a", secret_key="b",
        bucket="theseus-assets", client=client,
    )
    await backend.put("k/1/a.png", b"img", "image/png")
    client.put_object.assert_called_once_with(
        Bucket="theseus-assets", Key="k/1/a.png", Body=b"img", ContentType="image/png"
    )


@pytest.mark.asyncio
async def test_minio_presign_delegates_to_client() -> None:
    client = MagicMock()
    client.generate_presigned_url.return_value = "http://x/signed"
    backend = MinioStorageBackend(
        endpoint="http://x", access_key="a", secret_key="b",
        bucket="theseus-assets", client=client,
    )
    url = await backend.presign_get("k/1/a.png", ttl=120)
    assert url == "http://x/signed"
    client.generate_presigned_url.assert_called_once()


@pytest.mark.asyncio
async def test_local_backend_rejects_path_traversal(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))
    with pytest.raises(ValueError):
        await backend.put("../escape.txt", b"x", "text/plain")
