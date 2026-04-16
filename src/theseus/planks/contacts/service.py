from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore


class ContactService:
    """Domain service for the Contacts Plank."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresEventStore(session=session)

    async def create_contact(
        self,
        *,
        name: str,
        contact_type: str,
        company: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        contact_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": contact_id,
            "name": name,
            "contact_type": contact_type,
            "is_active": True,
        }
        if company is not None:
            params["company"] = company
        if email is not None:
            params["email"] = email
        if phone is not None:
            params["phone"] = phone
        if notes is not None:
            params["notes"] = notes

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO contacts_contact ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="contacts",
            entity="Contact", entity_id=contact_id,
            data={k: str(v) if isinstance(v, uuid.UUID) else v for k, v in params.items()},
        )
        await self._session.flush()
        row = result.mappings().one()
        return _row_to_dict(row)

    async def search_contacts(
        self,
        *,
        name_contains: str | None = None,
        contact_type: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if name_contains:
            conditions.append("name ILIKE :name_pattern")
            params["name_pattern"] = f"%{name_contains}%"
        if contact_type:
            conditions.append("contact_type = :contact_type")
            params["contact_type"] = contact_type

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = text(f"SELECT * FROM contacts_contact WHERE {where_clause} ORDER BY name")
        result = await self._session.execute(query, params)
        return [_row_to_dict(row) for row in result.mappings().all()]

    async def add_address(
        self,
        *,
        contact_id: uuid.UUID,
        street: str,
        city: str,
        label: str = "primary",
        state: str | None = None,
        postal_code: str | None = None,
        country: str = "US",
    ) -> dict[str, Any]:
        address_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": address_id,
            "contact_id": contact_id,
            "label": label,
            "street": street,
            "city": city,
            "country": country,
        }
        if state is not None:
            params["state"] = state
        if postal_code is not None:
            params["postal_code"] = postal_code

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO contacts_address ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)
        await self._session.flush()
        row = result.mappings().one()
        return _row_to_dict(row)

    async def get_contact_with_addresses(self, contact_id: uuid.UUID) -> dict[str, Any]:
        contact_query = text("SELECT * FROM contacts_contact WHERE id = :id")
        contact_result = await self._session.execute(contact_query, {"id": contact_id})
        contact_row = contact_result.mappings().one_or_none()
        if contact_row is None:
            msg = f"Contact {contact_id} not found"
            raise ValueError(msg)

        address_query = text(
            "SELECT * FROM contacts_address WHERE contact_id = :contact_id ORDER BY label"
        )
        address_result = await self._session.execute(address_query, {"contact_id": contact_id})

        contact = _row_to_dict(contact_row)
        contact["addresses"] = [_row_to_dict(row) for row in address_result.mappings().all()]
        return contact


def _row_to_dict(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        else:
            result[key] = value
    return result
