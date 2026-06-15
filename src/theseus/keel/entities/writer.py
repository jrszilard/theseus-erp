from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from theseus.keel.blueprint_engine.models import Blueprint


def extract_columns(bp: Blueprint, body: dict[str, Any]) -> dict[str, Any]:
    valid = set(bp.fields.keys())
    computed = {n for n, f in bp.fields.items() if f.computed}
    return {k: v for k, v in body.items() if k in valid and k not in computed}


def row_to_dict(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        out[key] = str(value) if isinstance(value, uuid.UUID) else value
    return out


async def insert_entity(
    session: AsyncSession,
    bp: Blueprint,
    body: dict[str, Any],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """INSERT one entity row + emit its creation event. Does NOT commit."""
    entity_id = uuid.uuid4()
    columns = extract_columns(bp, body)
    columns["id"] = entity_id
    names = ", ".join(columns.keys())
    params = ", ".join(f":{k}" for k in columns)
    result = await session.execute(
        text(f"INSERT INTO {bp.table_name} ({names}) VALUES ({params}) RETURNING *"),
        columns,
    )
    store = PostgresEventStore(session=session)
    await emit_entity_event(
        store=store, action="created", plank=bp.plank, entity=bp.entity,
        entity_id=entity_id, data=body, actor_id=actor_id,
    )
    return row_to_dict(result.mappings().one())


async def find_existing_by_unique(
    session: AsyncSession, bp: Blueprint, body: dict[str, Any]
) -> dict[str, Any] | None:
    """Return an existing row if any unique field in `body` already has that value."""
    unique_fields = [n for n, f in bp.fields.items() if f.unique]
    for uf in unique_fields:
        if uf in body and body[uf] is not None:
            row = (
                await session.execute(
                    text(f"SELECT * FROM {bp.table_name} WHERE {uf} = :v"), {"v": body[uf]}
                )
            ).mappings().one_or_none()
            if row is not None:
                return row_to_dict(row)
    return None
