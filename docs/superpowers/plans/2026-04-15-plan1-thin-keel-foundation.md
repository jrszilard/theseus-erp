# Plan 1: Thin Keel Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal-but-principled core platform ("Thin Keel") that Phase 2 Planks (Contacts, Inventory, Invoicing) can be built on top of.

**Architecture:** Domain-organized Python backend with strict typing. Blueprint YAML files are parsed by Pydantic v2 into typed models. The Schema Engine generates SQLAlchemy 2.0 async models and Alembic migrations. The Event Store is an append-only PostgreSQL table. The Knowledge Graph uses PostgreSQL tables with an abstraction layer. All subsystems communicate through defined Protocol interfaces so any can be replaced independently.

**Tech Stack:**
- Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic
- PostgreSQL 16+ (asyncpg driver)
- LiteLLM (skeleton only — full implementation in Plan 4)
- pytest + pytest-asyncio, Ruff, mypy
- Docker Compose

**Enterprise Python patterns used:**
- `typing.Protocol` for all subsystem interfaces (structural typing, no inheritance coupling)
- Pydantic `BaseModel` for all data transfer objects and validation
- Repository pattern for data access, Service layer for business logic
- FastAPI `Depends` for dependency injection
- Strict type hints on every function signature
- Domain-organized project structure (not layer-organized)

---

## File Structure

```
theseus/
├── pyproject.toml                          # Project metadata, dependencies, tool config
├── Dockerfile                              # Multi-stage Python build
├── docker-compose.yml                      # App + PostgreSQL
├── .env.example                            # Environment variable template
├── .gitignore
├── alembic.ini                             # Alembic configuration
├── alembic/
│   ├── env.py                              # Async Alembic environment
│   └── versions/                           # Auto-generated migrations
├── src/
│   └── theseus/
│       ├── __init__.py
│       ├── main.py                         # FastAPI app factory
│       ├── config.py                       # Pydantic Settings configuration
│       ├── database.py                     # Async SQLAlchemy engine + session factory
│       ├── keel/
│       │   ├── __init__.py
│       │   ├── blueprint_engine/
│       │   │   ├── __init__.py
│       │   │   ├── models.py               # Pydantic models for Blueprint YAML schema
│       │   │   ├── parser.py               # YAML loading + validation
│       │   │   ├── registry.py             # In-memory registry of loaded Blueprints
│       │   │   └── protocols.py            # BlueprintParser protocol
│       │   ├── schema_engine/
│       │   │   ├── __init__.py
│       │   │   ├── generator.py            # Blueprint → SQLAlchemy model generation
│       │   │   ├── migrator.py             # Dynamic Alembic migration management
│       │   │   └── protocols.py            # SchemaGenerator, Migrator protocols
│       │   ├── event_store/
│       │   │   ├── __init__.py
│       │   │   ├── models.py               # SQLAlchemy Event model + Pydantic schemas
│       │   │   ├── store.py                # Append, query, replay operations
│       │   │   ├── subscriptions.py        # LISTEN/NOTIFY pub/sub
│       │   │   └── protocols.py            # EventStore protocol
│       │   ├── knowledge_graph/
│       │   │   ├── __init__.py
│       │   │   ├── models.py               # GraphNode, GraphEdge SQLAlchemy models
│       │   │   ├── graph.py                # Registration, traversal, query
│       │   │   └── protocols.py            # KnowledgeGraph protocol
│       │   ├── auth/
│       │   │   ├── __init__.py
│       │   │   ├── models.py               # User, Role SQLAlchemy + Pydantic models
│       │   │   ├── service.py              # Auth logic, JWT, permission checks
│       │   │   ├── dependencies.py         # FastAPI Depends for auth
│       │   │   └── protocols.py            # AuthService protocol
│       │   └── llm_gateway/
│       │       ├── __init__.py
│       │       ├── gateway.py              # LiteLLM wrapper, provider routing
│       │       └── protocols.py            # LLMGateway protocol
│       └── api/
│           ├── __init__.py
│           ├── routes/
│           │   ├── __init__.py
│           │   ├── health.py               # Health check endpoints
│           │   ├── blueprints.py           # Blueprint management endpoints
│           │   └── entities.py             # Dynamic CRUD endpoints from Blueprints
│           ├── middleware.py               # Request logging, error handling
│           └── dependencies.py             # Shared FastAPI dependencies
├── tests/
│   ├── conftest.py                         # Shared fixtures (async DB, test client)
│   ├── keel/
│   │   ├── blueprint_engine/
│   │   │   ├── test_models.py
│   │   │   └── test_parser.py
│   │   ├── schema_engine/
│   │   │   ├── test_generator.py
│   │   │   └── test_migrator.py
│   │   ├── event_store/
│   │   │   ├── test_store.py
│   │   │   └── test_subscriptions.py
│   │   ├── knowledge_graph/
│   │   │   └── test_graph.py
│   │   └── auth/
│   │       └── test_service.py
│   ├── api/
│   │   ├── test_health.py
│   │   └── test_entities.py
│   └── integration/
│       └── test_full_pipeline.py
└── blueprints/                             # Example Blueprints for testing
    └── _test/
        ├── simple-entity.blueprint.yaml
        └── related-entities.blueprint.yaml
```

---

## Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `src/theseus/__init__.py`
- Create: `src/theseus/config.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /home/justin/lakeshore-studio/ai-projects/opensource-ai-erp
git init
```

- [ ] **Step 2: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
*.egg

# Virtual environment
.venv/
venv/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local

# Testing
.coverage
htmlcov/
.pytest_cache/

# mypy
.mypy_cache/

# Ruff
.ruff_cache/

# Docker
docker-compose.override.yml

# Alembic
alembic/versions/__pycache__/

# Superpowers brainstorm artifacts
.superpowers/
```

- [ ] **Step 3: Create pyproject.toml**

```toml
[project]
name = "theseus-erp"
version = "0.1.0"
description = "An open-source, AI-first ERP for small manufacturing and trade businesses"
license = "AGPL-3.0-or-later"
requires-python = ">=3.12"
authors = [
    { name = "Justin Szilard", email = "jrszilard@gmail.com" },
]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pyyaml>=6.0.2",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "litellm>=1.55.0",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "sqlalchemy[mypy]>=2.0.36",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/theseus"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = ["ignore::DeprecationWarning"]

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "RUF",  # ruff-specific
]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]

[tool.ruff.lint.isort]
known-first-party = ["theseus"]
```

- [ ] **Step 4: Create .env.example**

```env
# Database
DATABASE_URL=postgresql+asyncpg://theseus:theseus@localhost:5432/theseus

# Auth
SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32
ACCESS_TOKEN_EXPIRE_MINUTES=480

# LLM (optional — system works without AI configured)
LLM_PROVIDER=
LLM_MODEL=
LLM_API_KEY=

