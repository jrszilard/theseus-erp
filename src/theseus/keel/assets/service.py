from __future__ import annotations

import hashlib
import uuid  # noqa: TC003

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002
from sqlalchemy.orm import selectinload

from theseus.config import settings
from theseus.keel.assets.models import Asset, AssetRecord, AssetVersion
from theseus.keel.assets.protocols import StorageBackend  # noqa: TC001
from theseus.keel.assets.thumbnails import make_thumbnail
from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore


class AssetService:
    """Stores file bytes in object storage and records metadata + versions."""

    def __init__(self, session: AsyncSession, storage: StorageBackend) -> None:
        self._session = session
        self._storage = storage
        self._events = PostgresEventStore(session=session)

    async def upload(
        self, *, filename: str, content_type: str, data: bytes, kind: str = "other",
        actor_id: uuid.UUID | None = None,
    ) -> AssetRecord:
        asset = Asset(kind=kind, filename=filename, content_type=content_type)
        self._session.add(asset)
        await self._session.flush()  # assign asset.id

        # Reload with eager-loaded versions to avoid MissingGreenlet on the
        # relationship access inside _store_version.
        asset = await self._load(asset.id)
        await self._store_version(asset, filename, content_type, data, version=1, note=None)

        await emit_entity_event(
            store=self._events, action="uploaded", plank="assets", entity="Asset",
            entity_id=asset.id,
            data={
                "filename": filename, "content_type": content_type,
                "size": len(data), "kind": kind,
            },
            actor_id=actor_id,
        )
        return await self.get(asset.id)

    async def add_version(
        self, *, asset_id: uuid.UUID, filename: str, content_type: str, data: bytes,
        note: str | None = None, actor_id: uuid.UUID | None = None,
    ) -> AssetRecord:
        asset = await self._load(asset_id)
        next_version = (max((v.version for v in asset.versions), default=0)) + 1
        await self._store_version(
            asset, filename, content_type, data, version=next_version, note=note
        )

        await emit_entity_event(
            store=self._events, action="versioned", plank="assets", entity="Asset",
            entity_id=asset.id, data={"version": next_version, "note": note},
            actor_id=actor_id,
        )
        await self._session.flush()
        return await self.get(asset.id)

    async def get(self, asset_id: uuid.UUID) -> AssetRecord:
        asset = await self._load(asset_id)
        return AssetRecord.model_validate(asset)

    async def presigned_url(self, asset_id: uuid.UUID, version: int | None = None) -> str:
        asset = await self._load(asset_id)
        if version is not None:
            target = next((v for v in asset.versions if v.version == version), None)
        else:
            target = asset.current_version
        if target is None:
            msg = f"Asset {asset_id} has no matching version"
            raise ValueError(msg)
        return await self._storage.presign_get(
            target.storage_key, ttl=settings.storage_presign_ttl_seconds
        )

    async def _store_version(
        self, asset: Asset, filename: str, content_type: str, data: bytes,
        version: int, note: str | None,
    ) -> None:
        storage_key = f"{asset.id}/{version}/{filename}"
        await self._storage.put(storage_key, data, content_type)

        thumbnail_key: str | None = None
        thumb = make_thumbnail(data)
        if thumb is not None:
            thumbnail_key = f"{asset.id}/{version}/thumb.png"
            await self._storage.put(thumbnail_key, thumb, "image/png")

        asset.versions.append(
            AssetVersion(
                version=version, storage_key=storage_key, size_bytes=len(data),
                checksum=hashlib.sha256(data).hexdigest(), note=note,
                thumbnail_key=thumbnail_key,
            )
        )
        await self._session.flush()

    async def _load(self, asset_id: uuid.UUID) -> Asset:
        result = await self._session.execute(
            select(Asset).where(Asset.id == asset_id).options(selectinload(Asset.versions))
        )
        asset = result.unique().scalar_one_or_none()
        if asset is None:
            msg = f"Asset {asset_id} not found"
            raise ValueError(msg)
        return asset
