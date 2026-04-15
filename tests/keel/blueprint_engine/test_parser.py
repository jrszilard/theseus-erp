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
