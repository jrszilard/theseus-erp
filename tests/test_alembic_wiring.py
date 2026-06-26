from sqlalchemy import MetaData

from theseus.bootstrap import build_registry, register_blueprint_tables


def test_register_blueprint_tables_exposes_maker_tables():
    """env.py calls register_blueprint_tables(build_registry()) on Base.metadata so
    autogenerate/check see the dynamically-generated maker tables. Prove the helper
    actually puts them in a metadata (use a fresh MetaData to avoid colliding with the
    session test fixture's Base.metadata registration)."""
    md = register_blueprint_tables(build_registry(), MetaData())
    assert "maker_design" in md.tables                 # a maker entity table
    assert "maker_design_source_art" in md.tables       # a file-field junction table
    assert "maker_product_version" in md.tables
