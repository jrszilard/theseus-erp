from __future__ import annotations

import json
import uuid
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


@router.get("/markets", response_class=HTMLResponse)
async def markets(request: Request, session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    rows = await read_models.list_markets(session)
    return templates.TemplateResponse(request, "markets.html", {"markets": rows})


@router.get("/markets/{market_event_id}", response_class=HTMLResponse)
async def market_day(request: Request, market_event_id: uuid.UUID,
                     session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    view = await read_models.get_market_day(session, market_event_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market not found")
    options = [{"value": v["id"], "label": v["label"]} for v in view["variations"]]
    default_channel = (await session.execute(
        text("SELECT id FROM maker_channel ORDER BY created_at LIMIT 1")
    )).scalar()
    return templates.TemplateResponse(request, "market_day.html", {
        "market": view, "variation_options": options,
        "default_channel_id": str(default_channel) if default_channel else "",
    })


@router.post("/markets/{market_event_id}/sale", response_class=HTMLResponse)
async def market_sale(request: Request, market_event_id: uuid.UUID,
                      variation_id: uuid.UUID = Form(...), channel_id: uuid.UUID = Form(...),  # noqa: B008
                      quantity: float = Form(...), unit_price: float = Form(...),
                      session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    sale_id = uuid.uuid4()
    await session.execute(text(
        "INSERT INTO maker_sale (id, quantity, unit_price, fees, sale_date, source, "
        "variation_id, channel_id, market_event_id) "
        "VALUES (:i, :q, :p, 0, now(), 'manual', :v, :c, :m)"
    ), {"i": sale_id, "q": quantity, "p": unit_price,
        "v": variation_id, "c": channel_id, "m": market_event_id})
    await session.commit()
    view = await read_models.get_market_day(session, market_event_id)
    return templates.TemplateResponse(request, "partials/_market_lines.html", {"market": view})


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "",
                 session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    results = await read_models.search_designs(session, q) if q else []
    return templates.TemplateResponse(
        request, "partials/_command_results.html", {"results": results}
    )


@router.post("/markets/{market_event_id}/tally", response_class=HTMLResponse)
async def market_tally(request: Request, market_event_id: uuid.UUID,
                       session_data: str = Form(..., alias="session"),
                       session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    try:
        lines = json.loads(session_data)
        params = [
            {"i": uuid.uuid4(), "q": float(ln["quantity"]), "p": float(ln["unit_price"]),
             "v": uuid.UUID(ln["variation_id"]), "c": uuid.UUID(ln["channel_id"]),
             "m": market_event_id}
            for ln in lines
        ]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        # Validate the whole payload before any write, so a bad line is a clean
        # client error (422) rather than a 500 — and never a partial commit.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid tally payload",
        ) from exc
    for p in params:
        await session.execute(text(
            "INSERT INTO maker_sale (id, quantity, unit_price, fees, sale_date, source, "
            "variation_id, channel_id, market_event_id) "
            "VALUES (:i, :q, :p, 0, now(), 'tally', :v, :c, :m)"
        ), p)
    await session.commit()
    view = await read_models.get_market_day(session, market_event_id)
    return templates.TemplateResponse(request, "partials/_market_lines.html", {"market": view})
