from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from theseus.database import get_session
from theseus.planks.maker.service import MakerService
from theseus.web import read_models
from theseus.web.templating import templates

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
async def board(
    request: Request, session: AsyncSession = Depends(get_session)  # noqa: B008
) -> HTMLResponse:
    designs = await read_models.list_designs_for_board(session)
    return templates.TemplateResponse(request, "board.html", {"designs": designs})


@router.get("/designs/{design_id}", response_class=HTMLResponse)
async def design_detail(request: Request, design_id: uuid.UUID,
                        session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    design = await read_models.get_design_detail(session, design_id)
    if design is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="design not found")
    return templates.TemplateResponse(request, "design_detail.html", {"design": design})


@router.get("/bom/{variation_id}", response_class=HTMLResponse)
async def bom(request: Request, variation_id: uuid.UUID,
              session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    view = await read_models.get_bom_view(session, variation_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="variation not found")
    wh = (await session.execute(
        text("SELECT id FROM inventory_warehouse ORDER BY created_at LIMIT 1")
    )).scalar()
    return templates.TemplateResponse(request, "bom.html",
                                      {"bom": view, "warehouse_id": str(wh) if wh else ""})


@router.post("/bom/{variation_id}/run", response_class=HTMLResponse)
async def bom_run(request: Request, variation_id: uuid.UUID,
                  quantity: float = Form(...),
                  warehouse_id: uuid.UUID = Form(...),  # noqa: B008
                  session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    svc = MakerService(session=session)
    await svc.run_production(
        variation_id=variation_id, quantity=quantity, warehouse_id=warehouse_id
    )
    await session.commit()
    view = await read_models.get_bom_view(session, variation_id)
    return templates.TemplateResponse(request, "partials/_bom_numbers.html", {"bom": view})
