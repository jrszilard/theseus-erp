import pytest

from theseus.keel.blueprint_engine.parser import BlueprintFileParser
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.shipwright.context import ContextBuilder

from pathlib import Path
PLANKS_DIR = Path(__file__).parent.parent.parent / "planks"


class TestContextBuilder:
    def test_build_keel_context(self) -> None:
        builder = ContextBuilder()
        ctx = builder.build_keel_context()
        assert "Theseus ERP" in ctx
        assert "Shipwright" in ctx
        assert "Plank" in ctx

    def test_build_ship_context_includes_blueprints(self) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for plank_dir in sorted(PLANKS_DIR.iterdir()):
            bp_dir = plank_dir / "blueprints"
            if bp_dir.is_dir():
                for bp in parser.parse_directory(bp_dir):
                    registry.register(bp)

        builder = ContextBuilder(registry=registry)
        ctx = builder.build_ship_context()
        assert "contacts.Contact" in ctx
        assert "inventory.StockItem" in ctx
        assert "invoicing.Invoice" in ctx

    def test_build_crew_context(self) -> None:
        builder = ContextBuilder()
        ctx = builder.build_crew_context(
            username="maria",
            role="bosun",
            plank_scopes=["inventory", "manufacturing"],
        )
        assert "maria" in ctx
        assert "bosun" in ctx
        assert "inventory" in ctx

    def test_build_system_prompt_combines_all_layers(self) -> None:
        parser = BlueprintFileParser()
        registry = BlueprintRegistry()
        for plank_dir in sorted(PLANKS_DIR.iterdir()):
            bp_dir = plank_dir / "blueprints"
            if bp_dir.is_dir():
                for bp in parser.parse_directory(bp_dir):
                    registry.register(bp)

        builder = ContextBuilder(registry=registry)
        prompt = builder.build_system_prompt(
            username="captain",
            role="helmsman",
            plank_scopes=[],
        )
        # Should contain all layers
        assert "Theseus ERP" in prompt
        assert "contacts.Contact" in prompt
        assert "captain" in prompt
