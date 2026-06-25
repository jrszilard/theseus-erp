from __future__ import annotations

import json
import re
import uuid
from typing import TYPE_CHECKING, NamedTuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from theseus.bootstrap import build_registry
from theseus.config import settings
from theseus.database import get_session
from theseus.keel.assets.attachment import (
    FileFieldError,
    attach_asset,
    detach_asset,
    resolve_file_field,
)
from theseus.keel.assets.factory import build_storage
from theseus.keel.assets.service import AssetService
from theseus.keel.entities.writer import insert_entity
from theseus.keel.llm_gateway.gateway import LLMGateway
from theseus.planks.maker.capture import llm_available, parse_sale_text
from theseus.planks.maker.insights import MakerInsights
from theseus.planks.maker.service import MakerService
from theseus.web import read_models
from theseus.web.templating import templates

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from theseus.keel.assets.protocols import StorageBackend

class _TallyLine(NamedTuple):
    variation_id: uuid.UUID
    channel_id: uuid.UUID
    quantity: float
    unit_price: float


router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
async def board(
    request: Request, session: AsyncSession = Depends(get_session)  # noqa: B008
) -> HTMLResponse:
    designs = await read_models.list_designs_for_board(session)
    return templates.TemplateResponse(
        request, "board.html", {"designs": designs, "show_welcome": not designs}
    )


@router.post("/designs")
async def create_design(
    request: Request,
    title: str = Form(...),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> RedirectResponse:
    clean = title.strip()
    if not clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="title required"
        )
    slug = re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-") or "design"
    # build_registry() (not get_registry()): reads blueprints from disk so this works
    # regardless of the app-state registry — the test harness registers only a minimal set.
    registry = build_registry()
    bp = registry.get("maker.Design")
    row = await insert_entity(session, bp, {"title": clean, "slug": slug, "status": "idea"})
    await session.commit()
    return RedirectResponse(url=f"/designs/{row['id']}", status_code=status.HTTP_303_SEE_OTHER)


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
    restock = await MakerInsights(session=session).restock()
    return templates.TemplateResponse(request, "bom.html",
                                      {"bom": view, "warehouse_id": str(wh) if wh else "",
                                       "restock": restock})


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


@router.post("/designs/{design_id}/versions/{version_id}/promote")
async def promote_version_route(design_id: uuid.UUID, version_id: uuid.UUID,
                                session: AsyncSession = Depends(get_session)) -> RedirectResponse:  # noqa: B008
    svc = MakerService(session=session)
    try:
        await svc.promote_version(version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return RedirectResponse(f"/designs/{design_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/bom/{variation_id}/reorder")
async def bom_set_reorder(
    variation_id: uuid.UUID,
    stock_item_id: uuid.UUID = Form(...),  # noqa: B008
    value: float = Form(...),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> RedirectResponse:
    svc = MakerService(session=session)
    await svc.set_reorder_point(stock_item_id, value)
    await session.commit()
    return RedirectResponse(f"/bom/{variation_id}", status_code=status.HTTP_303_SEE_OTHER)


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
        "llm_ready": llm_available(),
    })


@router.post("/markets/{market_event_id}/sale", response_class=HTMLResponse)
async def market_sale(request: Request, market_event_id: uuid.UUID,
                      variation_id: uuid.UUID = Form(...), channel_id: uuid.UUID = Form(...),  # noqa: B008
                      quantity: float = Form(...), unit_price: float = Form(...),
                      session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    svc = MakerService(session=session)
    await svc.record_sale(variation_id=variation_id, channel_id=channel_id,
                          quantity=quantity, unit_price=unit_price, source="manual",
                          market_event_id=market_event_id)
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
            _TallyLine(
                variation_id=uuid.UUID(ln["variation_id"]),
                channel_id=uuid.UUID(ln["channel_id"]),
                quantity=float(ln["quantity"]),
                unit_price=float(ln["unit_price"]),
            )
            for ln in lines
        ]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        # Validate the whole payload before any write, so a bad line is a clean
        # client error (422) rather than a 500 — and never a partial commit.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid tally payload",
        ) from exc
    svc = MakerService(session=session)
    for p in params:
        await svc.record_sale(
            variation_id=p.variation_id, channel_id=p.channel_id,
            quantity=p.quantity, unit_price=p.unit_price,
            source="tally", market_event_id=market_event_id,
        )
    await session.commit()
    view = await read_models.get_market_day(session, market_event_id)
    return templates.TemplateResponse(request, "partials/_market_lines.html", {"market": view})


