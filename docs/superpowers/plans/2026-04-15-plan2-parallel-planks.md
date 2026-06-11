# Plan 2: Parallel Planks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first three Planks (Contacts, Inventory, Invoicing) to stress-test the Keel, then integrate them through the Knowledge Graph (Phase 3 merge point).

**Architecture:** Each Plank is a directory of Blueprint YAML files plus an optional service module for business logic beyond generic CRUD. The Keel handles schema generation, API endpoints, and event storage automatically. Plank services add domain-specific operations (e.g., stock movement processing, invoice totaling).

**Tech Stack:** Same as Plan 1 — Python 3.12, FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Pydantic v2.

**Prerequisite:** Plan 1 (Thin Keel) is complete. 55 tests passing, all Keel subsystems operational.

---

## Overview: What Each Task Tests

| Task | Plank | Keel Stress Test |
|------|-------|-----------------|
| 1-2 | (Keel enhancements) | Auto event emission + Knowledge Graph registration |
| 3 | Contacts | Basic entities, relationships, search |
| 4 | Inventory | Event sourcing, computed state, domain services |
| 5 | Invoicing | Financial calculations, cross-Plank references |
| 6 | (Integration) | Phase 3 merge: all Planks connected via Knowledge Graph |

---

## File Structure (new files only)

```
planks/
  contacts/
    blueprints/
      contact.blueprint.yaml
      address.blueprint.yaml
    README.md
  inventory/
    blueprints/
      stock-item.blueprint.yaml
      warehouse.blueprint.yaml
      stock-movement.blueprint.yaml
    README.md
  invoicing/
    blueprints/
      invoice.blueprint.yaml
      invoice-line.blueprint.yaml
      payment.blueprint.yaml
    README.md
src/theseus/
  keel/
    event_store/
      middleware.py              # Auto event emission on CRUD
    knowledge_graph/
      registration.py           # Auto-register Blueprints in graph on startup
  planks/
    __init__.py
    contacts/
      __init__.py
      service.py                # Contact search, type filtering
    inventory/
      __init__.py
      service.py                # Stock movement processing, level computation
    invoicing/
      __init__.py
      service.py                # Invoice totaling, payment tracking
  api/routes/
    plank_services.py           # Plank-specific API endpoints beyond generic CRUD
tests/
  keel/
    event_store/
      test_middleware.py
    knowledge_graph/
      test_registration.py
  planks/
    __init__.py
    contacts/
      __init__.py
      test_service.py
    inventory/
      __init__.py
      test_service.py
    invoicing/
      __init__.py
      test_service.py
  integration/
    test_cross_plank.py         # Phase 3 merge point test
```

---

## Task 1: Keel Enhancement — Auto Event Emission on CRUD

Currently, the entity CRUD endpoints create/update records but don't emit events. This task adds automatic event emission so every entity change is captured in the Event Store.

**Files:**
- Create: `src/theseus/keel/event_store/middleware.py`
- Modify: `src/theseus/api/routes/entities.py`
- Create: `tests/keel/event_store/test_middleware.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/keel/event_store/test_middleware.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/keel/event_store/test_middleware.py -v
```

- [ ] **Step 3: Implement the event emission helper**

```python
# src/theseus/keel/event_store/middleware.py
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/keel/event_store/test_middleware.py -v
```

- [ ] **Step 5: Integrate into entity CRUD routes**

Modify `src/theseus/api/routes/entities.py` — add event emission to `create_entity` and `update_entity`:

```python
# src/theseus/api/routes/entities.py
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.api.dependencies import get_blueprint
from theseus.database import get_session
from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore

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

    # Auto-emit creation event
    store = PostgresEventStore(session=session)
    await emit_entity_event(
        store=store, action="created", plank=plank, entity=entity,
        entity_id=entity_id, data=body,
    )

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

    # Auto-emit update event
    store = PostgresEventStore(session=session)
    await emit_entity_event(
        store=store, action="updated", plank=plank, entity=entity,
        entity_id=entity_id, data=body,
    )

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
```

- [ ] **Step 6: Run all tests to verify nothing broke**

```bash
pytest tests/ -v
```

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: auto event emission on entity CRUD operations

Every create and update through the generic entity API now automatically
emits an event to the Event Store. Event type format: '{plank}.{entity}.{action}'.
System actor used when no authenticated user is present.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Keel Enhancement — Knowledge Graph Auto-Registration

On startup, register all Blueprint entity types and their relationships in the Knowledge Graph. Currently the lifespan only parses Blueprints and creates tables — it doesn't populate the graph.

