from __future__ import annotations

from typing import Protocol


class StorageBackend(Protocol):
    """Pluggable object storage. Local for dev/tests, MinIO/S3 for deployment."""

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def presign_get(self, key: str, ttl: int) -> str: ...

    async def delete(self, key: str) -> None: ...