@router.post("/markets/{market_event_id}/capture/parse", response_class=HTMLResponse)
async def capture_parse(request: Request, market_event_id: uuid.UUID,
                        natural: str = Form(...),
                        session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    view = await read_models.get_market_day(session, market_event_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market not found")
    lines = await parse_sale_text(natural, view["variations"], LLMGateway())
    return templates.TemplateResponse(request, "partials/_capture_confirm.html",
                                      {"market": view, "lines": lines})


@router.post("/markets/{market_event_id}/capture/commit", response_class=HTMLResponse)
async def capture_commit(request: Request, market_event_id: uuid.UUID,
                         lines_json: str = Form(..., alias="lines"),
                         session: AsyncSession = Depends(get_session)) -> HTMLResponse:  # noqa: B008
    exists = (await session.execute(
        text("SELECT 1 FROM maker_market_event WHERE id = :m"), {"m": market_event_id})).scalar()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market not found")
    try:
        items = json.loads(lines_json)
        parsed = [(uuid.UUID(i["variation_id"]), float(i["quantity"]), float(i["unit_price"]))
                  for i in items]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="invalid capture payload") from exc
    channel_raw = (await session.execute(
        text("SELECT id FROM maker_channel ORDER BY created_at LIMIT 1"))).scalar()
    if channel_raw is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="no channel configured")
    channel: uuid.UUID = uuid.UUID(str(channel_raw))
    svc = MakerService(session=session)
    try:
        for variation_id, quantity, unit_price in parsed:
            await svc.record_sale(variation_id=variation_id, channel_id=channel,
                                  quantity=quantity, unit_price=unit_price,
                                  source="shipwright_nl", market_event_id=market_event_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="invalid capture payload") from exc
    await session.commit()
    view = await read_models.get_market_day(session, market_event_id)
    return templates.TemplateResponse(request, "partials/_market_lines.html", {"market": view})


def _get_storage() -> StorageBackend:
    """Module-level factory (mockable in tests; mirrors the assets API route)."""
    return build_storage()


def _validate_file_field(ref: str, field_name: str) -> None:
    """404 before any work if ref isn't a known Blueprint or field_name isn't one of
    its declared `file` fields. This is the SQL-identifier whitelist gate."""
    bp = build_registry().get(ref)
    if bp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="entity type not found")
    try:
        resolve_file_field(bp, field_name)
    except FileFieldError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="file field not found"
        ) from exc


async def _file_group_response(
    request: Request, session: AsyncSession, ref: str, entity_id: uuid.UUID,
    field_name: str, error: str | None = None,
) -> HTMLResponse:
    registry = build_registry()
    groups = await read_models.file_groups_for_entity(
        session, registry, ref, entity_id, include_empty=True
    )
    group = next((g for g in groups if g["field_name"] == field_name), None)
    return templates.TemplateResponse(
        request, "partials/_file_group.html",
        {"group": group, "ref": ref, "entity_id": str(entity_id), "error": error},
    )


@router.post("/entities/{ref}/{entity_id}/files/{field_name}", response_class=HTMLResponse)
async def upload_entity_file(
    request: Request, ref: str, entity_id: uuid.UUID, field_name: str,
    files: list[UploadFile] | None = File(None),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> HTMLResponse:
    _validate_file_field(ref, field_name)
    registry = build_registry()
    svc = AssetService(session=session, storage=_get_storage())
    cap = settings.max_upload_bytes
    errors: list[str] = []
    for f in (files or []):
        data = await f.read()
        if not data:
            continue
        if len(data) > cap:
            errors.append(f"{f.filename or 'file'} is too large (max {cap // (1024 * 1024)} MB)")
            continue
        rec = await svc.upload(
            filename=f.filename or "upload.bin",
            content_type=f.content_type or "application/octet-stream",
            data=data, kind=field_name,
        )
        await attach_asset(session, registry, ref, entity_id, field_name, rec.id)
    await session.commit()
    error = "; ".join(errors) if errors else None
    return await _file_group_response(request, session, ref, entity_id, field_name, error)


@router.post(
    "/entities/{ref}/{entity_id}/files/{field_name}/detach/{asset_id}",
    response_class=HTMLResponse,
)
async def detach_entity_file(
    request: Request, ref: str, entity_id: uuid.UUID, field_name: str, asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> HTMLResponse:
    _validate_file_field(ref, field_name)
    await detach_asset(session, build_registry(), ref, entity_id, field_name, asset_id)
    await session.commit()
    return await _file_group_response(request, session, ref, entity_id, field_name)