# App
LOG_LEVEL=INFO
DEBUG=false
```

- [ ] **Step 5: Create config.py with Pydantic Settings**

```python
# src/theseus/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://theseus:theseus@localhost:5432/theseus"

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 480

    # LLM (all optional — system works without AI)
    llm_provider: str = ""
    llm_model: str = ""
    llm_api_key: str = ""

    # App
    log_level: str = "INFO"
    debug: bool = False

    @property
    def database_url_sync(self) -> str:
        """Sync URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "")


settings = Settings()
```

- [ ] **Step 6: Create __init__.py**

```python
# src/theseus/__init__.py
"""Theseus ERP — An open-source, AI-first ERP for small manufacturing and trade businesses."""
```

- [ ] **Step 7: Create Dockerfile**

```dockerfile
# Dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

FROM base AS builder

RUN pip install --upgrade pip
COPY pyproject.toml .
RUN pip install . --no-deps --target=/install

FROM base AS runtime

COPY --from=builder /install /usr/local/lib/python3.12/site-packages
COPY src/ /app/src/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/

EXPOSE 8000

CMD ["uvicorn", "theseus.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 8: Create docker-compose.yml**

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: theseus
      POSTGRES_PASSWORD: theseus
      POSTGRES_DB: theseus
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U theseus"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://theseus:theseus@db:5432/theseus
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./blueprints:/app/blueprints

volumes:
  pgdata:
```

- [ ] **Step 9: Create directory structure**

```bash
mkdir -p src/theseus/keel/{blueprint_engine,schema_engine,event_store,knowledge_graph,auth,llm_gateway}
mkdir -p src/theseus/api/routes
mkdir -p tests/keel/{blueprint_engine,schema_engine,event_store,knowledge_graph,auth}
mkdir -p tests/{api,integration}
mkdir -p alembic/versions
mkdir -p blueprints/_test
touch src/theseus/keel/__init__.py
touch src/theseus/keel/blueprint_engine/__init__.py
touch src/theseus/keel/schema_engine/__init__.py
touch src/theseus/keel/event_store/__init__.py
touch src/theseus/keel/knowledge_graph/__init__.py
touch src/theseus/keel/auth/__init__.py
touch src/theseus/keel/llm_gateway/__init__.py
touch src/theseus/api/__init__.py
touch src/theseus/api/routes/__init__.py
```

- [ ] **Step 10: Install dependencies and verify**

```bash
cd /home/justin/lakeshore-studio/ai-projects/opensource-ai-erp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -c "import theseus; print('Theseus package OK')"
```

- [ ] **Step 11: Commit**

```bash
git add .
git commit -m "feat: project bootstrap with FastAPI, SQLAlchemy, Docker Compose

Initialize Theseus ERP project structure with enterprise Python patterns.
Includes pyproject.toml, Docker setup, Pydantic config, and full directory
structure for the Keel subsystems."
```

---

## Task 2: Database Foundation

**Files:**
- Create: `src/theseus/database.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `tests/conftest.py`
- Create: `tests/keel/__init__.py` (and nested __init__.py files)

- [ ] **Step 1: Create database.py with async engine and session**

```python
# src/theseus/database.py
from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from theseus.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = metadata


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 2: Create alembic.ini**

```ini
# alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = src

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Create async Alembic env.py**

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from theseus.config import settings
from theseus.database import Base

# Import all models so Alembic sees them for autogenerate.
# Add new model imports here as subsystems are built.
import theseus.keel.event_store.models  # noqa: F401
import theseus.keel.knowledge_graph.models  # noqa: F401
import theseus.keel.auth.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Create test conftest.py with async DB fixtures**

```python
# tests/conftest.py
import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from theseus.database import Base, get_session
from theseus.main import create_app

TEST_DATABASE_URL = "postgresql+asyncpg://theseus:theseus@localhost:5432/theseus_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

- [ ] **Step 5: Create init files for test packages**

```bash
touch tests/__init__.py
touch tests/keel/__init__.py
touch tests/keel/blueprint_engine/__init__.py
touch tests/keel/schema_engine/__init__.py
touch tests/keel/event_store/__init__.py
touch tests/keel/knowledge_graph/__init__.py
touch tests/keel/auth/__init__.py
touch tests/api/__init__.py
touch tests/integration/__init__.py
```

- [ ] **Step 6: Create minimal FastAPI app factory**

```python
# src/theseus/main.py
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="Theseus ERP",
        description="An open-source, AI-first ERP for small manufacturing and trade businesses.",
        version="0.1.0",
    )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "theseus"}

    return app


app = create_app()
```

- [ ] **Step 7: Write test for health endpoint**

```python
# tests/api/test_health.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "theseus"
```

- [ ] **Step 8: Start PostgreSQL and run test**

```bash
docker compose up db -d
# Create test database
docker compose exec db psql -U theseus -c "CREATE DATABASE theseus_test;"
# Run test
pytest tests/api/test_health.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "feat: database foundation with async SQLAlchemy, Alembic, test fixtures

Async PostgreSQL via asyncpg, SQLAlchemy 2.0 session management,
Alembic async migrations, pytest fixtures with per-test rollback,
FastAPI app factory with health endpoint."
```

---

## Task 3: Blueprint Meta-Schema (Pydantic Models)

**Files:**
- Create: `src/theseus/keel/blueprint_engine/models.py`
- Create: `tests/keel/blueprint_engine/test_models.py`

- [ ] **Step 1: Write the failing test for Blueprint field models**

```python
# tests/keel/blueprint_engine/test_models.py
import pytest
from pydantic import ValidationError

from theseus.keel.blueprint_engine.models import (
    BlueprintField,
    BlueprintRelation,
    BlueprintBehavior,
    Blueprint,
    FieldType,
    RelationType,
)


class TestBlueprintField:
    def test_valid_string_field(self) -> None:
        field = BlueprintField(type=FieldType.STRING, required=True)
        assert field.type == FieldType.STRING
        assert field.required is True
        assert field.unique is False

    def test_valid_enum_field_with_values(self) -> None:
        field = BlueprintField(
            type=FieldType.ENUM,
            values=["draft", "sent", "paid"],
        )
        assert field.values == ["draft", "sent", "paid"]

    def test_enum_field_requires_values(self) -> None:
        with pytest.raises(ValidationError, match="values"):
            BlueprintField(type=FieldType.ENUM)

    def test_decimal_field_with_default(self) -> None:
        field = BlueprintField(type=FieldType.DECIMAL, default=0)
        assert field.default == 0

    def test_computed_field(self) -> None:
        field = BlueprintField(type=FieldType.DECIMAL, computed=True)
        assert field.computed is True


class TestBlueprintRelation:
    def test_valid_many_to_one(self) -> None:
        rel = BlueprintRelation(
            type=RelationType.MANY_TO_ONE,
            target="contacts.Contact",
        )
        assert rel.type == RelationType.MANY_TO_ONE
        assert rel.target == "contacts.Contact"
        assert rel.target_plank == "contacts"
        assert rel.target_entity == "Contact"

    def test_valid_many_to_many_with_filter(self) -> None:
        rel = BlueprintRelation(
            type=RelationType.MANY_TO_MANY,
            target="contacts.Contact",
            filter={"type": "supplier"},
        )
        assert rel.filter == {"type": "supplier"}

    def test_invalid_target_format(self) -> None:
        with pytest.raises(ValidationError, match="target"):
            BlueprintRelation(
                type=RelationType.MANY_TO_ONE,
                target="no_dot_separator",
            )


class TestBlueprintBehavior:
    def test_valid_behavior(self) -> None:
        behavior = BlueprintBehavior(
            trigger="current_stock < reorder_point",
            action="emit_event",
            event="RestockNeeded",
        )
        assert behavior.trigger == "current_stock < reorder_point"
        assert behavior.event == "RestockNeeded"


class TestBlueprint:
    def test_valid_minimal_blueprint(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="SimpleItem",
            version=1,
            description="A simple test entity",
            fields={
                "name": BlueprintField(type=FieldType.STRING, required=True),
            },
        )
        assert bp.plank == "test"
        assert bp.entity == "SimpleItem"
        assert bp.table_name == "test_simple_item"

    def test_valid_full_blueprint(self) -> None:
        bp = Blueprint(
            plank="inventory",
            entity="StockItem",
            version=1,
            description="A trackable item in inventory",
            fields={
                "sku": BlueprintField(type=FieldType.STRING, required=True, unique=True),
                "name": BlueprintField(type=FieldType.STRING, required=True),
                "category": BlueprintField(
                    type=FieldType.ENUM,
                    values=["raw_material", "component", "finished_good"],
                ),
                "reorder_point": BlueprintField(type=FieldType.DECIMAL, default=0),
            },
            relations={
                "suppliers": BlueprintRelation(
                    type=RelationType.MANY_TO_MANY,
                    target="contacts.Contact",
                    filter={"type": "supplier"},
                ),
            },
            behaviors={
                "on_stock_below_reorder": BlueprintBehavior(
                    trigger="current_stock < reorder_point",
                    action="emit_event",
                    event="RestockNeeded",
                ),
            },
        )
        assert bp.table_name == "inventory_stock_item"
        assert len(bp.fields) == 4
        assert len(bp.relations) == 1
        assert len(bp.behaviors) == 1

    def test_blueprint_requires_at_least_one_field(self) -> None:
        with pytest.raises(ValidationError, match="fields"):
            Blueprint(
                plank="test",
                entity="Empty",
                version=1,
                description="No fields",
                fields={},
            )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/keel/blueprint_engine/test_models.py -v
```

Expected: FAIL — models not yet defined

- [ ] **Step 3: Implement Blueprint models**

```python
# src/theseus/keel/blueprint_engine/models.py
from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, field_validator, model_validator


class FieldType(StrEnum):
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"
    JSON = "json"


class RelationType(StrEnum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class UIHints(BaseModel):
    """Optional rendering hints for the Hull design system."""

    component: str | None = None
    colors: dict[str, str] | None = None
    max_height: str | None = None
    highlight_when: str | None = None


class BlueprintField(BaseModel):
    """A field definition within a Blueprint entity."""

    type: FieldType
    required: bool = False
    unique: bool = False
    default: Any = None
    computed: bool = False
    values: list[str] | None = None
    ui: UIHints | None = None

    @model_validator(mode="after")
    def enum_requires_values(self) -> BlueprintField:
        if self.type == FieldType.ENUM and not self.values:
            msg = "Enum fields require 'values' to be specified"
            raise ValueError(msg)
        return self


class BlueprintRelation(BaseModel):
    """A relationship to another entity, possibly in another Plank."""

    type: RelationType
    target: str
    filter: dict[str, Any] | None = None

    @field_validator("target")
    @classmethod
    def validate_target_format(cls, v: str) -> str:
        if "." not in v:
            msg = f"target must be in 'plank.Entity' format, got '{v}'"
            raise ValueError(msg)
        return v

    @property
    def target_plank(self) -> str:
        return self.target.split(".")[0]

    @property
    def target_entity(self) -> str:
        return self.target.split(".")[1]


class BlueprintBehavior(BaseModel):
    """A reactive behavior triggered by entity state changes."""

    trigger: str
    action: str
    event: str | None = None


class Blueprint(BaseModel):
    """The complete definition of a Theseus entity — the core unit of the Plank system."""

    plank: str
    entity: str
    version: int
    description: str
    fields: dict[str, BlueprintField]
    relations: dict[str, BlueprintRelation] | None = None
    behaviors: dict[str, BlueprintBehavior] | None = None

    @field_validator("fields")
    @classmethod
    def require_at_least_one_field(cls, v: dict[str, BlueprintField]) -> dict[str, BlueprintField]:
        if not v:
            msg = "Blueprint must define at least one field"
            raise ValueError(msg)
        return v

    @property
    def table_name(self) -> str:
        """Generate the PostgreSQL table name from plank + entity.

        Example: plank='inventory', entity='StockItem' -> 'inventory_stock_item'
        """
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", self.entity).lower()
        return f"{self.plank}_{snake}"

    @property
    def full_name(self) -> str:
        """Fully qualified entity name: 'plank.Entity'."""
        return f"{self.plank}.{self.entity}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/keel/blueprint_engine/test_models.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/theseus/keel/blueprint_engine/models.py tests/keel/blueprint_engine/test_models.py
git commit -m "feat: Blueprint meta-schema with Pydantic v2 models

Define FieldType, RelationType, BlueprintField, BlueprintRelation,
BlueprintBehavior, and Blueprint as strict Pydantic models. Includes
validation: enum requires values, target format validation, at least
one field required. Generates table names from plank+entity."
```

---

## Task 4: Blueprint Parser

**Files:**
- Create: `src/theseus/keel/blueprint_engine/parser.py`
- Create: `src/theseus/keel/blueprint_engine/registry.py`
- Create: `src/theseus/keel/blueprint_engine/protocols.py`
- Create: `blueprints/_test/simple-entity.blueprint.yaml`
- Create: `blueprints/_test/related-entities.blueprint.yaml`
- Create: `tests/keel/blueprint_engine/test_parser.py`

- [ ] **Step 1: Create test Blueprint YAML files**

```yaml
# blueprints/_test/simple-entity.blueprint.yaml
plank: test
entity: Widget
version: 1
description: A simple test widget

fields:
  name:
    type: string
    required: true
  color:
    type: enum
    values: [red, green, blue]
  weight:
    type: decimal
    default: 0
  is_active:
    type: boolean
    default: true
```

```yaml
# blueprints/_test/related-entities.blueprint.yaml
plank: test
entity: WidgetOrder
version: 1
description: An order for widgets

fields:
  order_number:
    type: string
    required: true
    unique: true
  quantity:
    type: integer
    required: true
  notes:
    type: text

relations:
  widget:
    type: many_to_one
    target: test.Widget
  customer:
    type: many_to_one
    target: contacts.Contact

behaviors:
  on_quantity_zero:
    trigger: "quantity == 0"
    action: emit_event
    event: OrderCancelled
```

- [ ] **Step 2: Write the failing test for the parser**

```python
# tests/keel/blueprint_engine/test_parser.py
from pathlib import Path

import pytest
from pydantic import ValidationError

from theseus.keel.blueprint_engine.models import Blueprint, FieldType, RelationType
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "blueprints" / "_test"


class TestBlueprintFileParser:
    def test_parse_simple_entity(self) -> None:
        parser = BlueprintFileParser()
        bp = parser.parse_file(FIXTURES_DIR / "simple-entity.blueprint.yaml")
        assert bp.plank == "test"
        assert bp.entity == "Widget"
        assert bp.version == 1
        assert "name" in bp.fields
        assert bp.fields["name"].type == FieldType.STRING
        assert bp.fields["name"].required is True
        assert bp.fields["color"].type == FieldType.ENUM
        assert bp.fields["color"].values == ["red", "green", "blue"]

    def test_parse_related_entities(self) -> None:
        parser = BlueprintFileParser()
        bp = parser.parse_file(FIXTURES_DIR / "related-entities.blueprint.yaml")
        assert bp.entity == "WidgetOrder"
        assert bp.relations is not None
        assert "widget" in bp.relations
        assert bp.relations["widget"].type == RelationType.MANY_TO_ONE
        assert bp.relations["widget"].target == "test.Widget"
        assert bp.behaviors is not None
        assert "on_quantity_zero" in bp.behaviors

    def test_parse_nonexistent_file_raises(self) -> None:
        parser = BlueprintFileParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file(Path("/nonexistent/file.yaml"))

    def test_parse_invalid_yaml_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.blueprint.yaml"
        bad_file.write_text("plank: test\nentity: Bad\nversion: 1\n")
        parser = BlueprintFileParser()
        with pytest.raises(ValidationError):
            parser.parse_file(bad_file)

    def test_parse_directory(self) -> None:
        parser = BlueprintFileParser()
        blueprints = parser.parse_directory(FIXTURES_DIR)
        assert len(blueprints) == 2
        names = {bp.entity for bp in blueprints}
        assert names == {"Widget", "WidgetOrder"}


class TestBlueprintRegistry:
    def test_register_and_get(self) -> None:
        parser = BlueprintFileParser()
        bp = parser.parse_file(FIXTURES_DIR / "simple-entity.blueprint.yaml")
        registry = BlueprintRegistry()
        registry.register(bp)
        assert registry.get("test.Widget") is bp
        assert registry.get("test.Widget") is not None

    def test_get_nonexistent_returns_none(self) -> None:
        registry = BlueprintRegistry()
        assert registry.get("nonexistent.Entity") is None

    def test_list_by_plank(self) -> None:
        parser = BlueprintFileParser()
        blueprints = parser.parse_directory(FIXTURES_DIR)
        registry = BlueprintRegistry()
        for bp in blueprints:
            registry.register(bp)
        test_planks = registry.list_by_plank("test")
        assert len(test_planks) == 2

    def test_all(self) -> None:
        parser = BlueprintFileParser()
        blueprints = parser.parse_directory(FIXTURES_DIR)
        registry = BlueprintRegistry()
        for bp in blueprints:
            registry.register(bp)
        assert len(registry.all()) == 2

    def test_duplicate_registration_raises(self) -> None:
        parser = BlueprintFileParser()
        bp = parser.parse_file(FIXTURES_DIR / "simple-entity.blueprint.yaml")
        registry = BlueprintRegistry()
        registry.register(bp)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(bp)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/keel/blueprint_engine/test_parser.py -v
```

Expected: FAIL — parser and registry not yet defined

- [ ] **Step 4: Implement the protocol**

```python
# src/theseus/keel/blueprint_engine/protocols.py
from pathlib import Path
from typing import Protocol

from theseus.keel.blueprint_engine.models import Blueprint


class BlueprintParser(Protocol):
    """Protocol for parsing Blueprint files into validated models."""

    def parse_file(self, path: Path) -> Blueprint: ...
    def parse_directory(self, path: Path) -> list[Blueprint]: ...
```

- [ ] **Step 5: Implement the parser**

```python
# src/theseus/keel/blueprint_engine/parser.py
from pathlib import Path

import yaml

from theseus.keel.blueprint_engine.models import Blueprint


class BlueprintFileParser:
    """Parses Blueprint YAML files into validated Pydantic models."""

    SUFFIX = ".blueprint.yaml"

    def parse_file(self, path: Path) -> Blueprint:
        if not path.exists():
            msg = f"Blueprint file not found: {path}"
            raise FileNotFoundError(msg)

        with open(path) as f:
            raw = yaml.safe_load(f)

        return Blueprint.model_validate(raw)

    def parse_directory(self, path: Path) -> list[Blueprint]:
        if not path.is_dir():
            msg = f"Blueprint directory not found: {path}"
            raise FileNotFoundError(msg)

        blueprints: list[Blueprint] = []
        for file in sorted(path.glob(f"**/*{self.SUFFIX}")):
            blueprints.append(self.parse_file(file))
        return blueprints
```

- [ ] **Step 6: Implement the registry**

```python
# src/theseus/keel/blueprint_engine/registry.py
from theseus.keel.blueprint_engine.models import Blueprint


class BlueprintRegistry:
    """In-memory registry of loaded Blueprints, keyed by full_name (plank.Entity)."""

    def __init__(self) -> None:
        self._blueprints: dict[str, Blueprint] = {}

    def register(self, blueprint: Blueprint) -> None:
        if blueprint.full_name in self._blueprints:
            msg = f"Blueprint '{blueprint.full_name}' is already registered"
            raise ValueError(msg)
        self._blueprints[blueprint.full_name] = blueprint

    def get(self, full_name: str) -> Blueprint | None:
        return self._blueprints.get(full_name)

    def list_by_plank(self, plank: str) -> list[Blueprint]:
        return [bp for bp in self._blueprints.values() if bp.plank == plank]

    def all(self) -> list[Blueprint]:
        return list(self._blueprints.values())
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/keel/blueprint_engine/test_parser.py -v
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "feat: Blueprint parser and registry

Parse YAML Blueprint files into validated Pydantic models. Registry
provides in-memory lookup by full_name, plank filtering, and duplicate
detection. Includes test fixture Blueprints for Widget and WidgetOrder."
```

---

## Task 5: Schema Engine — Model Generation

**Files:**
- Create: `src/theseus/keel/schema_engine/generator.py`
- Create: `src/theseus/keel/schema_engine/protocols.py`
- Create: `tests/keel/schema_engine/test_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/keel/schema_engine/test_generator.py
from pathlib import Path

import pytest
from sqlalchemy import Column, inspect

from theseus.keel.blueprint_engine.models import (
    Blueprint,
    BlueprintField,
    BlueprintRelation,
    FieldType,
    RelationType,
)
from theseus.keel.schema_engine.generator import SchemaGenerator

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "blueprints" / "_test"


class TestSchemaGenerator:
    def test_generate_simple_table(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="Widget",
            version=1,
            description="Test widget",
            fields={
                "name": BlueprintField(type=FieldType.STRING, required=True),
                "weight": BlueprintField(type=FieldType.DECIMAL, default=0),
                "is_active": BlueprintField(type=FieldType.BOOLEAN, default=True),
            },
        )
        generator = SchemaGenerator()
        table = generator.generate_table(bp)

        assert table.name == "test_widget"
        column_names = {c.name for c in table.columns}
        assert "id" in column_names
        assert "name" in column_names
        assert "weight" in column_names
        assert "is_active" in column_names
        assert "created_at" in column_names
        assert "updated_at" in column_names

    def test_string_field_nullable(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="Thing",
            version=1,
            description="Test",
            fields={
                "required_name": BlueprintField(type=FieldType.STRING, required=True),
                "optional_note": BlueprintField(type=FieldType.STRING),
            },
        )
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        required_col = table.c["required_name"]
        optional_col = table.c["optional_note"]
        assert required_col.nullable is False
        assert optional_col.nullable is True

    def test_unique_field(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="UniqueTest",
            version=1,
            description="Test",
            fields={
                "code": BlueprintField(type=FieldType.STRING, required=True, unique=True),
            },
        )
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        code_col = table.c["code"]
        assert code_col.unique is True

    def test_enum_field_generates_check_constraint(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="EnumTest",
            version=1,
            description="Test",
            fields={
                "status": BlueprintField(
                    type=FieldType.ENUM, values=["draft", "sent", "paid"]
                ),
            },
        )
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        status_col = table.c["status"]
        assert status_col.type.enums == ("draft", "sent", "paid")

    def test_field_type_mapping(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="AllTypes",
            version=1,
            description="Test all types",
            fields={
                "a_string": BlueprintField(type=FieldType.STRING),
                "a_text": BlueprintField(type=FieldType.TEXT),
                "an_int": BlueprintField(type=FieldType.INTEGER),
                "a_decimal": BlueprintField(type=FieldType.DECIMAL),
                "a_bool": BlueprintField(type=FieldType.BOOLEAN),
                "a_date": BlueprintField(type=FieldType.DATE),
                "a_datetime": BlueprintField(type=FieldType.DATETIME),
                "a_json": BlueprintField(type=FieldType.JSON),
            },
        )
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        assert len([c for c in table.columns if c.name not in ("id", "created_at", "updated_at")]) == 8

    def test_computed_fields_are_excluded_from_table(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="ComputedTest",
            version=1,
            description="Test",
            fields={
                "name": BlueprintField(type=FieldType.STRING, required=True),
                "derived_value": BlueprintField(type=FieldType.DECIMAL, computed=True),
            },
        )
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        column_names = {c.name for c in table.columns}
        assert "name" in column_names
        assert "derived_value" not in column_names

    def test_many_to_one_generates_foreign_key_column(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="Order",
            version=1,
            description="Test",
            fields={
                "total": BlueprintField(type=FieldType.DECIMAL),
            },
            relations={
                "customer": BlueprintRelation(
                    type=RelationType.MANY_TO_ONE,
                    target="contacts.Contact",
                ),
            },
        )
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        column_names = {c.name for c in table.columns}
        assert "customer_id" in column_names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/keel/schema_engine/test_generator.py -v
```

Expected: FAIL — generator not yet defined

- [ ] **Step 3: Implement the protocol**

```python
# src/theseus/keel/schema_engine/protocols.py
from typing import Protocol

from sqlalchemy import Table

from theseus.keel.blueprint_engine.models import Blueprint


class SchemaGeneratorProtocol(Protocol):
    """Protocol for generating SQLAlchemy tables from Blueprints."""

    def generate_table(self, blueprint: Blueprint) -> Table: ...
```

- [ ] **Step 4: Implement the schema generator**

```python
# src/theseus/keel/schema_engine/generator.py
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID

from theseus.keel.blueprint_engine.models import (
    Blueprint,
    BlueprintField,
    BlueprintRelation,
    FieldType,
    RelationType,
)

FIELD_TYPE_MAP = {
    FieldType.STRING: lambda _f: String(255),
    FieldType.TEXT: lambda _f: Text(),
    FieldType.INTEGER: lambda _f: Integer(),
    FieldType.DECIMAL: lambda _f: Numeric(precision=19, scale=4),
    FieldType.BOOLEAN: lambda _f: Boolean(),
    FieldType.DATE: lambda _f: Date(),
    FieldType.DATETIME: lambda _f: DateTime(timezone=True),
    FieldType.ENUM: lambda f: Enum(*f.values, name=f"enum_{f.values[0]}_{len(f.values)}"),
    FieldType.JSON: lambda _f: JSON(),
}


class SchemaGenerator:
    """Generates SQLAlchemy Table objects from Blueprint definitions."""

    def __init__(self, metadata: MetaData | None = None) -> None:
        self._metadata = metadata or MetaData()

    def generate_table(self, blueprint: Blueprint) -> Table:
        columns = self._build_system_columns()
        columns.extend(self._build_field_columns(blueprint))
        columns.extend(self._build_relation_columns(blueprint))
        return Table(blueprint.table_name, self._metadata, *columns)

    def _build_system_columns(self) -> list[Column]:
        return [
            Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column(
                "created_at",
                DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
            ),
            Column(
                "updated_at",
                DateTime(timezone=True),
                server_default=func.now(),
                onupdate=func.now(),
                nullable=False,
            ),
        ]

    def _build_field_columns(self, blueprint: Blueprint) -> list[Column]:
        columns: list[Column] = []
        for name, field in blueprint.fields.items():
            if field.computed:
                continue
            col_type = FIELD_TYPE_MAP[field.type](field)
            columns.append(
                Column(
                    name,
                    col_type,
                    nullable=not field.required,
                    unique=field.unique or None,
                    default=field.default,
                )
            )
        return columns

    def _build_relation_columns(self, blueprint: Blueprint) -> list[Column]:
        columns: list[Column] = []
        if not blueprint.relations:
            return columns
        for name, relation in blueprint.relations.items():
            if relation.type in (RelationType.MANY_TO_ONE, RelationType.ONE_TO_ONE):
                target_table = _relation_target_table_name(relation)
                columns.append(
                    Column(
                        f"{name}_id",
                        UUID(as_uuid=True),
                        ForeignKey(f"{target_table}.id"),
                        nullable=True,
                    )
                )
        return columns


def _relation_target_table_name(relation: BlueprintRelation) -> str:
    """Convert 'contacts.Contact' -> 'contacts_contact'."""
    import re

    entity = relation.target_entity
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", entity).lower()
    return f"{relation.target_plank}_{snake}"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/keel/schema_engine/test_generator.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: Schema Engine generates SQLAlchemy tables from Blueprints

Maps Blueprint field types to SQLAlchemy column types. Handles
required/nullable, unique constraints, enum types, computed field
exclusion, and many-to-one foreign keys. System columns (id,
created_at, updated_at) added automatically with UUID primary keys."
```

---

## Task 6: Event Store

**Files:**
- Create: `src/theseus/keel/event_store/models.py`
- Create: `src/theseus/keel/event_store/store.py`
- Create: `src/theseus/keel/event_store/protocols.py`
- Create: `tests/keel/event_store/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/keel/event_store/test_store.py
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.models import EventRecord
from theseus.keel.event_store.store import PostgresEventStore


@pytest.fixture
def event_store(db_session: AsyncSession) -> PostgresEventStore:
    return PostgresEventStore(session=db_session)


class TestPostgresEventStore:
    @pytest.mark.asyncio
    async def test_append_event(self, event_store: PostgresEventStore) -> None:
        event = await event_store.append(
            event_type="test.ItemCreated",
            entity_type="Widget",
            entity_id=uuid.uuid4(),
            actor_type="user",
            actor_id=uuid.uuid4(),
            data={"name": "Test Widget", "color": "red"},
        )
        assert event.event_id is not None
        assert event.event_type == "test.ItemCreated"
        assert event.data == {"name": "Test Widget", "color": "red"}
        assert event.timestamp is not None

    @pytest.mark.asyncio
    async def test_get_events_for_entity(self, event_store: PostgresEventStore) -> None:
        entity_id = uuid.uuid4()
        await event_store.append(
            event_type="test.Created",
            entity_type="Widget",
            entity_id=entity_id,
            actor_type="user",
            actor_id=uuid.uuid4(),
            data={"name": "Widget A"},
        )
        await event_store.append(
            event_type="test.Updated",
            entity_type="Widget",
            entity_id=entity_id,
            actor_type="user",
            actor_id=uuid.uuid4(),
            data={"name": "Widget A (updated)"},
        )
        events = await event_store.get_events_for_entity("Widget", entity_id)
        assert len(events) == 2
        assert events[0].event_type == "test.Created"
        assert events[1].event_type == "test.Updated"

    @pytest.mark.asyncio
    async def test_get_events_by_type(self, event_store: PostgresEventStore) -> None:
        actor_id = uuid.uuid4()
        await event_store.append(
            event_type="inventory.StockAdjusted",
            entity_type="StockItem",
            entity_id=uuid.uuid4(),
            actor_type="user",
            actor_id=actor_id,
            data={"quantity_change": -5},
        )
        await event_store.append(
            event_type="inventory.StockAdjusted",
            entity_type="StockItem",
            entity_id=uuid.uuid4(),
            actor_type="user",
            actor_id=actor_id,
            data={"quantity_change": 10},
        )
        await event_store.append(
            event_type="contacts.ContactCreated",
            entity_type="Contact",
            entity_id=uuid.uuid4(),
            actor_type="user",
            actor_id=actor_id,
            data={"name": "Acme"},
        )
        events = await event_store.get_events_by_type("inventory.StockAdjusted")
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_events_are_ordered_by_timestamp(
        self, event_store: PostgresEventStore
    ) -> None:
        entity_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        for i in range(5):
            await event_store.append(
                event_type=f"test.Event{i}",
                entity_type="Widget",
                entity_id=entity_id,
                actor_type="user",
                actor_id=actor_id,
                data={"sequence": i},
            )
        events = await event_store.get_events_for_entity("Widget", entity_id)
        sequences = [e.data["sequence"] for e in events]
        assert sequences == [0, 1, 2, 3, 4]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/keel/event_store/test_store.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement event models**

```python
# src/theseus/keel/event_store/models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from theseus.database import Base


class Event(Base):
    """SQLAlchemy model for the append-only event store."""

    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    __table_args__ = (
        Index("ix_events_entity_lookup", "entity_type", "entity_id", "timestamp"),
    )


class EventRecord(BaseModel):
    """Pydantic model for event data transfer."""

    model_config = {"from_attributes": True}

    event_id: uuid.UUID
    event_type: str
    entity_type: str
    entity_id: uuid.UUID
    timestamp: datetime
    actor_type: str
    actor_id: uuid.UUID
    data: dict[str, Any] = Field(default_factory=dict)
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
```

- [ ] **Step 4: Implement the protocol**

```python
# src/theseus/keel/event_store/protocols.py
from __future__ import annotations

import uuid
from typing import Any, Protocol

from theseus.keel.event_store.models import EventRecord


class EventStoreProtocol(Protocol):
    """Protocol for the event store subsystem."""

    async def append(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: uuid.UUID,
        actor_type: str,
        actor_id: uuid.UUID,
        data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> EventRecord: ...

    async def get_events_for_entity(
        self, entity_type: str, entity_id: uuid.UUID
    ) -> list[EventRecord]: ...

    async def get_events_by_type(self, event_type: str) -> list[EventRecord]: ...
```

- [ ] **Step 5: Implement the event store**

```python
# src/theseus/keel/event_store/store.py
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

    async def append(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: uuid.UUID,
        actor_type: str,
        actor_id: uuid.UUID,
        data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> EventRecord:
        event = Event(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            data=data,
            metadata_=metadata or {},
        )
        self._session.add(event)
        await self._session.flush()
        return EventRecord.model_validate(event)

    async def get_events_for_entity(
        self, entity_type: str, entity_id: uuid.UUID
    ) -> list[EventRecord]:
        stmt = (
            select(Event)
            .where(Event.entity_type == entity_type, Event.entity_id == entity_id)
            .order_by(Event.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return [EventRecord.model_validate(row) for row in result.scalars().all()]

    async def get_events_by_type(self, event_type: str) -> list[EventRecord]:
        stmt = (
            select(Event)
            .where(Event.event_type == event_type)
            .order_by(Event.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return [EventRecord.model_validate(row) for row in result.scalars().all()]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/keel/event_store/test_store.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "feat: Event Store with append-only PostgreSQL storage

Append-only events table with JSONB data, indexed for entity lookup
and event type queries. EventRecord Pydantic model for data transfer.
PostgresEventStore implements append, entity query, and type query
with timestamp ordering."
```

---

## Task 7: Knowledge Graph

**Files:**
- Create: `src/theseus/keel/knowledge_graph/models.py`
- Create: `src/theseus/keel/knowledge_graph/graph.py`
- Create: `src/theseus/keel/knowledge_graph/protocols.py`
- Create: `tests/keel/knowledge_graph/test_graph.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/keel/knowledge_graph/test_graph.py
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph


@pytest.fixture
def graph(db_session: AsyncSession) -> PostgresKnowledgeGraph:
    return PostgresKnowledgeGraph(session=db_session)


class TestPostgresKnowledgeGraph:
    @pytest.mark.asyncio
    async def test_register_entity_type(self, graph: PostgresKnowledgeGraph) -> None:
        node = await graph.register_entity_type(
            plank="inventory",
            entity="StockItem",
            description="A trackable inventory item",
        )
        assert node.plank == "inventory"
        assert node.entity == "StockItem"
        assert node.full_name == "inventory.StockItem"

    @pytest.mark.asyncio
    async def test_register_relationship_type(self, graph: PostgresKnowledgeGraph) -> None:
        await graph.register_entity_type("inventory", "StockItem", "Item")
        await graph.register_entity_type("contacts", "Contact", "Contact")
        edge = await graph.register_relationship_type(
            source="inventory.StockItem",
            target="contacts.Contact",
            relation_name="suppliers",
            relation_type="many_to_many",
        )
        assert edge.source_full_name == "inventory.StockItem"
        assert edge.target_full_name == "contacts.Contact"
        assert edge.relation_name == "suppliers"

    @pytest.mark.asyncio
    async def test_get_entity_type(self, graph: PostgresKnowledgeGraph) -> None:
        await graph.register_entity_type("test", "Widget", "A widget")
        result = await graph.get_entity_type("test.Widget")
        assert result is not None
        assert result.entity == "Widget"

    @pytest.mark.asyncio
    async def test_get_related_types(self, graph: PostgresKnowledgeGraph) -> None:
        await graph.register_entity_type("inventory", "StockItem", "Item")
        await graph.register_entity_type("contacts", "Contact", "Contact")
        await graph.register_entity_type("invoicing", "InvoiceLine", "Line")
        await graph.register_relationship_type(
            "inventory.StockItem", "contacts.Contact", "suppliers", "many_to_many"
        )
        await graph.register_relationship_type(
            "invoicing.InvoiceLine", "inventory.StockItem", "product", "many_to_one"
        )
        related = await graph.get_related_types("inventory.StockItem")
        related_names = {r.full_name for r in related}
        assert "contacts.Contact" in related_names
        assert "invoicing.InvoiceLine" in related_names

    @pytest.mark.asyncio
    async def test_get_types_by_plank(self, graph: PostgresKnowledgeGraph) -> None:
        await graph.register_entity_type("inventory", "StockItem", "Item")
        await graph.register_entity_type("inventory", "Warehouse", "Warehouse")
        await graph.register_entity_type("contacts", "Contact", "Contact")
        types = await graph.get_types_by_plank("inventory")
        names = {t.entity for t in types}
        assert names == {"StockItem", "Warehouse"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/keel/knowledge_graph/test_graph.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement knowledge graph models**

```python
# src/theseus/keel/knowledge_graph/models.py
from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from theseus.database import Base


class GraphNode(Base):
    """An entity type registered in the knowledge graph."""

    __tablename__ = "graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plank: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(201), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("plank", "entity", name="uq_graph_nodes_plank_entity"),
    )


class GraphEdge(Base):
    """A relationship type between two entity types in the knowledge graph."""

    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False
    )
    source_full_name: Mapped[str] = mapped_column(String(201), nullable=False, index=True)
    target_full_name: Mapped[str] = mapped_column(String(201), nullable=False, index=True)
    relation_name: Mapped[str] = mapped_column(String(100), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)


class GraphNodeRecord(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    plank: str
    entity: str
    full_name: str
    description: str


class GraphEdgeRecord(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    source_full_name: str
    target_full_name: str
    relation_name: str
    relation_type: str
```

- [ ] **Step 4: Implement the protocol**

```python
# src/theseus/keel/knowledge_graph/protocols.py
from __future__ import annotations

from typing import Protocol

from theseus.keel.knowledge_graph.models import GraphEdgeRecord, GraphNodeRecord


class KnowledgeGraphProtocol(Protocol):
    """Protocol for the knowledge graph subsystem."""

    async def register_entity_type(
        self, plank: str, entity: str, description: str
    ) -> GraphNodeRecord: ...

    async def register_relationship_type(
        self,
        source: str,
        target: str,
        relation_name: str,
        relation_type: str,
    ) -> GraphEdgeRecord: ...

    async def get_entity_type(self, full_name: str) -> GraphNodeRecord | None: ...

    async def get_related_types(self, full_name: str) -> list[GraphNodeRecord]: ...

    async def get_types_by_plank(self, plank: str) -> list[GraphNodeRecord]: ...
```

- [ ] **Step 5: Implement the knowledge graph**

```python
# src/theseus/keel/knowledge_graph/graph.py
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.knowledge_graph.models import (
    GraphEdge,
    GraphEdgeRecord,
    GraphNode,
    GraphNodeRecord,
)


class PostgresKnowledgeGraph:
    """Knowledge graph backed by PostgreSQL tables.

    Stores entity types as nodes and relationship types as edges.
    Abstracted behind KnowledgeGraphProtocol so the implementation
    can be swapped for Neo4j or Apache AGE if graph complexity demands it.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_entity_type(
        self, plank: str, entity: str, description: str
    ) -> GraphNodeRecord:
        node = GraphNode(
            plank=plank,
            entity=entity,
            full_name=f"{plank}.{entity}",
            description=description,
        )
        self._session.add(node)
        await self._session.flush()
        return GraphNodeRecord.model_validate(node)

    async def register_relationship_type(
        self,
        source: str,
        target: str,
        relation_name: str,
        relation_type: str,
    ) -> GraphEdgeRecord:
        source_node = await self._get_node(source)
        target_node = await self._get_node(target)
        if source_node is None:
            msg = f"Source entity type not found: {source}"
            raise ValueError(msg)
        if target_node is None:
            msg = f"Target entity type not found: {target}"
            raise ValueError(msg)

        edge = GraphEdge(
            source_id=source_node.id,
            target_id=target_node.id,
            source_full_name=source,
            target_full_name=target,
            relation_name=relation_name,
            relation_type=relation_type,
        )
        self._session.add(edge)
        await self._session.flush()
        return GraphEdgeRecord.model_validate(edge)

    async def get_entity_type(self, full_name: str) -> GraphNodeRecord | None:
        node = await self._get_node(full_name)
        if node is None:
            return None
        return GraphNodeRecord.model_validate(node)

    async def get_related_types(self, full_name: str) -> list[GraphNodeRecord]:
        """Get all entity types related to the given type (in either direction)."""
        edges_stmt = select(GraphEdge).where(
            or_(
                GraphEdge.source_full_name == full_name,
                GraphEdge.target_full_name == full_name,
            )
        )
        result = await self._session.execute(edges_stmt)
        edges = result.scalars().all()

        related_names: set[str] = set()
        for edge in edges:
            if edge.source_full_name == full_name:
                related_names.add(edge.target_full_name)
            else:
                related_names.add(edge.source_full_name)

        if not related_names:
            return []

        nodes_stmt = select(GraphNode).where(GraphNode.full_name.in_(related_names))
        result = await self._session.execute(nodes_stmt)
        return [GraphNodeRecord.model_validate(n) for n in result.scalars().all()]

    async def get_types_by_plank(self, plank: str) -> list[GraphNodeRecord]:
        stmt = select(GraphNode).where(GraphNode.plank == plank)
        result = await self._session.execute(stmt)
        return [GraphNodeRecord.model_validate(n) for n in result.scalars().all()]

    async def _get_node(self, full_name: str) -> GraphNode | None:
        stmt = select(GraphNode).where(GraphNode.full_name == full_name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/keel/knowledge_graph/test_graph.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "feat: Knowledge Graph with PostgreSQL-backed entity and relationship registry

GraphNode stores entity types, GraphEdge stores relationship types.
Supports registration, lookup, bidirectional traversal, and plank
filtering. Abstracted behind KnowledgeGraphProtocol for future swap
to Neo4j or Apache AGE."
```

---

## Task 8: Auth Foundation

**Files:**
- Create: `src/theseus/keel/auth/models.py`
- Create: `src/theseus/keel/auth/service.py`
- Create: `src/theseus/keel/auth/dependencies.py`
- Create: `src/theseus/keel/auth/protocols.py`
- Create: `tests/keel/auth/test_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/keel/auth/test_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.auth.models import CrewRole
from theseus.keel.auth.service import AuthService


@pytest.fixture
def auth_service(db_session: AsyncSession) -> AuthService:
    return AuthService(session=db_session)


class TestAuthService:
    @pytest.mark.asyncio
    async def test_create_crew_member(self, auth_service: AuthService) -> None:
        member = await auth_service.create_crew_member(
            username="captain",
            password="secure-password-123",
            display_name="Captain Hook",
            role=CrewRole.HELMSMAN,
        )
        assert member.username == "captain"
        assert member.display_name == "Captain Hook"
        assert member.role == CrewRole.HELMSMAN
        assert member.password_hash != "secure-password-123"

    @pytest.mark.asyncio
    async def test_authenticate_valid_credentials(self, auth_service: AuthService) -> None:
        await auth_service.create_crew_member(
            username="bosun_maria",
            password="maria-pass-456",
            display_name="Maria",
            role=CrewRole.BOSUN,
        )
        member = await auth_service.authenticate("bosun_maria", "maria-pass-456")
        assert member is not None
        assert member.username == "bosun_maria"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, auth_service: AuthService) -> None:
        await auth_service.create_crew_member(
            username="deckhand_tom",
            password="correct-password",
            display_name="Tom",
            role=CrewRole.DECKHAND,
        )
        member = await auth_service.authenticate("deckhand_tom", "wrong-password")
        assert member is None

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self, auth_service: AuthService) -> None:
        member = await auth_service.authenticate("nobody", "password")
        assert member is None

    @pytest.mark.asyncio
    async def test_create_access_token(self, auth_service: AuthService) -> None:
        member = await auth_service.create_crew_member(
            username="helmsman",
            password="helm-pass",
            display_name="Helmsman",
            role=CrewRole.HELMSMAN,
        )
        token = auth_service.create_access_token(member)
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_verify_access_token(self, auth_service: AuthService) -> None:
        member = await auth_service.create_crew_member(
            username="verified_user",
            password="pass",
            display_name="Verified",
            role=CrewRole.BOSUN,
        )
        token = auth_service.create_access_token(member)
        payload = auth_service.verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == str(member.id)
        assert payload["role"] == CrewRole.BOSUN.value

    @pytest.mark.asyncio
    async def test_assign_plank_scope(self, auth_service: AuthService) -> None:
        member = await auth_service.create_crew_member(
            username="scoped_user",
            password="pass",
            display_name="Scoped",
            role=CrewRole.BOSUN,
            plank_scopes=["inventory", "manufacturing"],
        )
        assert member.plank_scopes == ["inventory", "manufacturing"]

    @pytest.mark.asyncio
    async def test_duplicate_username_raises(self, auth_service: AuthService) -> None:
        await auth_service.create_crew_member(
            username="unique_user",
            password="pass",
            display_name="First",
            role=CrewRole.DECKHAND,
        )
        with pytest.raises(ValueError, match="already exists"):
            await auth_service.create_crew_member(
                username="unique_user",
                password="pass2",
                display_name="Second",
                role=CrewRole.DECKHAND,
            )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/keel/auth/test_service.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement auth models**

