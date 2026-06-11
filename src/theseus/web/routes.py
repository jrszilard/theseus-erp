from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from theseus.database import get_session
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
