from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from theseus.database import get_session
from theseus.keel.assets.factory import build_storage
from theseus.keel.assets.service import AssetService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from theseus.keel.assets.protocols import StorageBackend

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


def _get_storage() -> StorageBackend:
    """Module-level factory (mockable in tests; mirrors shipwright._get_gateway)."""
    return build_storage()


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),  # noqa: B008
    kind: str = Form("other"),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    service = AssetService(session=session, storage=_get_storage())
    data = await file.read()
    record = await service.upload(
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        kind=kind,
    )
    await session.commit()
    return record.model_dump(mode="json")


@router.post("/{asset_id}/versions", status_code=status.HTTP_201_CREATED)
async def add_asset_version(
    asset_id: uuid.UUID,
    file: UploadFile = File(...),  # noqa: B008
    note: str = Form(""),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    service = AssetService(session=session, storage=_get_storage())
    data = await file.read()
    try:
        record = await service.add_version(
            asset_id=asset_id,
            filename=file.filename or "upload.bin",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            note=note or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return record.model_dump(mode="json")


@router.get("/{asset_id}")
async def get_asset(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    service = AssetService(session=session, storage=_get_storage())
    try:
        record = await service.get(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return record.model_dump(mode="json")


@router.get("/{asset_id}/url")
async def get_asset_url(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, str]:
    service = AssetService(session=session, storage=_get_storage())
    try:
        url = await service.presigned_url(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"url": url}