```python
# src/theseus/keel/auth/models.py
from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from theseus.database import Base


class CrewRole(StrEnum):
    HELMSMAN = "helmsman"
    BOSUN = "bosun"
    DECKHAND = "deckhand"


class CrewMember(Base):
    """SQLAlchemy model for a Theseus user (Crew member)."""

    __tablename__ = "crew_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    plank_scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class CrewMemberRecord(BaseModel):
    """Pydantic model for crew member data transfer."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    password_hash: str
    display_name: str
    role: CrewRole
    plank_scopes: list[str]
    is_active: bool
```

- [ ] **Step 4: Implement the protocol**

```python
# src/theseus/keel/auth/protocols.py
from __future__ import annotations

from typing import Any, Protocol

from theseus.keel.auth.models import CrewMemberRecord, CrewRole


class AuthServiceProtocol(Protocol):
    async def create_crew_member(
        self,
        *,
        username: str,
        password: str,
        display_name: str,
        role: CrewRole,
        plank_scopes: list[str] | None = None,
    ) -> CrewMemberRecord: ...

    async def authenticate(self, username: str, password: str) -> CrewMemberRecord | None: ...

    def create_access_token(self, member: CrewMemberRecord) -> str: ...

    def verify_access_token(self, token: str) -> dict[str, Any] | None: ...
```

