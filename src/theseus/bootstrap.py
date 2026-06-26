from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

# Import Keel ORM models so their tables are present in Base.metadata for create_all.
import theseus.keel.assets.models
import theseus.keel.event_store.models  # noqa: F401
from theseus.database import Base, engine
from theseus.keel.blueprint_engine.discovery import discover_blueprint_files
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.schema_engine.generator import SchemaGenerator

if TYPE_CHECKING:
    from sqlalchemy import MetaData

BLUEPRINTS_DIR = Path("blueprints")
PLANKS_DIR = Path("planks")


def build_registry(
    blueprints_dir: Path = BLUEPRINTS_DIR, planks_dir: Path = PLANKS_DIR
) -> BlueprintRegistry:
    parser = BlueprintFileParser()
    registry = BlueprintRegistry()
    for bp_file in discover_blueprint_files(blueprints_dir, planks_dir):
        registry.register(parser.parse_file(bp_file))
    return registry


def register_blueprint_tables(
    registry: BlueprintRegistry, metadata: MetaData | None = None
) -> MetaData:
    """Generate every Blueprint's SQLAlchemy table onto `metadata` (default
    Base.metadata). Shared by create_all_tables and alembic/env.py so the running
    app and the migration environment see an identical schema."""
    target = Base.metadata if metadata is None else metadata
    generator = SchemaGenerator(metadata=target)
    for bp in registry.all():
        generator.generate_table(bp)
    return target


async def create_all_tables(registry: BlueprintRegistry) -> None:
    register_blueprint_tables(registry)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)