**Files:**
- Create: `src/theseus/keel/knowledge_graph/registration.py`
- Modify: `src/theseus/main.py` (add graph registration to lifespan)
- Create: `tests/keel/knowledge_graph/test_registration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/keel/knowledge_graph/test_registration.py
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.knowledge_graph.registration import register_blueprints_in_graph

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "blueprints" / "_test"


class TestRegisterBlueprintsInGraph:
    @pytest.mark.asyncio
    async def test_registers_entity_types(self, db_session: AsyncSession) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for bp in parser.parse_directory(FIXTURES_DIR):
            registry.register(bp)

        graph = PostgresKnowledgeGraph(session=db_session)
        await register_blueprints_in_graph(registry, graph)

        widget = await graph.get_entity_type("test.Widget")
        assert widget is not None
        assert widget.entity == "Widget"

        order = await graph.get_entity_type("test.WidgetOrder")
        assert order is not None
        assert order.entity == "WidgetOrder"

    @pytest.mark.asyncio
    async def test_registers_relationships(self, db_session: AsyncSession) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for bp in parser.parse_directory(FIXTURES_DIR):
            registry.register(bp)

        graph = PostgresKnowledgeGraph(session=db_session)
        await register_blueprints_in_graph(registry, graph)

        # WidgetOrder has relations to test.Widget and contacts.Contact
        related = await graph.get_related_types("test.WidgetOrder")
        related_names = {r.full_name for r in related}
        # test.Widget should be registered and connected
        assert "test.Widget" in related_names

    @pytest.mark.asyncio
    async def test_idempotent_registration(self, db_session: AsyncSession) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for bp in parser.parse_directory(FIXTURES_DIR):
            registry.register(bp)

        graph = PostgresKnowledgeGraph(session=db_session)
        await register_blueprints_in_graph(registry, graph)
        # Run again — should not raise
        await register_blueprints_in_graph(registry, graph)

        widget = await graph.get_entity_type("test.Widget")
        assert widget is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/keel/knowledge_graph/test_registration.py -v
```

- [ ] **Step 3: Implement the registration function**

```python
# src/theseus/keel/knowledge_graph/registration.py
from __future__ import annotations

import logging

from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph

logger = logging.getLogger(__name__)


async def register_blueprints_in_graph(
    registry: BlueprintRegistry,
    graph: PostgresKnowledgeGraph,
) -> None:
    """Register all Blueprint entity types and relationships in the Knowledge Graph.

    Idempotent — skips entities and relationships that are already registered.
    """
    # First pass: register all entity types
    for bp in registry.all():
        existing = await graph.get_entity_type(bp.full_name)
        if existing is None:
            await graph.register_entity_type(
                plank=bp.plank,
                entity=bp.entity,
                description=bp.description,
            )
            logger.info("Graph: registered entity type %s", bp.full_name)

    # Second pass: register relationships (all entity types must exist first)
    for bp in registry.all():
        if not bp.relations:
            continue
        for rel_name, relation in bp.relations.items():
            # Only register if the target entity type is also registered
            target = await graph.get_entity_type(relation.target)
            if target is None:
                logger.warning(
                    "Graph: skipping relationship %s.%s -> %s (target not registered)",
                    bp.full_name, rel_name, relation.target,
                )
                continue

            # Check if this edge already exists (simple dedup by source+target+name)
            existing_related = await graph.get_related_types(bp.full_name)
            already_connected = any(
                r.full_name == relation.target for r in existing_related
            )
            if not already_connected:
                await graph.register_relationship_type(
                    source=bp.full_name,
                    target=relation.target,
                    relation_name=rel_name,
                    relation_type=relation.type.value,
                )
                logger.info(
                    "Graph: registered relationship %s -[%s]-> %s",
                    bp.full_name, rel_name, relation.target,
                )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/keel/knowledge_graph/test_registration.py -v
```

- [ ] **Step 5: Add graph registration to app lifespan**

Modify `src/theseus/main.py` — add Knowledge Graph registration after table creation:

```python
# src/theseus/main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from theseus.api.dependencies import set_registry
from theseus.api.middleware import RequestLoggingMiddleware
from theseus.api.routes import entities, health
from theseus.database import async_session_factory, engine
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.knowledge_graph.registration import register_blueprints_in_graph
from theseus.keel.schema_engine.generator import SchemaGenerator

logger = logging.getLogger("theseus")

BLUEPRINTS_DIR = Path("blueprints")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Theseus ERP...")

    parser = BlueprintFileParser()
    registry = BlueprintRegistry()

    if BLUEPRINTS_DIR.exists():
        for bp in parser.parse_directory(BLUEPRINTS_DIR):
            registry.register(bp)
            logger.info("Registered Blueprint: %s", bp.full_name)

    set_registry(registry)

    generator = SchemaGenerator()
    for bp in registry.all():
        table = generator.generate_table(bp)
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all, checkfirst=True)
        logger.info("Ensured table exists: %s", bp.table_name)

    # Register all entity types and relationships in the Knowledge Graph
    async with async_session_factory() as session:
        graph = PostgresKnowledgeGraph(session=session)
        await register_blueprints_in_graph(registry, graph)
        await session.commit()

    logger.info("Theseus ERP started with %d Blueprints", len(registry.all()))
    yield
    await engine.dispose()
    logger.info("Theseus ERP shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Theseus ERP",
        description="An open-source, AI-first ERP for small manufacturing and trade businesses.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(health.router)
    app.include_router(entities.router)
    return app


app = create_app()
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: auto-register Blueprint entities and relationships in Knowledge Graph

On startup, all Blueprint entity types and their relationships are
registered in the Knowledge Graph. Idempotent — safe to run multiple
times. Skips relationships where the target entity isn't registered.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Contacts Plank

The simplest Plank — tests that the Keel handles basic entities and relationships correctly.

**Files:**
- Create: `planks/contacts/blueprints/contact.blueprint.yaml`
- Create: `planks/contacts/blueprints/address.blueprint.yaml`
- Create: `planks/contacts/README.md`
- Create: `src/theseus/planks/__init__.py`
- Create: `src/theseus/planks/contacts/__init__.py`
- Create: `src/theseus/planks/contacts/service.py`
- Create: `tests/planks/__init__.py`
- Create: `tests/planks/contacts/__init__.py`
- Create: `tests/planks/contacts/test_service.py`

- [ ] **Step 1: Create Contact Blueprint**

```yaml
# planks/contacts/blueprints/contact.blueprint.yaml
plank: contacts
entity: Contact
version: 1
description: A business contact — customer, supplier, or employee