- [ ] **Step 5: Implement auth service**

```python
# src/theseus/keel/auth/service.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.config import settings
from theseus.keel.auth.models import CrewMember, CrewMemberRecord, CrewRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_crew_member(
        self,
        *,
        username: str,
        password: str,
        display_name: str,
        role: CrewRole,
        plank_scopes: list[str] | None = None,
    ) -> CrewMemberRecord:
        existing = await self._get_by_username(username)
        if existing is not None:
            msg = f"Username '{username}' already exists"
            raise ValueError(msg)

        member = CrewMember(
            username=username,
            password_hash=pwd_context.hash(password),
            display_name=display_name,
            role=role.value,
            plank_scopes=plank_scopes or [],
        )
        self._session.add(member)
        await self._session.flush()
        return CrewMemberRecord.model_validate(member)

    async def authenticate(self, username: str, password: str) -> CrewMemberRecord | None:
        member = await self._get_by_username(username)
        if member is None:
            return None
        if not pwd_context.verify(password, member.password_hash):
            return None
        return CrewMemberRecord.model_validate(member)

    def create_access_token(self, member: CrewMemberRecord) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        payload = {
            "sub": str(member.id),
            "username": member.username,
            "role": member.role.value,
            "plank_scopes": member.plank_scopes,
            "exp": expire,
        }
        return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

    async def _get_by_username(self, username: str) -> CrewMember | None:
        stmt = select(CrewMember).where(CrewMember.username == username)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
```

