from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from theseus.keel.assets.models import Asset, AssetVersion


@pytest.mark.asyncio
async def test_asset_with_versions_persists_and_loads(db_session) -> None:
    asset = Asset(kind="cut-file", filename="loon.svg", content_type="image/svg+xml")
    asset.versions.append(
        AssetVersion(version=1, storage_key=f"{uuid.uuid4()}/1/loon.svg", size_bytes=42)
    )
    db_session.add(asset)
    await db_session.flush()

    loaded = (
        await db_session.execute(select(Asset).where(Asset.id == asset.id))
    ).scalar_one()
    assert loaded.kind == "cut-file"
    assert len(loaded.versions) == 1
    assert loaded.versions[0].version == 1
