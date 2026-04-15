from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.api.dependencies import get_blueprint
from theseus.database import get_session

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.post("/{plank}/{entity}", status_code=status.HTTP_201_CREATED)
async def create_entity(plank: str, entity: str, body: dict[str, Any],
                        session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    bp = get_blueprint(plank, entity)
    entity_id = uuid.uuid4()
    columns = _extract_columns(bp, body)
    columns["id"] = entity_id
    col_names = ", ".join(columns.keys())
    col_params = ", ".join(f":{k}" for k in columns.keys())
    query = text(f"INSERT INTO {bp.table_name} ({col_names}) VALUES ({col_params}) RETURNING *")
    result = await session.execute(query, columns)
    await session.commit()
    row = result.mappings().one()
    return _row_to_dict(row)


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
    await session.commit()
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"{entity} with id {entity_id} not found")
    return _row_to_dict(row)


def _extract_columns(bp, body: dict[str, Any]) -> dict[str, Any]:
    valid_fields = set(bp.fields.keys())
    computed_fields = {name for name, field in bp.fields.items() if field.computed}
    return {k: v for k, v in body.items() if k in valid_fields and k not in computed_fields}


def _row_to_dict(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        else:
            result[key] = value
    return result