- [ ] **Step 6: Implement auth dependencies for FastAPI**

```python
# src/theseus/keel/auth/dependencies.py
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.database import get_session
from theseus.keel.auth.service import AuthService

security = HTTPBearer(auto_error=False)


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthService:
    return AuthService(session=session)


async def get_current_crew_member(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = auth_service.verify_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/keel/auth/test_service.py -v
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "feat: Auth foundation with Crew roles, JWT, and bcrypt

CrewMember model with Helmsman/Bosun/Deckhand roles and plank_scopes.
AuthService handles creation, authentication, JWT token creation and
verification. FastAPI dependencies for route protection."
```

---

## Task 9: LLM Gateway Skeleton

**Files:**
- Create: `src/theseus/keel/llm_gateway/gateway.py`
- Create: `src/theseus/keel/llm_gateway/protocols.py`

- [ ] **Step 1: Implement the protocol**

```python
# src/theseus/keel/llm_gateway/protocols.py
from __future__ import annotations

from typing import Any, Protocol


class LLMGatewayProtocol(Protocol):
    """Protocol for provider-agnostic LLM interaction.

    Full implementation deferred to Plan 4 (Shipwright).
    This skeleton defines the interface that future subsystems will depend on.
    """

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]: ...

    def is_configured(self) -> bool: ...
```

