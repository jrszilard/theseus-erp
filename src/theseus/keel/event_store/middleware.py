from __future__ import annotations

import uuid

from theseus.keel.event_store.models import EventRecord
from theseus.keel.event_store.store import PostgresEventStore

# Sentinel UUID for system-initiated actions (no logged-in user)
SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


async def emit_entity_event(
    *,
    store: PostgresEventStore,
    action: str,
    plank: str,
    entity: str,
    entity_id: uuid.UUID,
    data: dict,
    actor_id: uuid.UUID | None = None,
) -> EventRecord:
    """Emit a standardized entity event.

    Event type format: '{plank}.{entity}.{action}'
    Examples: 'contacts.Contact.created', 'inventory.StockItem.updated'
    """
    return await store.append(
        event_type=f"{plank}.{entity}.{action}",
        entity_type=entity,
        entity_id=entity_id,
        actor_type="user" if actor_id else "system",
        actor_id=actor_id or SYSTEM_ACTOR_ID,
        data=data,
    )
