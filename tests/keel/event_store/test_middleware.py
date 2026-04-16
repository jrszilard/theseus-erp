import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore


class TestEmitEntityEvent:
    @pytest.mark.asyncio
    async def test_emit_create_event(self, db_session: AsyncSession) -> None:
        store = PostgresEventStore(session=db_session)
        entity_id = uuid.uuid4()
        event = await emit_entity_event(
            store=store,
            action="created",
            plank="test",
            entity="Widget",
            entity_id=entity_id,
            data={"name": "Test Widget", "color": "red"},
            actor_id=None,
        )
        assert event.event_type == "test.Widget.created"
        assert event.entity_type == "Widget"
        assert event.entity_id == entity_id
        assert event.data == {"name": "Test Widget", "color": "red"}

    @pytest.mark.asyncio
    async def test_emit_updated_event(self, db_session: AsyncSession) -> None:
        store = PostgresEventStore(session=db_session)
        entity_id = uuid.uuid4()
        event = await emit_entity_event(
            store=store,
            action="updated",
            plank="inventory",
            entity="StockItem",
            entity_id=entity_id,
            data={"name": "Updated Item"},
            actor_id=uuid.uuid4(),
        )
        assert event.event_type == "inventory.StockItem.updated"
        assert event.actor_type == "user"

    @pytest.mark.asyncio
    async def test_emit_with_system_actor_when_no_user(self, db_session: AsyncSession) -> None:
        store = PostgresEventStore(session=db_session)
        event = await emit_entity_event(
            store=store,
            action="created",
            plank="test",
            entity="Widget",
            entity_id=uuid.uuid4(),
            data={"name": "System Widget"},
            actor_id=None,
        )
        assert event.actor_type == "system"