- [ ] **Step 2: Implement the gateway skeleton**

```python
# src/theseus/keel/llm_gateway/gateway.py
from __future__ import annotations

import logging
from typing import Any

from theseus.config import settings

logger = logging.getLogger(__name__)


class LLMGateway:
    """Provider-agnostic LLM gateway.

    Uses LiteLLM under the hood for unified API across providers.
    Full implementation in Plan 4 (Shipwright). This skeleton provides
    the interface and graceful degradation behavior.
    """

    def is_configured(self) -> bool:
        return bool(settings.llm_provider and settings.llm_model and settings.llm_api_key)

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        if not self.is_configured():
            logger.warning("LLM Gateway not configured — returning empty response")
            return {"content": "", "tool_calls": [], "configured": False}

        # Full LiteLLM integration implemented in Plan 4
        raise NotImplementedError("Full LLM Gateway implementation is in Plan 4 (Shipwright)")
```

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "feat: LLM Gateway skeleton with protocol and graceful degradation

Defines LLMGatewayProtocol interface for provider-agnostic AI.
Gateway skeleton includes is_configured() check and graceful
degradation when no LLM is configured. Full LiteLLM integration
deferred to Plan 4 (Shipwright)."
```

---

## Task 10: API Foundation — Dynamic Entity CRUD

**Files:**
- Create: `src/theseus/api/routes/health.py`
- Create: `src/theseus/api/routes/blueprints.py`
- Create: `src/theseus/api/routes/entities.py`
- Create: `src/theseus/api/middleware.py`
- Create: `src/theseus/api/dependencies.py`
- Modify: `src/theseus/main.py`
- Create: `tests/api/test_entities.py`

- [ ] **Step 1: Write the failing test for dynamic entity CRUD**

```python
# tests/api/test_entities.py
from pathlib import Path

