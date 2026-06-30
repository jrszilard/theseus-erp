from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, status

from theseus.database import get_session
from theseus.keel.integration.auth import require_service_token
from theseus.planks.maker.service import MakerService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["integration"],
    dependencies=[Depends(require_service_token)],
)


@router.get("/products")
async def list_products(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, list[dict[str, Any]]]:
    svc = MakerService(session=session)
    return {"products": await svc.sellable_products()}


@router.get("/products/{sku}")
async def get_product(
    sku: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    svc = MakerService(session=session)
    product = await svc.sellable_product(sku)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return product
