"""Tool executor — bridges Shipwright tool calls to Keel operations."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.api.dependencies import get_blueprint, get_registry
from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.contacts.service import ContactService
from theseus.planks.inventory.service import InventoryService

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes Shipwright tool calls against the Keel and Plank services."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresEventStore(session=session)

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a named tool with the given arguments.

        Returns: {"success": bool, "data": Any, "error": str | None}
        """
        handler = self._get_handler(tool_name)
        if handler is None:
            return {"success": False, "data": None, "error": f"Unknown tool: {tool_name}"}

        try:
            data = await handler(arguments)
            return {"success": True, "data": data, "error": None}
        except Exception as e:
            logger.error("Tool execution error (%s): %s", tool_name, str(e))
            return {"success": False, "data": None, "error": str(e)}

    def _get_handler(self, tool_name: str):
        handlers = {
            "create_entity": self._create_entity,
            "query_entities": self._query_entities,
            "get_entity": self._get_entity,
            "update_entity": self._update_entity,
            "get_stock_level": self._get_stock_level,
            "search_contacts": self._search_contacts,
        }
        return handlers.get(tool_name)

    async def _create_entity(self, args: dict[str, Any]) -> dict[str, Any]:
        plank = args["plank"]
        entity = args["entity"]
        data = args["data"]

        bp = get_blueprint(plank, entity)
        entity_id = uuid.uuid4()

        # Filter to valid Blueprint fields
        valid_fields = set(bp.fields.keys())
        computed = {n for n, f in bp.fields.items() if f.computed}
        columns = {k: v for k, v in data.items() if k in valid_fields and k not in computed}
        columns["id"] = entity_id

        col_names = ", ".join(columns.keys())
        col_params = ", ".join(f":{k}" for k in columns.keys())
        query = text(f"INSERT INTO {bp.table_name} ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, columns)

        await emit_entity_event(
            store=self._store, action="created", plank=plank,
            entity=entity, entity_id=entity_id, data=data,
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def _query_entities(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        plank = args["plank"]
        entity = args["entity"]
        bp = get_blueprint(plank, entity)

        query = text(f"SELECT * FROM {bp.table_name} ORDER BY created_at DESC LIMIT 50")
        result = await self._session.execute(query)
        return [_row_to_dict(row) for row in result.mappings().all()]

    async def _get_entity(self, args: dict[str, Any]) -> dict[str, Any]:
        plank = args["plank"]
        entity = args["entity"]
        entity_id = args["entity_id"]
        bp = get_blueprint(plank, entity)

        query = text(f"SELECT * FROM {bp.table_name} WHERE id = :id")
        result = await self._session.execute(query, {"id": entity_id})
        row = result.mappings().one_or_none()
        if row is None:
            raise ValueError(f"{entity} with id {entity_id} not found")
        return _row_to_dict(row)

    async def _update_entity(self, args: dict[str, Any]) -> dict[str, Any]:
        plank = args["plank"]
        entity = args["entity"]
        entity_id = args["entity_id"]
        data = args["data"]
        bp = get_blueprint(plank, entity)

        valid_fields = set(bp.fields.keys())
        computed = {n for n, f in bp.fields.items() if f.computed}
        columns = {k: v for k, v in data.items() if k in valid_fields and k not in computed}

        set_clause = ", ".join(f"{k} = :{k}" for k in columns.keys())
        columns["id"] = entity_id
        query = text(
            f"UPDATE {bp.table_name} SET {set_clause}, updated_at = now() "
            f"WHERE id = :id RETURNING *"
        )
        result = await self._session.execute(query, columns)
        await emit_entity_event(
            store=self._store, action="updated", plank=plank,
            entity=entity, entity_id=uuid.UUID(entity_id), data=data,
        )
        await self._session.flush()
        row = result.mappings().one_or_none()
        if row is None:
            raise ValueError(f"{entity} with id {entity_id} not found")
        return _row_to_dict(row)

    async def _get_stock_level(self, args: dict[str, Any]) -> dict[str, Any]:
        svc = InventoryService(session=self._session)
        item_id = uuid.UUID(args["stock_item_id"])
        level = await svc.get_stock_level(item_id)
        return {"stock_item_id": args["stock_item_id"], "current_stock": level}

    async def _search_contacts(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        svc = ContactService(session=self._session)
        return await svc.search_contacts(
            name_contains=args.get("name_contains"),
            contact_type=args.get("contact_type"),
        )


def _row_to_dict(row: Any) -> dict[str, Any]:
    from decimal import Decimal
    from datetime import date, datetime
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
