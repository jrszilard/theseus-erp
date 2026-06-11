from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from theseus.api.dependencies import set_registry
from theseus.api.middleware import RequestLoggingMiddleware
from theseus.api.routes import assets, entities, health, maker, shipwright
from theseus.database import Base, async_session_factory, engine
import theseus.keel.assets.models  # noqa: F401
import theseus.keel.event_store.models  # noqa: F401
from theseus.keel.blueprint_engine.discovery import discover_blueprint_files
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.knowledge_graph.registration import register_blueprints_in_graph
from theseus.keel.schema_engine.generator import SchemaGenerator

logger = logging.getLogger("theseus")

BLUEPRINTS_DIR = Path("blueprints")
PLANKS_DIR = Path("planks")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Theseus ERP...")

    parser = BlueprintFileParser()
    registry = BlueprintRegistry()

    for bp_file in discover_blueprint_files(BLUEPRINTS_DIR, PLANKS_DIR):
        bp = parser.parse_file(bp_file)
        registry.register(bp)
        logger.info("Registered Blueprint: %s", bp.full_name)

    set_registry(registry)

    generator = SchemaGenerator(metadata=Base.metadata)
    for bp in registry.all():
        generator.generate_table(bp)
        logger.info("Generated table: %s", bp.table_name)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

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
    app.include_router(assets.router)
    app.include_router(maker.router)
    app.include_router(shipwright.router)
    return app


app = create_app()
