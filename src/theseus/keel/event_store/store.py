from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.models import Event, EventRecord


class PostgresEventStore:
    """Append-only event store backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, *, event_type: str, entity_type: str, entity_id: uuid.UUID,
                     actor_type: str, actor_id: uuid.UUID, data: dict[str, Any],
                     metadata: dict[str, Any] | None = None) -> EventRecord:
        event = Event(event_type=event_type, entity_type=entity_type, entity_id=entity_id,
                      actor_type=actor_type, actor_id=actor_id, data=data, metadata_=metadata or {})
        self._session.add(event)
        await self._session.flush()
        return EventRecord.model_validate(event)

    async def get_events_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[EventRecord]:
        stmt = (select(Event)
                .where(Event.entity_type == entity_type, Event.entity_id == entity_id)
                .order_by(Event.timestamp.asc()))
        result = await self._session.execute(stmt)
        return [EventRecord.model_validate(row) for row in result.scalars().all()]

    async def get_events_by_type(self, event_type: str) -> list[EventRecord]:
        stmt = (select(Event).where(Event.event_type == event_type).order_by(Event.timestamp.asc()))
        result = await self._session.execute(stmt)
        return [EventRecord.model_validate(row) for row in result.scalars().all()]
