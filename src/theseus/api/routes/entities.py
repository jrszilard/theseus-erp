from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.api.dependencies import get_blueprint
from theseus.database import get_session
from theseus.keel.entities.writer import (
    extract_columns as _extract_columns,
    insert_entity,
    row_to_dict as _row_to_dict,
)
from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.post("/{plank}/{entity}", status_code=status.HTTP_201_CREATED)
async def create_entity(plank: str, entity: str, body: dict[str, Any],
                        session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    bp = get_blueprint(plank, entity)
    row = await insert_entity(session, bp, body)
    await session.commit()
    return row


@router.get("/{plank}/{entity}")
async def list_entities(plank: str, entity: str,
                        session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    bp = get_blueprint(plank, entity)
    query = text(f"SELECT * FROM {bp.table_name} ORDER BY created_at DESC")
    result = await session.execute(query)
    return [_row_to_dict(row) for row in result.mappings().all()]


@router.get("/{plank}/{entity}/{entity_id}")
async def get_entity(plank: str, entity: str, entity_id: uuid.UUID,
                     session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    bp = get_blueprint(plank, entity)
    query = text(f"SELECT * FROM {bp.table_name} WHERE id = :id")
    result = await session.execute(query, {"id": entity_id})
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"{entity} with id {entity_id} not found")
    return _row_to_dict(row)


@router.patch("/{plank}/{entity}/{entity_id}")
async def update_entity(plank: str, entity: str, entity_id: uuid.UUID, body: dict[str, Any],
                        session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    bp = get_blueprint(plank, entity)
    columns = _extract_columns(bp, body)
    if not columns:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No valid fields to update")
    set_clause = ", ".join(f"{k} = :{k}" for k in columns.keys())
    columns["id"] = entity_id
    query = text(f"UPDATE {bp.table_name} SET {set_clause}, updated_at = now() WHERE id = :id RETURNING *")
    result = await session.execute(query, columns)

    # Auto-emit update event
    store = PostgresEventStore(session=session)
    await emit_entity_event(
        store=store, action="updated", plank=plank, entity=entity,
        entity_id=entity_id, data=body,
    )

    await session.commit()
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"{entity} with id {entity_id} not found")
    return _row_to_dict(row)


