from pathlib import Path

from theseus.keel.blueprint_engine.discovery import discover_blueprint_files


def test_discovers_plank_blueprints_excluding_test_fixtures(tmp_path: Path) -> None:
    root_bp = tmp_path / "blueprints"
    (root_bp / "_test").mkdir(parents=True)
    (root_bp / "_test" / "fixture.blueprint.yaml").write_text("x")
    (root_bp / "core.blueprint.yaml").write_text("x")

    planks = tmp_path / "planks"
    (planks / "maker" / "blueprints").mkdir(parents=True)
    (planks / "maker" / "blueprints" / "design.blueprint.yaml").write_text("x")
    (planks / "inventory" / "blueprints").mkdir(parents=True)
    (planks / "inventory" / "blueprints" / "stock-item.blueprint.yaml").write_text("x")

    files = discover_blueprint_files(root_bp, planks)
    names = {f.name for f in files}

    assert "core.blueprint.yaml" in names
    assert "design.blueprint.yaml" in names
    assert "stock-item.blueprint.yaml" in names
    assert "fixture.blueprint.yaml" not in names  # _test excluded
    assert files == sorted(files)


def test_returns_empty_when_dirs_missing(tmp_path: Path) -> None:
    missing_root = tmp_path / "no_blueprints"
    missing_planks = tmp_path / "no_planks"
    assert discover_blueprint_files(missing_root, missing_planks) == []
