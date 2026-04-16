import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.contacts.service import ContactService


class TestContactService:
    @pytest.mark.asyncio
    async def test_create_contact(self, db_session: AsyncSession) -> None:
        svc = ContactService(session=db_session)
        contact = await svc.create_contact(
            name="Acme Corp",
            contact_type="customer",
            email="info@acme.com",
            phone="555-0100",
        )
        assert contact["name"] == "Acme Corp"
        assert contact["contact_type"] == "customer"
        assert "id" in contact

    @pytest.mark.asyncio
    async def test_create_contact_emits_event(self, db_session: AsyncSession) -> None:
        svc = ContactService(session=db_session)
        contact = await svc.create_contact(
            name="Event Test Corp",
            contact_type="supplier",
        )
        store = PostgresEventStore(session=db_session)
        events = await store.get_events_for_entity("Contact", uuid.UUID(contact["id"]))
        assert len(events) == 1
        assert events[0].event_type == "contacts.Contact.created"

    @pytest.mark.asyncio
    async def test_search_contacts_by_name(self, db_session: AsyncSession) -> None:
        svc = ContactService(session=db_session)
        await svc.create_contact(name="Alpha Industries", contact_type="customer")
        await svc.create_contact(name="Beta Corp", contact_type="supplier")
        await svc.create_contact(name="Alpha Services", contact_type="customer")

        results = await svc.search_contacts(name_contains="Alpha")
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Alpha Industries", "Alpha Services"}

    @pytest.mark.asyncio
    async def test_search_contacts_by_type(self, db_session: AsyncSession) -> None:
        svc = ContactService(session=db_session)
        await svc.create_contact(name="Customer A", contact_type="customer")
        await svc.create_contact(name="Supplier B", contact_type="supplier")
        await svc.create_contact(name="Customer C", contact_type="customer")

        results = await svc.search_contacts(contact_type="customer")
        assert all(r["contact_type"] == "customer" for r in results)
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_get_contact_with_addresses(self, db_session: AsyncSession) -> None:
        svc = ContactService(session=db_session)
        contact = await svc.create_contact(name="Multi Address Inc", contact_type="customer")
        contact_id = uuid.UUID(contact["id"])

        await svc.add_address(
            contact_id=contact_id,
            street="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62701",
        )
        await svc.add_address(
            contact_id=contact_id,
            label="shipping",
            street="456 Oak Ave",
            city="Springfield",
            state="IL",
            postal_code="62702",
        )

        full = await svc.get_contact_with_addresses(contact_id)
        assert full["name"] == "Multi Address Inc"
        assert len(full["addresses"]) == 2
