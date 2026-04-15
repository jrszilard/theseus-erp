from __future__ import annotations

import uuid
from typing import Any, Protocol

from theseus.keel.event_store.models import EventRecord


class EventStoreProtocol(Protocol):
    """Protocol for the event store subsystem."""
    async def append(self, *, event_type: str, entity_type: str, entity_id: uuid.UUID,
                     actor_type: str, actor_id: uuid.UUID, data: dict[str, Any],
                     metadata: dict[str, Any] | None = None) -> EventRecord: ...
    async def get_events_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[EventRecord]: ...
    async def get_events_by_type(self, event_type: str) -> list[EventRecord]: ...