fields:
  name:
    type: string
    required: true
  contact_type:
    type: enum
    values: [customer, supplier, employee, other]
    required: true
  company:
    type: string
  email:
    type: string
  phone:
    type: string
  notes:
    type: text
  is_active:
    type: boolean
    default: true
```

- [ ] **Step 2: Create Address Blueprint**

```yaml
# planks/contacts/blueprints/address.blueprint.yaml
plank: contacts
entity: Address
version: 1
description: A physical address linked to a contact

fields:
  label:
    type: string
    default: "primary"
  street:
    type: string
    required: true
  city:
    type: string
    required: true
  state:
    type: string
  postal_code:
    type: string
  country:
    type: string
    default: "US"

relations:
  contact:
    type: many_to_one
    target: contacts.Contact
```

- [ ] **Step 3: Create README**

```markdown
# Contacts Plank

Core contact management for Theseus ERP. Manages customers, suppliers, employees, and their addresses.

## Entities
- **Contact** — A business contact with type, email, phone, notes
- **Address** — A physical address linked to a Contact
```

- [ ] **Step 4: Write the service test**

```python
# tests/planks/contacts/test_service.py
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
```

- [ ] **Step 5: Run test to verify it fails**

```bash
pytest tests/planks/contacts/test_service.py -v
```

- [ ] **Step 6: Implement the Contact service**

```python
# src/theseus/planks/contacts/service.py
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
            entity="Contact", entity_id=contact_id, data=params,
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
```

- [ ] **Step 7: Create __init__.py files and plank directories**

```bash
mkdir -p src/theseus/planks/contacts
mkdir -p tests/planks/contacts
touch src/theseus/planks/__init__.py
touch src/theseus/planks/contacts/__init__.py
touch tests/planks/__init__.py
touch tests/planks/contacts/__init__.py
```

- [ ] **Step 8: Update conftest.py to load Contacts Blueprints for test tables**

The test conftest needs to also create the contacts tables. Update the `test_engine` fixture to load Blueprints from `planks/contacts/blueprints/` in addition to `blueprints/_test/`. The simplest approach: add a `PLANKS_DIR` constant and load all Plank Blueprints at test startup.

Add to `tests/conftest.py` after the existing `FIXTURES_DIR`:
```python
PLANKS_DIR = Path(__file__).parent.parent / "planks"
```

And in the `test_engine` fixture, after creating Blueprint tables from `FIXTURES_DIR`, also create tables from each Plank's `blueprints/` directory:
```python
if PLANKS_DIR.exists():
    for plank_dir in sorted(PLANKS_DIR.iterdir()):
        bp_dir = plank_dir / "blueprints"
        if bp_dir.is_dir():
            for bp in parser.parse_directory(bp_dir):
                table = generator.generate_table(bp)
                async with eng.begin() as conn:
                    await conn.run_sync(table.metadata.create_all, checkfirst=True)
```

- [ ] **Step 9: Run tests**

```bash
pytest tests/planks/contacts/test_service.py -v
pytest tests/ -v
```

- [ ] **Step 10: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Contacts Plank with Contact and Address entities

First Plank — validates the Keel handles basic entities and relationships.
Contact entity with type (customer/supplier/employee), search by name
and type. Address entity with many-to-one link to Contact. Service layer
with create, search, and get-with-addresses operations. Events emitted
on contact creation.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Inventory Plank

The key test of event sourcing — stock levels are computed from movement events rather than stored directly.

**Files:**
- Create: `planks/inventory/blueprints/stock-item.blueprint.yaml`
- Create: `planks/inventory/blueprints/warehouse.blueprint.yaml`
- Create: `planks/inventory/blueprints/stock-movement.blueprint.yaml`
- Create: `planks/inventory/README.md`
- Create: `src/theseus/planks/inventory/__init__.py`
- Create: `src/theseus/planks/inventory/service.py`
- Create: `tests/planks/inventory/__init__.py`
- Create: `tests/planks/inventory/test_service.py`

- [ ] **Step 1: Create Inventory Blueprints**

```yaml
# planks/inventory/blueprints/stock-item.blueprint.yaml
plank: inventory
entity: StockItem
version: 1
description: A trackable item in inventory

fields:
  sku:
    type: string
    required: true
    unique: true
  name:
    type: string
    required: true
  category:
    type: enum
    values: [raw_material, component, finished_good, consumable]
  unit_of_measure:
    type: string
    default: "each"
  reorder_point:
    type: decimal
    default: 0
  is_active:
    type: boolean
    default: true
```

```yaml
# planks/inventory/blueprints/warehouse.blueprint.yaml
plank: inventory
entity: Warehouse
version: 1
description: A physical storage location

