import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from theseus.keel.event_store.store import PostgresEventStore


@pytest.fixture
def event_store(db_session: AsyncSession) -> PostgresEventStore:
    return PostgresEventStore(session=db_session)


class TestPostgresEventStore:
    @pytest.mark.asyncio
    async def test_append_event(self, event_store: PostgresEventStore) -> None:
        event = await event_store.append(event_type="test.ItemCreated", entity_type="Widget",
            entity_id=uuid.uuid4(), actor_type="user", actor_id=uuid.uuid4(),
            data={"name": "Test Widget", "color": "red"})
        assert event.event_id is not None
        assert event.event_type == "test.ItemCreated"
        assert event.data == {"name": "Test Widget", "color": "red"}

    @pytest.mark.asyncio
    async def test_get_events_for_entity(self, event_store: PostgresEventStore) -> None:
        entity_id = uuid.uuid4()
        await event_store.append(event_type="test.Created", entity_type="Widget",
            entity_id=entity_id, actor_type="user", actor_id=uuid.uuid4(), data={"name": "Widget A"})
        await event_store.append(event_type="test.Updated", entity_type="Widget",
            entity_id=entity_id, actor_type="user", actor_id=uuid.uuid4(), data={"name": "Widget A (updated)"})
        events = await event_store.get_events_for_entity("Widget", entity_id)
        assert len(events) == 2
        assert events[0].event_type == "test.Created"
        assert events[1].event_type == "test.Updated"

    @pytest.mark.asyncio
    async def test_get_events_by_type(self, event_store: PostgresEventStore) -> None:
        actor_id = uuid.uuid4()
        await event_store.append(event_type="inventory.StockAdjusted", entity_type="StockItem",
            entity_id=uuid.uuid4(), actor_type="user", actor_id=actor_id, data={"quantity_change": -5})
        await event_store.append(event_type="inventory.StockAdjusted", entity_type="StockItem",
            entity_id=uuid.uuid4(), actor_type="user", actor_id=actor_id, data={"quantity_change": 10})
        await event_store.append(event_type="contacts.ContactCreated", entity_type="Contact",
            entity_id=uuid.uuid4(), actor_type="user", actor_id=actor_id, data={"name": "Acme"})
        events = await event_store.get_events_by_type("inventory.StockAdjusted")
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_events_are_ordered_by_timestamp(self, event_store: PostgresEventStore) -> None:
        entity_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        for i in range(5):
            await event_store.append(event_type=f"test.Event{i}", entity_type="Widget",
                entity_id=entity_id, actor_type="user", actor_id=actor_id, data={"sequence": i})
        events = await event_store.get_events_for_entity("Widget", entity_id)
        sequences = [e.data["sequence"] for e in events]
        assert sequences == [0, 1, 2, 3, 4]
