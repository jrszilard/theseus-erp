from __future__ import annotations

from pathlib import Path

from theseus.database import Base, engine
from theseus.keel.blueprint_engine.discovery import discover_blueprint_files
from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.schema_engine.generator import SchemaGenerator

# Import Keel ORM models so their tables are present in Base.metadata for create_all.
import theseus.keel.assets.models  # noqa: F401
import theseus.keel.event_store.models  # noqa: F401

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


async def create_all_tables(registry: BlueprintRegistry) -> None:
    generator = SchemaGenerator(metadata=Base.metadata)
    for bp in registry.all():
        generator.generate_table(bp)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)