import pytest
from httpx import AsyncClient

FIXTURES_DIR = Path(__file__).parent.parent.parent / "blueprints" / "_test"


class TestEntityCRUD:
    """Tests for the dynamic CRUD endpoints generated from Blueprints.

    Note: These tests require the app to be bootstrapped with test Blueprints.
    The test client fixture in conftest.py handles this.
    """

    @pytest.mark.asyncio
    async def test_create_entity(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/entities/test/Widget",
            json={"name": "Red Widget", "color": "red", "weight": 1.5},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Red Widget"
        assert data["color"] == "red"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_entity(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/v1/entities/test/Widget",
            json={"name": "Blue Widget", "color": "blue"},
        )
        entity_id = create_resp.json()["id"]
        get_resp = await client.get(f"/api/v1/entities/test/Widget/{entity_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Blue Widget"

    @pytest.mark.asyncio
    async def test_list_entities(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/entities/test/Widget",
            json={"name": "Widget A", "color": "red"},
        )
        await client.post(
            "/api/v1/entities/test/Widget",
            json={"name": "Widget B", "color": "green"},
        )
        response = await client.get("/api/v1/entities/test/Widget")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_update_entity(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/v1/entities/test/Widget",
            json={"name": "Old Name", "color": "red"},
        )
        entity_id = create_resp.json()["id"]
        update_resp = await client.patch(
            f"/api/v1/entities/test/Widget/{entity_id}",
            json={"name": "New Name"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_nonexistent_entity_returns_404(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/entities/test/Widget/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_nonexistent_blueprint_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/entities/fake/Nothing")
        assert response.status_code == 404
```

- [ ] **Step 2: Extract health route to its own file**

```python
# src/theseus/api/routes/health.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "theseus"}
```

- [ ] **Step 3: Implement shared API dependencies**

```python
# src/theseus/api/dependencies.py
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.database import get_session
from theseus.keel.blueprint_engine.models import Blueprint
from theseus.keel.blueprint_engine.registry import BlueprintRegistry

# Module-level registry — populated at app startup
_registry: BlueprintRegistry | None = None


def set_registry(registry: BlueprintRegistry) -> None:
    global _registry
    _registry = registry


def get_registry() -> BlueprintRegistry:
    if _registry is None:
        msg = "BlueprintRegistry not initialized"
        raise RuntimeError(msg)
    return _registry


def get_blueprint(plank: str, entity: str) -> Blueprint:
    registry = get_registry()
    bp = registry.get(f"{plank}.{entity}")
    if bp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint '{plank}.{entity}' not found",
        )
    return bp
```

- [ ] **Step 4: Implement dynamic entity CRUD routes**

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
from theseus.keel.blueprint_engine.models import Blueprint

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.post("/{plank}/{entity}", status_code=status.HTTP_201_CREATED)
async def create_entity(
    plank: str,
    entity: str,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    bp = get_blueprint(plank, entity)
    entity_id = uuid.uuid4()
    columns = _extract_columns(bp, body)
    columns["id"] = entity_id

    col_names = ", ".join(columns.keys())
    col_params = ", ".join(f":{k}" for k in columns.keys())
    query = text(f"INSERT INTO {bp.table_name} ({col_names}) VALUES ({col_params}) RETURNING *")

    result = await session.execute(query, columns)
    await session.commit()
    row = result.mappings().one()
    return _row_to_dict(row)


@router.get("/{plank}/{entity}")
async def list_entities(
    plank: str,
    entity: str,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    bp = get_blueprint(plank, entity)
    query = text(f"SELECT * FROM {bp.table_name} ORDER BY created_at DESC")
    result = await session.execute(query)
    return [_row_to_dict(row) for row in result.mappings().all()]


@router.get("/{plank}/{entity}/{entity_id}")
async def get_entity(
    plank: str,
    entity: str,
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    bp = get_blueprint(plank, entity)
    query = text(f"SELECT * FROM {bp.table_name} WHERE id = :id")
    result = await session.execute(query, {"id": entity_id})
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity} with id {entity_id} not found",
        )
    return _row_to_dict(row)


@router.patch("/{plank}/{entity}/{entity_id}")
async def update_entity(
    plank: str,
    entity: str,
    entity_id: uuid.UUID,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    bp = get_blueprint(plank, entity)
    columns = _extract_columns(bp, body)
    if not columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update",
        )

    set_clause = ", ".join(f"{k} = :{k}" for k in columns.keys())
    columns["id"] = entity_id
    query = text(
        f"UPDATE {bp.table_name} SET {set_clause}, updated_at = now() "
        f"WHERE id = :id RETURNING *"
    )

    result = await session.execute(query, columns)
    await session.commit()
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity} with id {entity_id} not found",
        )
    return _row_to_dict(row)


def _extract_columns(bp: Blueprint, body: dict[str, Any]) -> dict[str, Any]:
    """Extract only fields that exist in the Blueprint (ignore unknown fields)."""
    valid_fields = set(bp.fields.keys())
    computed_fields = {name for name, field in bp.fields.items() if field.computed}
    return {k: v for k, v in body.items() if k in valid_fields and k not in computed_fields}


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy row mapping to a JSON-serializable dict."""
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        else:
            result[key] = value
    return result
```

- [ ] **Step 5: Implement request logging middleware**

```python
# src/theseus/api/middleware.py
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("theseus.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
```

- [ ] **Step 6: Update main.py app factory with startup bootstrap**

```python
# src/theseus/main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import text

from theseus.api.dependencies import set_registry
from theseus.api.middleware import RequestLoggingMiddleware
from theseus.api.routes import blueprints, entities, health
from theseus.config import settings
from theseus.database import engine
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.schema_engine.generator import SchemaGenerator

logger = logging.getLogger("theseus")

BLUEPRINTS_DIR = Path("blueprints")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Bootstrap the Keel on startup: load Blueprints, generate schemas, register in graph."""
    logger.info("Starting Theseus ERP...")

    # Load and register Blueprints
    parser = BlueprintFileParser()
    registry = BlueprintRegistry()

    if BLUEPRINTS_DIR.exists():
        for bp in parser.parse_directory(BLUEPRINTS_DIR):
            registry.register(bp)
            logger.info("Registered Blueprint: %s", bp.full_name)

    set_registry(registry)

    # Generate database tables for all registered Blueprints
    generator = SchemaGenerator()
    for bp in registry.all():
        table = generator.generate_table(bp)
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all, checkfirst=True)
        logger.info("Ensured table exists: %s", bp.table_name)

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

- [ ] **Step 7: Create empty blueprints route file (placeholder for future)**

```python
# src/theseus/api/routes/blueprints.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/blueprints", tags=["blueprints"])

# Blueprint management endpoints (upload, validate, apply) will be
# implemented in Plan 4 when the Shipwright can generate Blueprints.
```

- [ ] **Step 8: Update conftest.py to bootstrap Blueprints for tests**

Update `tests/conftest.py` to add Blueprint bootstrapping to the test client fixture:

```python
# tests/conftest.py
import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from theseus.api.dependencies import set_registry
from theseus.database import Base, get_session
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.schema_engine.generator import SchemaGenerator
from theseus.main import create_app

TEST_DATABASE_URL = "postgresql+asyncpg://theseus:theseus@localhost:5432/theseus_test"
FIXTURES_DIR = Path(__file__).parent.parent / "blueprints" / "_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create core tables (events, graph_nodes, graph_edges, crew_members)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create Blueprint-generated tables
    parser = BlueprintFileParser()
    generator = SchemaGenerator()
    if FIXTURES_DIR.exists():
        for bp in parser.parse_directory(FIXTURES_DIR):
            table = generator.generate_table(bp)
            async with engine.begin() as conn:
                await conn.run_sync(table.metadata.create_all, checkfirst=True)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # Clean up Blueprint tables too
    generator_meta = generator._metadata
    async with engine.begin() as conn:
        await conn.run_sync(generator_meta.drop_all, checkfirst=True)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    # Register test Blueprints
    parser = BlueprintFileParser()
    registry = BlueprintRegistry()
    if FIXTURES_DIR.exists():
        for bp in parser.parse_directory(FIXTURES_DIR):
            registry.register(bp)
    set_registry(registry)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

- [ ] **Step 9: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 10: Commit**

```bash
git add .
git commit -m "feat: API foundation with dynamic entity CRUD from Blueprints

FastAPI app factory with lifespan bootstrap: loads Blueprints, generates
tables, registers in registry. Dynamic CRUD endpoints at /api/v1/entities
/{plank}/{entity} for create, list, get, update. Request logging middleware.
Blueprint-aware field validation. Full test coverage with bootstrapped
test Blueprints."
```

---

## Task 11: Integration Test — Full Pipeline

**Files:**
- Create: `tests/integration/test_full_pipeline.py`

- [ ] **Step 1: Write the full pipeline integration test**

```python
# tests/integration/test_full_pipeline.py
"""End-to-end integration test: Blueprint → Schema → Entity → Event → Graph.

Validates that the Thin Keel subsystems work together correctly.
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.models import (
    Blueprint,
    BlueprintField,
    BlueprintRelation,
    FieldType,
    RelationType,
)
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.event_store.store import PostgresEventStore
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.schema_engine.generator import SchemaGenerator


FIXTURES_DIR = Path(__file__).parent.parent.parent / "blueprints" / "_test"


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_blueprint_to_entity_to_event_to_graph(
        self, db_session: AsyncSession
    ) -> None:
        """Test the complete flow: load Blueprint, generate schema, create entity via
        raw SQL, emit an event, and register in the knowledge graph."""

        # 1. Parse a Blueprint
        parser = BlueprintFileParser()
        bp = parser.parse_file(FIXTURES_DIR / "simple-entity.blueprint.yaml")
        assert bp.entity == "Widget"

        # 2. Generate the schema (table already created by conftest)
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        assert table.name == "test_widget"

        # 3. Register in knowledge graph
        graph = PostgresKnowledgeGraph(session=db_session)
        node = await graph.register_entity_type(
            plank=bp.plank,
            entity=bp.entity,
            description=bp.description,
        )
        assert node.full_name == "test.Widget"

        # 4. Create an entity (simulating what the API does)
        from sqlalchemy import text

        entity_id = uuid.uuid4()
        await db_session.execute(
            text(
                "INSERT INTO test_widget (id, name, color, weight, is_active) "
                "VALUES (:id, :name, :color, :weight, :is_active)"
            ),
            {
                "id": entity_id,
                "name": "Integration Widget",
                "color": "red",
                "weight": 2.5,
                "is_active": True,
            },
        )

        # 5. Emit an event for the creation
        event_store = PostgresEventStore(session=db_session)
        actor_id = uuid.uuid4()
        event = await event_store.append(
            event_type="test.WidgetCreated",
            entity_type="Widget",
            entity_id=entity_id,
            actor_type="user",
            actor_id=actor_id,
            data={"name": "Integration Widget", "color": "red", "weight": 2.5},
        )
        assert event.event_type == "test.WidgetCreated"
        assert event.entity_id == entity_id

        # 6. Verify we can retrieve the event
        events = await event_store.get_events_for_entity("Widget", entity_id)
        assert len(events) == 1
        assert events[0].data["name"] == "Integration Widget"

        # 7. Verify the entity exists in the graph
        graph_node = await graph.get_entity_type("test.Widget")
        assert graph_node is not None
        assert graph_node.entity == "Widget"

    @pytest.mark.asyncio
    async def test_cross_plank_relationship_in_graph(
        self, db_session: AsyncSession
    ) -> None:
        """Test that cross-Plank relationships are registered in the knowledge graph."""

        graph = PostgresKnowledgeGraph(session=db_session)

        # Register two entity types from different Planks
        await graph.register_entity_type("inventory", "StockItem", "An inventory item")
        await graph.register_entity_type("contacts", "Contact", "A business contact")

        # Register the relationship
        edge = await graph.register_relationship_type(
            source="inventory.StockItem",
            target="contacts.Contact",
            relation_name="suppliers",
            relation_type="many_to_many",
        )
        assert edge.relation_name == "suppliers"

        # Verify traversal works both directions
        stock_related = await graph.get_related_types("inventory.StockItem")
        assert any(r.full_name == "contacts.Contact" for r in stock_related)

        contact_related = await graph.get_related_types("contacts.Contact")
        assert any(r.full_name == "inventory.StockItem" for r in contact_related)
```

- [ ] **Step 2: Run the integration test**

```bash
pytest tests/integration/test_full_pipeline.py -v
```

Expected: all PASS

- [ ] **Step 3: Run the complete test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests PASS

- [ ] **Step 4: Run linting and type checking**

```bash
ruff check src/ tests/
mypy src/theseus/ --ignore-missing-imports
```

Expected: no errors (or only minor type issues from dynamic SQL)

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: integration tests validating full Keel pipeline

End-to-end test: Blueprint parse → schema generate → entity create →
event emit → event query → graph register → graph traverse. Cross-Plank
relationship test validates bidirectional graph traversal. This proves
the Thin Keel subsystems work together correctly."
```

---

## Task 12: Generate Initial Alembic Migration

**Files:**
- Modify: `alembic/env.py` (already created in Task 2)
- Generate: `alembic/versions/0001_initial_keel_tables.py`

- [ ] **Step 1: Generate the initial migration**

```bash
cd /home/justin/lakeshore-studio/ai-projects/opensource-ai-erp
source .venv/bin/activate
alembic revision --autogenerate -m "initial keel tables"
```

This should detect the Event, GraphNode, GraphEdge, and CrewMember models and generate CREATE TABLE statements.

- [ ] **Step 2: Review the generated migration**

```bash
cat alembic/versions/*initial_keel_tables*.py
```

Verify it contains:
- `events` table with all columns and indexes
- `graph_nodes` table with unique constraint
- `graph_edges` table with foreign keys
- `crew_members` table with unique username

- [ ] **Step 3: Apply the migration to the dev database**

```bash
alembic upgrade head
```

Expected: migration applies cleanly

- [ ] **Step 4: Verify migration can be reversed**

```bash
alembic downgrade base
alembic upgrade head
```

Expected: both directions work cleanly

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: initial Alembic migration for Keel tables

Auto-generated migration for events, graph_nodes, graph_edges, and
crew_members tables. Verified upgrade and downgrade both work."
```

---

## Task 13: Final Verification & Documentation

**Files:**
- Create: `README.md`

- [ ] **Step 1: Run the complete test suite one final time**

```bash
pytest tests/ -v --cov=theseus --cov-report=term-missing
```

Expected: all PASS with coverage report

- [ ] **Step 2: Run Docker Compose to verify deployment**

```bash
docker compose up --build -d
sleep 5
curl http://localhost:8000/health
docker compose down
```

Expected: `{"status":"ok","service":"theseus"}`

- [ ] **Step 3: Create README.md**

```markdown
# Theseus ERP

An open-source, AI-first ERP for small manufacturing and trade businesses.

> Named after the Ship of Theseus — every module can be rebuilt, no two implementations are alike.

## Quick Start

```bash
# Clone and start
git clone <repo-url>
cd theseus
docker compose up -d

# Open http://localhost:8000/health
```

## Development

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start database
docker compose up db -d
docker compose exec db psql -U theseus -c "CREATE DATABASE theseus_test;"

# Run migrations
alembic upgrade head

# Run tests
pytest tests/ -v

# Lint and type check
ruff check src/ tests/
mypy src/theseus/ --ignore-missing-imports
```

## Architecture

See `docs/superpowers/specs/2026-04-15-theseus-erp-architecture-design.md` for the full architecture spec.

## License

AGPL-3.0-or-later
```

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "feat: README and final verification of Thin Keel

Complete Plan 1: Thin Keel foundation with Blueprint Engine, Schema
Engine, Event Store, Knowledge Graph, Auth, LLM Gateway skeleton,
and dynamic entity CRUD API. All tests passing."
```

---

## Summary

This plan builds the Thin Keel in 13 tasks with 70+ individual steps. After completion, the following is operational:

| Subsystem | Status | What It Does |
|-----------|--------|-------------|
| Blueprint Engine | Complete | Parse YAML → validated Pydantic models, in-memory registry |
| Schema Engine | Complete | Blueprint → SQLAlchemy Table → PostgreSQL tables |
| Event Store | Complete | Append-only events, entity queries, type queries |
| Knowledge Graph | Complete | Entity type and relationship registration, bidirectional traversal |
| Auth | Complete | Crew roles, JWT tokens, password hashing, plank scopes |
| LLM Gateway | Skeleton | Protocol defined, graceful degradation when unconfigured |
| API | Complete | Dynamic CRUD for any registered Blueprint entity |
| Migrations | Complete | Alembic with async PostgreSQL support |
| Testing | Complete | Full unit + integration coverage, async fixtures |

**Phase 2 (Parallel Planks) can now begin** — the Keel provides everything needed to define Contacts, Inventory, and Invoicing Planks as YAML Blueprints and have them automatically generate working database tables, API endpoints, events, and knowledge graph entries.
