from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from theseus.api.dependencies import set_registry
from theseus.api.middleware import RequestLoggingMiddleware
from theseus.api.routes import entities, health, shipwright
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
    app.include_router(shipwright.router)
    return app


app = create_app()
