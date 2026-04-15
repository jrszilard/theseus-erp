import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
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
# Only the simple fixture — related-entities.blueprint.yaml has cross-plank FKs
# (contacts.Contact) that are not present in the test schema.
SIMPLE_FIXTURE = FIXTURES_DIR / "simple-entity.blueprint.yaml"


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def test_engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    parser = BlueprintFileParser()
    generator = SchemaGenerator()
    if SIMPLE_FIXTURE.exists():
        bp = parser.parse_file(SIMPLE_FIXTURE)
        generator.generate_table(bp)
        async with eng.begin() as conn:
            await conn.run_sync(generator._metadata.create_all, checkfirst=True)

    yield eng

    # Drop Blueprint tables then Base tables
    async with eng.begin() as conn:
        await conn.run_sync(generator._metadata.drop_all, checkfirst=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    parser = BlueprintFileParser()
    registry = BlueprintRegistry()
    if SIMPLE_FIXTURE.exists():
        bp = parser.parse_file(SIMPLE_FIXTURE)
        registry.register(bp)
    set_registry(registry)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
