from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from theseus.web.templating import templates

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
async def board(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "base.html", {})
