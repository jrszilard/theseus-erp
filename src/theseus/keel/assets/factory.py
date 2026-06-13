from __future__ import annotations

from typing import TYPE_CHECKING

from theseus.config import settings
from theseus.keel.assets.storage import LocalStorageBackend, MinioStorageBackend

if TYPE_CHECKING:
    from theseus.keel.assets.protocols import StorageBackend


def build_storage() -> StorageBackend:
    if settings.storage_backend == "local":
        return LocalStorageBackend(root=settings.storage_local_root)
    return MinioStorageBackend(
        endpoint=settings.storage_endpoint,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        bucket=settings.storage_bucket,
        region=settings.storage_region,
    )
