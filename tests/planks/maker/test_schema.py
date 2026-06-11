from pathlib import Path

import pytest
from sqlalchemy import text

from theseus.keel.blueprint_engine.parser import BlueprintFileParser

MAKER_BP_DIR = Path(__file__).resolve().parents[3] / "planks" / "maker" / "blueprints"

EXPECTED_TABLES = {
    "maker_format", "maker_channel", "maker_design", "maker_product",
    "maker_product_version", "maker_variation", "maker_recipe", "maker_recipe_line",
    "maker_listing", "maker_market_event", "maker_sale", "maker_production_run",
}


def test_all_maker_blueprints_parse() -> None:
    parser = BlueprintFileParser()
    bps = parser.parse_directory(MAKER_BP_DIR)
    table_names = {bp.table_name for bp in bps}
    assert EXPECTED_TABLES <= table_names


@pytest.mark.asyncio
async def test_maker_tables_exist_after_create_all(db_session) -> None:
    for table in EXPECTED_TABLES:
        res = await db_session.execute(text(f"SELECT to_regclass('{table}')"))
        assert res.scalar() is not None, f"{table} was not created"


@pytest.mark.asyncio
async def test_design_file_junction_tables_exist(db_session) -> None:
    for junction in ("maker_design_source_art", "maker_design_writing",
                     "maker_product_version_production_files", "maker_product_version_mockups"):
        res = await db_session.execute(text(f"SELECT to_regclass('{junction}')"))
        assert res.scalar() is not None, f"{junction} junction missing"


@pytest.mark.asyncio
async def test_cross_plank_fk_columns_exist(db_session) -> None:
    checks = [
        ("maker_variation", "finished_stock_id"),
        ("maker_variation", "recipe_id"),
        ("maker_variation", "product_version_id"),
        ("maker_recipe_line", "material_id"),
        ("maker_recipe_line", "recipe_id"),
    ]
    for table, column in checks:
        res = await db_session.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c AND table_schema = 'public'"
        ), {"t": table, "c": column})
        assert res.scalar() == 1, f"{table}.{column} missing"
