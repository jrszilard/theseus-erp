from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
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
