from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.database import get_session
from theseus.planks.maker.service import MakerService

router = APIRouter(prefix="/api/v1/maker", tags=["maker"])


class PurchaseRequest(BaseModel):
    quantity: float
    unit_cost: float
    warehouse_id: uuid.UUID


class ProductionRunRequest(BaseModel):
    quantity: float
    warehouse_id: uuid.UUID


@router.get("/materials/{material_id}/cost")
async def material_cost(material_id: uuid.UUID,
                        session: AsyncSession = Depends(get_session)) -> dict[str, float]:
    svc = MakerService(session=session)
    return {"weighted_average_cost": await svc.weighted_average_cost(material_id)}


@router.get("/variations/{variation_id}/cogs")
async def variation_cogs(variation_id: uuid.UUID,
                         session: AsyncSession = Depends(get_session)) -> dict[str, float]:
    svc = MakerService(session=session)
    return {"unit_cogs": await svc.unit_cogs(variation_id)}


@router.get("/variations/{variation_id}/buildable")
async def variation_buildable(variation_id: uuid.UUID,
                              session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    svc = MakerService(session=session)
    return {"buildable_now": await svc.buildable_now(variation_id)}


@router.get("/variations/{variation_id}/on-hand")
async def variation_on_hand(variation_id: uuid.UUID,
                            session: AsyncSession = Depends(get_session)) -> dict[str, float]:
    svc = MakerService(session=session)
    return {"on_hand": await svc.variation_on_hand(variation_id)}


@router.post("/materials/{material_id}/purchases", status_code=status.HTTP_201_CREATED)
async def record_purchase(material_id: uuid.UUID, body: PurchaseRequest,
                          session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    svc = MakerService(session=session)
    result = await svc.record_material_purchase(
        material_id=material_id,
        quantity=body.quantity,
        unit_cost=body.unit_cost,
        warehouse_id=body.warehouse_id,
    )
    await session.commit()
    return result


@router.post("/variations/{variation_id}/production-runs", status_code=status.HTTP_201_CREATED)
async def record_production_run(variation_id: uuid.UUID, body: ProductionRunRequest,
                                session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    svc = MakerService(session=session)
    try:
        run = await svc.run_production(
            variation_id=variation_id,
            quantity=body.quantity,
            warehouse_id=body.warehouse_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return run