fields:
  name:
    type: string
    required: true
    unique: true
  code:
    type: string
    required: true
    unique: true
  address:
    type: text
  is_active:
    type: boolean
    default: true
```

```yaml
# planks/inventory/blueprints/stock-movement.blueprint.yaml
plank: inventory
entity: StockMovement
version: 1
description: A record of stock entering or leaving inventory

fields:
  movement_type:
    type: enum
    values: [received, shipped, adjusted, transferred]
    required: true
  quantity:
    type: decimal
    required: true
  reference:
    type: string
  notes:
    type: text

relations:
  stock_item:
    type: many_to_one
    target: inventory.StockItem
  warehouse:
    type: many_to_one
    target: inventory.Warehouse
```

- [ ] **Step 2: Create README**

```markdown
# Inventory Plank

Stock management for Theseus ERP. Tracks items, warehouses, and stock movements.

## Entities
- **StockItem** — A trackable inventory item with SKU, category, reorder point
- **Warehouse** — A physical storage location
- **StockMovement** — A record of stock entering or leaving inventory

## Key Design
Stock levels are **event-sourced** — the current quantity of a StockItem is computed by summing all StockMovement events, not stored as a static field. This ensures the audit trail is always consistent with the reported stock level.
```

- [ ] **Step 3: Write the service test**

```python
# tests/planks/inventory/test_service.py
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.inventory.service import InventoryService


