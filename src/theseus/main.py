from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from theseus.api.dependencies import set_registry
from theseus.api.middleware import RequestLoggingMiddleware
from theseus.api.routes import assets, entities, health, maker, shipwright
from theseus.web import routes as web_routes
from theseus.web.templating import mount_static
from theseus.bootstrap import build_registry, create_all_tables
from theseus.database import async_session_factory, engine
from theseus.keel.knowledge_graph.graph import PostgresKnowledgeGraph
from theseus.keel.knowledge_graph.registration import register_blueprints_in_graph

logger = logging.getLogger("theseus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Theseus ERP...")

    registry = build_registry()
    for bp in registry.all():
        logger.info("Registered Blueprint: %s", bp.full_name)
    set_registry(registry)

    await create_all_tables(registry)

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
    app.include_router(web_routes.router)
    mount_static(app)
    return app


app = create_app()