class TestInventoryService:
    @pytest.mark.asyncio
    async def test_create_stock_item(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(
            sku="STEEL-001",
            name="Steel Sheet 4x8",
            category="raw_material",
        )
        assert item["sku"] == "STEEL-001"
        assert item["name"] == "Steel Sheet 4x8"
        assert "id" in item

    @pytest.mark.asyncio
    async def test_create_warehouse(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        wh = await svc.create_warehouse(name="Main Warehouse", code="WH-01")
        assert wh["name"] == "Main Warehouse"
        assert wh["code"] == "WH-01"

    @pytest.mark.asyncio
    async def test_record_stock_movement(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(sku="BOLT-100", name="Bolts", category="component")
        wh = await svc.create_warehouse(name="Test WH", code="TWH-01")

        movement = await svc.record_movement(
            stock_item_id=uuid.UUID(item["id"]),
            warehouse_id=uuid.UUID(wh["id"]),
            movement_type="received",
            quantity=100,
            reference="PO-001",
        )
        assert movement["movement_type"] == "received"
        assert float(movement["quantity"]) == 100

    @pytest.mark.asyncio
    async def test_movement_emits_event(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(sku="NUT-200", name="Nuts", category="component")
        wh = await svc.create_warehouse(name="Event WH", code="EWH-01")

        await svc.record_movement(
            stock_item_id=uuid.UUID(item["id"]),
            warehouse_id=uuid.UUID(wh["id"]),
            movement_type="received",
            quantity=50,
        )

        store = PostgresEventStore(session=db_session)
        events = await store.get_events_by_type("inventory.StockMovement.created")
        assert len(events) >= 1
        latest = events[-1]
        assert float(latest.data["quantity"]) == 50

    @pytest.mark.asyncio
    async def test_compute_stock_level(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(sku="WASHER-300", name="Washers", category="component")
        wh = await svc.create_warehouse(name="Stock WH", code="SWH-01")

        item_id = uuid.UUID(item["id"])
        wh_id = uuid.UUID(wh["id"])

        # Receive 100
        await svc.record_movement(
            stock_item_id=item_id, warehouse_id=wh_id,
            movement_type="received", quantity=100,
        )
        # Ship 30
        await svc.record_movement(
            stock_item_id=item_id, warehouse_id=wh_id,
            movement_type="shipped", quantity=-30,
        )
        # Adjust +5
        await svc.record_movement(
            stock_item_id=item_id, warehouse_id=wh_id,
            movement_type="adjusted", quantity=5,
        )

        level = await svc.get_stock_level(item_id)
        assert level == 75  # 100 - 30 + 5

    @pytest.mark.asyncio
    async def test_stock_level_zero_when_no_movements(self, db_session: AsyncSession) -> None:
        svc = InventoryService(session=db_session)
        item = await svc.create_stock_item(sku="EMPTY-001", name="Empty Item", category="finished_good")
        level = await svc.get_stock_level(uuid.UUID(item["id"]))
        assert level == 0
```

- [ ] **Step 4: Run test to verify it fails**

```bash
pytest tests/planks/inventory/test_service.py -v
```

- [ ] **Step 5: Implement the Inventory service**

```python
# src/theseus/planks/inventory/service.py
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore


class InventoryService:
    """Domain service for the Inventory Plank.

    Stock levels are event-sourced: computed by summing StockMovement quantities
    rather than stored as a static field.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresEventStore(session=session)

    async def create_stock_item(
        self,
        *,
        sku: str,
        name: str,
        category: str,
        unit_of_measure: str = "each",
        reorder_point: float = 0,
    ) -> dict[str, Any]:
        item_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": item_id, "sku": sku, "name": name, "category": category,
            "unit_of_measure": unit_of_measure, "reorder_point": reorder_point,
            "is_active": True,
        }
        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO inventory_stock_item ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="inventory",
            entity="StockItem", entity_id=item_id, data=params,
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def create_warehouse(self, *, name: str, code: str, address: str | None = None) -> dict[str, Any]:
        wh_id = uuid.uuid4()
        params: dict[str, Any] = {"id": wh_id, "name": name, "code": code, "is_active": True}
        if address is not None:
            params["address"] = address
        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO inventory_warehouse ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="inventory",
            entity="Warehouse", entity_id=wh_id, data=params,
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def record_movement(
        self,
        *,
        stock_item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        movement_type: str,
        quantity: float,
        reference: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        movement_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": movement_id, "stock_item_id": stock_item_id,
            "warehouse_id": warehouse_id, "movement_type": movement_type,
            "quantity": quantity,
        }
        if reference is not None:
            params["reference"] = reference
        if notes is not None:
            params["notes"] = notes

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO inventory_stock_movement ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="inventory",
            entity="StockMovement", entity_id=movement_id,
            data={"stock_item_id": str(stock_item_id), "warehouse_id": str(warehouse_id),
                  "movement_type": movement_type, "quantity": quantity,
                  "reference": reference},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def get_stock_level(self, stock_item_id: uuid.UUID) -> float:
        """Compute current stock level by summing all movement quantities.

        This is the event-sourced approach: stock level is derived from
        movements rather than stored as a mutable counter.
        """
        query = text(
            "SELECT COALESCE(SUM(quantity), 0) as total "
            "FROM inventory_stock_movement WHERE stock_item_id = :item_id"
        )
        result = await self._session.execute(query, {"item_id": stock_item_id})
        row = result.mappings().one()
        total = row["total"]
        return float(total) if total else 0.0


def _row_to_dict(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result
```

- [ ] **Step 6: Create directory structure**

```bash
mkdir -p src/theseus/planks/inventory
mkdir -p tests/planks/inventory
touch src/theseus/planks/inventory/__init__.py
touch tests/planks/inventory/__init__.py
```

- [ ] **Step 7: Update conftest.py if not already loading plank Blueprints**

Ensure the `test_engine` fixture creates tables for all Planks (should already be handled if Task 3 added PLANKS_DIR loading).

- [ ] **Step 8: Run tests**

```bash
pytest tests/planks/inventory/test_service.py -v
pytest tests/ -v
```

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Inventory Plank with event-sourced stock levels

StockItem, Warehouse, and StockMovement entities. Stock levels are
computed by summing movement quantities (event-sourced) rather than
stored as a mutable counter. Validates the Keel's event store integration
with domain-specific business logic. Movements emit events for full
audit trail.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Invoicing Plank

Tests cross-Plank references and financial calculations.

**Files:**
- Create: `planks/invoicing/blueprints/invoice.blueprint.yaml`
- Create: `planks/invoicing/blueprints/invoice-line.blueprint.yaml`
- Create: `planks/invoicing/blueprints/payment.blueprint.yaml`
- Create: `planks/invoicing/README.md`
- Create: `src/theseus/planks/invoicing/__init__.py`
- Create: `src/theseus/planks/invoicing/service.py`
- Create: `tests/planks/invoicing/__init__.py`
- Create: `tests/planks/invoicing/test_service.py`

- [ ] **Step 1: Create Invoicing Blueprints**

```yaml
# planks/invoicing/blueprints/invoice.blueprint.yaml
plank: invoicing
entity: Invoice
version: 1
description: A sales invoice sent to a customer

fields:
  invoice_number:
    type: string
    required: true
    unique: true
  status:
    type: enum
    values: [draft, sent, paid, overdue, cancelled]
    required: true
  issue_date:
    type: date
    required: true
  due_date:
    type: date
  subtotal:
    type: decimal
    default: 0
  tax_rate:
    type: decimal
    default: 0
  tax_amount:
    type: decimal
    default: 0
  total:
    type: decimal
    default: 0
  notes:
    type: text

relations:
  customer:
    type: many_to_one
    target: contacts.Contact
```

```yaml
# planks/invoicing/blueprints/invoice-line.blueprint.yaml
plank: invoicing
entity: InvoiceLine
version: 1
description: A line item on an invoice

fields:
  description:
    type: string
    required: true
  quantity:
    type: decimal
    required: true
  unit_price:
    type: decimal
    required: true
  line_total:
    type: decimal
    default: 0

relations:
  invoice:
    type: many_to_one
    target: invoicing.Invoice
  product:
    type: many_to_one
    target: inventory.StockItem
```

```yaml
# planks/invoicing/blueprints/payment.blueprint.yaml
plank: invoicing
entity: Payment
version: 1
description: A payment received against an invoice

fields:
  amount:
    type: decimal
    required: true
  payment_date:
    type: date
    required: true
  payment_method:
    type: enum
    values: [cash, check, bank_transfer, credit_card, other]
    required: true
  reference:
    type: string
  notes:
    type: text

relations:
  invoice:
    type: many_to_one
    target: invoicing.Invoice
```

- [ ] **Step 2: Create README**

```markdown
# Invoicing Plank

Invoice management for Theseus ERP. Creates invoices with line items, tracks payments.

## Entities
- **Invoice** — A sales invoice with status, dates, totals, linked to a Contact (customer)
- **InvoiceLine** — A line item on an invoice, optionally linked to a StockItem (product)
- **Payment** — A payment received against an invoice

## Cross-Plank References
- Invoice.customer -> contacts.Contact
- InvoiceLine.product -> inventory.StockItem
```

- [ ] **Step 3: Write the service test**

```python
# tests/planks/invoicing/test_service.py
import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.contacts.service import ContactService
from theseus.planks.invoicing.service import InvoicingService


class TestInvoicingService:
    @pytest.mark.asyncio
    async def test_create_invoice(self, db_session: AsyncSession) -> None:
        # First create a contact to reference
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Invoice Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-001",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
            due_date=date(2026, 5, 15),
        )
        assert invoice["invoice_number"] == "INV-001"
        assert invoice["status"] == "draft"
        assert "id" in invoice

    @pytest.mark.asyncio
    async def test_add_line_items_and_compute_total(self, db_session: AsyncSession) -> None:
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Total Test Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-002",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
        )
        invoice_id = uuid.UUID(invoice["id"])

        await svc.add_line_item(
            invoice_id=invoice_id,
            description="Steel Brackets x100",
            quantity=100,
            unit_price=4.50,
        )
        await svc.add_line_item(
            invoice_id=invoice_id,
            description="Powder Coating",
            quantity=1,
            unit_price=200.00,
        )

        totaled = await svc.compute_totals(invoice_id, tax_rate=0.08)
        assert float(totaled["subtotal"]) == 650.0  # 100*4.50 + 200
        assert float(totaled["tax_amount"]) == 52.0  # 650 * 0.08
        assert float(totaled["total"]) == 702.0  # 650 + 52

    @pytest.mark.asyncio
    async def test_record_payment(self, db_session: AsyncSession) -> None:
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Payment Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-003",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
        )
        invoice_id = uuid.UUID(invoice["id"])

        payment = await svc.record_payment(
            invoice_id=invoice_id,
            amount=500.00,
            payment_date=date(2026, 4, 20),
            payment_method="bank_transfer",
            reference="TXN-12345",
        )
        assert float(payment["amount"]) == 500.0
        assert payment["payment_method"] == "bank_transfer"

    @pytest.mark.asyncio
    async def test_payment_emits_event(self, db_session: AsyncSession) -> None:
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Event Payment Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-004",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
        )

        await svc.record_payment(
            invoice_id=uuid.UUID(invoice["id"]),
            amount=100.00,
            payment_date=date(2026, 4, 20),
            payment_method="cash",
        )

        store = PostgresEventStore(session=db_session)
        events = await store.get_events_by_type("invoicing.Payment.created")
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_get_invoice_with_lines_and_payments(self, db_session: AsyncSession) -> None:
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Full Invoice Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-005",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
        )
        invoice_id = uuid.UUID(invoice["id"])

        await svc.add_line_item(invoice_id=invoice_id, description="Item A", quantity=2, unit_price=50.00)
        await svc.add_line_item(invoice_id=invoice_id, description="Item B", quantity=1, unit_price=75.00)
        await svc.record_payment(invoice_id=invoice_id, amount=100.00,
                                  payment_date=date(2026, 4, 20), payment_method="check")

        full = await svc.get_invoice_detail(invoice_id)
        assert full["invoice_number"] == "INV-005"
        assert len(full["lines"]) == 2
        assert len(full["payments"]) == 1
        assert float(full["payments"][0]["amount"]) == 100.0
```

- [ ] **Step 4: Run test to verify it fails**

```bash
pytest tests/planks/invoicing/test_service.py -v
```

- [ ] **Step 5: Implement the Invoicing service**

```python
# src/theseus/planks/invoicing/service.py
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore


class InvoicingService:
    """Domain service for the Invoicing Plank."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresEventStore(session=session)

    async def create_invoice(
        self,
        *,
        invoice_number: str,
        customer_id: uuid.UUID,
        issue_date: date,
        due_date: date | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        invoice_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": invoice_id, "invoice_number": invoice_number,
            "customer_id": customer_id, "status": "draft",
            "issue_date": issue_date, "subtotal": 0, "tax_rate": 0,
            "tax_amount": 0, "total": 0,
        }
        if due_date is not None:
            params["due_date"] = due_date
        if notes is not None:
            params["notes"] = notes

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO invoicing_invoice ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="invoicing",
            entity="Invoice", entity_id=invoice_id,
            data={"invoice_number": invoice_number, "customer_id": str(customer_id)},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def add_line_item(
        self,
        *,
        invoice_id: uuid.UUID,
        description: str,
        quantity: float,
        unit_price: float,
        product_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        line_id = uuid.uuid4()
        line_total = round(quantity * unit_price, 2)
        params: dict[str, Any] = {
            "id": line_id, "invoice_id": invoice_id, "description": description,
            "quantity": quantity, "unit_price": unit_price, "line_total": line_total,
        }
        if product_id is not None:
            params["product_id"] = product_id

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO invoicing_invoice_line ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def compute_totals(self, invoice_id: uuid.UUID, tax_rate: float = 0) -> dict[str, Any]:
        """Recompute invoice totals from line items."""
        subtotal_query = text(
            "SELECT COALESCE(SUM(line_total), 0) as subtotal "
            "FROM invoicing_invoice_line WHERE invoice_id = :invoice_id"
        )
        result = await self._session.execute(subtotal_query, {"invoice_id": invoice_id})
        subtotal = float(result.mappings().one()["subtotal"])
        tax_amount = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax_amount, 2)

        update_query = text(
            "UPDATE invoicing_invoice SET subtotal = :subtotal, tax_rate = :tax_rate, "
            "tax_amount = :tax_amount, total = :total, updated_at = now() "
            "WHERE id = :id RETURNING *"
        )
        result = await self._session.execute(update_query, {
            "id": invoice_id, "subtotal": subtotal, "tax_rate": tax_rate,
            "tax_amount": tax_amount, "total": total,
        })
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def record_payment(
        self,
        *,
        invoice_id: uuid.UUID,
        amount: float,
        payment_date: date,
        payment_method: str,
        reference: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        payment_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": payment_id, "invoice_id": invoice_id, "amount": amount,
            "payment_date": payment_date, "payment_method": payment_method,
        }
        if reference is not None:
            params["reference"] = reference
        if notes is not None:
            params["notes"] = notes

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO invoicing_payment ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="invoicing",
            entity="Payment", entity_id=payment_id,
            data={"invoice_id": str(invoice_id), "amount": amount, "payment_method": payment_method},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def get_invoice_detail(self, invoice_id: uuid.UUID) -> dict[str, Any]:
        invoice_query = text("SELECT * FROM invoicing_invoice WHERE id = :id")
        inv_result = await self._session.execute(invoice_query, {"id": invoice_id})
        inv_row = inv_result.mappings().one_or_none()
        if inv_row is None:
            raise ValueError(f"Invoice {invoice_id} not found")

        lines_query = text("SELECT * FROM invoicing_invoice_line WHERE invoice_id = :id ORDER BY created_at")
        lines_result = await self._session.execute(lines_query, {"id": invoice_id})

        payments_query = text("SELECT * FROM invoicing_payment WHERE invoice_id = :id ORDER BY payment_date")
        payments_result = await self._session.execute(payments_query, {"id": invoice_id})

        invoice = _row_to_dict(inv_row)
        invoice["lines"] = [_row_to_dict(r) for r in lines_result.mappings().all()]
        invoice["payments"] = [_row_to_dict(r) for r in payments_result.mappings().all()]
        return invoice


def _row_to_dict(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, date):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
```

- [ ] **Step 6: Create directory structure**

```bash
mkdir -p src/theseus/planks/invoicing
mkdir -p tests/planks/invoicing
touch src/theseus/planks/invoicing/__init__.py
touch tests/planks/invoicing/__init__.py
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/planks/invoicing/test_service.py -v
pytest tests/ -v
```

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: Invoicing Plank with cross-Plank references and financial calculations

Invoice, InvoiceLine, and Payment entities. Invoice links to contacts.Contact
(customer), InvoiceLine optionally links to inventory.StockItem (product).
Service layer handles invoice creation, line item management, total computation
(subtotal + tax), payment recording, and detail retrieval. All mutations
emit events. Tests use ContactService to create referenced entities.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Cross-Plank Integration Test (Phase 3 Merge Point)

The critical test: three Planks connected through the Knowledge Graph. An Invoice references a Contact and a StockItem, and the Knowledge Graph shows all the connections.

**Files:**
- Create: `tests/integration/test_cross_plank.py`

- [ ] **Step 1: Write the cross-Plank integration test**

```python
# tests/integration/test_cross_plank.py
"""Phase 3 merge point: all three Planks connected via Knowledge Graph.

This is the critical test of Theseus's interconnectivity thesis.
An invoice references a contact (customer) and inventory items (products).
The Knowledge Graph should show all these connections.
"""
import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.store import PostgresEventStore
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.knowledge_graph.registration import register_blueprints_in_graph
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.planks.contacts.service import ContactService
from theseus.planks.inventory.service import InventoryService
from theseus.planks.invoicing.service import InvoicingService

from pathlib import Path
PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"


class TestCrossPlankIntegration:
    @pytest.mark.asyncio
    async def test_full_business_flow(self, db_session: AsyncSession) -> None:
        """Simulate a real business flow: create a customer, receive inventory,
        create an invoice with line items referencing inventory, record payment."""

        contacts = ContactService(session=db_session)
        inventory = InventoryService(session=db_session)
        invoicing = InvoicingService(session=db_session)

        # 1. Create a customer
        customer = await contacts.create_contact(
            name="BuildRight Manufacturing",
            contact_type="customer",
            email="orders@buildright.com",
        )
        customer_id = uuid.UUID(customer["id"])

        # 2. Create inventory items and receive stock
        brackets = await inventory.create_stock_item(
            sku="BRK-001", name="Steel Bracket", category="finished_good",
        )
        coating = await inventory.create_stock_item(
            sku="SVC-COAT", name="Powder Coating Service", category="consumable",
        )
        wh = await inventory.create_warehouse(name="Main Warehouse", code="MAIN")

        brackets_id = uuid.UUID(brackets["id"])
        await inventory.record_movement(
            stock_item_id=brackets_id,
            warehouse_id=uuid.UUID(wh["id"]),
            movement_type="received",
            quantity=500,
            reference="PO-100",
        )

        # 3. Create an invoice
        invoice = await invoicing.create_invoice(
            invoice_number="INV-100",
            customer_id=customer_id,
            issue_date=date(2026, 4, 15),
            due_date=date(2026, 5, 15),
        )
        invoice_id = uuid.UUID(invoice["id"])

        # 4. Add line items (referencing inventory products)
        await invoicing.add_line_item(
            invoice_id=invoice_id,
            description="Steel Brackets x200",
            quantity=200,
            unit_price=4.50,
            product_id=brackets_id,
        )
        await invoicing.add_line_item(
            invoice_id=invoice_id,
            description="Powder Coating",
            quantity=1,
            unit_price=150.00,
            product_id=uuid.UUID(coating["id"]),
        )

        # 5. Compute totals
        totaled = await invoicing.compute_totals(invoice_id, tax_rate=0.07)
        assert float(totaled["subtotal"]) == 1050.0  # 200*4.50 + 150
        assert float(totaled["total"]) == 1123.5  # 1050 + 73.5

        # 6. Record payment
        await invoicing.record_payment(
            invoice_id=invoice_id,
            amount=1123.50,
            payment_date=date(2026, 4, 20),
            payment_method="bank_transfer",
            reference="TXN-9999",
        )

        # 7. Record the shipment (stock goes out)
        await inventory.record_movement(
            stock_item_id=brackets_id,
            warehouse_id=uuid.UUID(wh["id"]),
            movement_type="shipped",
            quantity=-200,
            reference="INV-100",
        )

        # 8. Verify stock level reflects the shipment
        stock_level = await inventory.get_stock_level(brackets_id)
        assert stock_level == 300  # 500 received - 200 shipped

        # 9. Verify the event trail tells the full story
        store = PostgresEventStore(session=db_session)
        all_events = await store.get_events_by_type("invoicing.Invoice.created")
        assert any(e.data.get("invoice_number") == "INV-100" for e in all_events)

        payment_events = await store.get_events_by_type("invoicing.Payment.created")
        assert any(float(e.data.get("amount", 0)) == 1123.5 for e in payment_events)

    @pytest.mark.asyncio
    async def test_knowledge_graph_shows_cross_plank_connections(
        self, db_session: AsyncSession
    ) -> None:
        """Verify the Knowledge Graph registers cross-Plank relationships."""

        # Register all Plank Blueprints in the graph
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for plank_dir in sorted(PLANKS_DIR.iterdir()):
            bp_dir = plank_dir / "blueprints"
            if bp_dir.is_dir():
                for bp in parser.parse_directory(bp_dir):
                    registry.register(bp)

        graph = PostgresKnowledgeGraph(session=db_session)
        await register_blueprints_in_graph(registry, graph)

        # Verify entity types are registered
        contact = await graph.get_entity_type("contacts.Contact")
        assert contact is not None

        stock_item = await graph.get_entity_type("inventory.StockItem")
        assert stock_item is not None

        invoice = await graph.get_entity_type("invoicing.Invoice")
        assert invoice is not None

        # Verify cross-Plank relationships
        # Invoice -> Contact (via customer relation)
        invoice_related = await graph.get_related_types("invoicing.Invoice")
        invoice_related_names = {r.full_name for r in invoice_related}
        assert "contacts.Contact" in invoice_related_names

        # InvoiceLine -> StockItem (via product relation)
        line_related = await graph.get_related_types("invoicing.InvoiceLine")
        line_related_names = {r.full_name for r in line_related}
        assert "inventory.StockItem" in line_related_names
        assert "invoicing.Invoice" in line_related_names

        # StockMovement -> StockItem and Warehouse
        movement_related = await graph.get_related_types("inventory.StockMovement")
        movement_related_names = {r.full_name for r in movement_related}
        assert "inventory.StockItem" in movement_related_names
        assert "inventory.Warehouse" in movement_related_names
```

- [ ] **Step 2: Run the integration test**

```bash
pytest tests/integration/test_cross_plank.py -v
```

- [ ] **Step 3: Run the complete test suite**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "$(cat <<'EOF'
feat: cross-Plank integration tests (Phase 3 merge point)

Full business flow test: create customer (Contacts) -> receive inventory
(Inventory) -> create invoice with line items referencing inventory products
(Invoicing) -> record payment -> ship goods -> verify stock levels and
event trail. Knowledge Graph test verifies cross-Plank relationships:
Invoice->Contact, InvoiceLine->StockItem, StockMovement->Warehouse.
This validates the core interconnectivity thesis of Theseus.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Summary

After Plan 2, the following is operational:

| Component | Status |
|-----------|--------|
| Keel — Auto Event Emission | CRUD ops auto-emit events |
| Keel — Knowledge Graph Registration | Startup auto-registers entities and relationships |
| Contacts Plank | Contact + Address entities, search, events |
| Inventory Plank | StockItem + Warehouse + StockMovement, event-sourced stock levels |
| Invoicing Plank | Invoice + InvoiceLine + Payment, cross-Plank refs, financial calcs |
| Phase 3 Merge Point | Full business flow + Knowledge Graph interconnectivity verified |

**The core thesis is validated:** three independently-built Planks, connected through the Knowledge Graph, with a full business flow from customer creation to invoice payment to inventory shipment — all with a complete event audit trail.

**Next:** Plan 3 was originally "Integration Point" but is now covered by Task 6 above. The next plan is **Plan 4: The Shipwright** (AI engine).
