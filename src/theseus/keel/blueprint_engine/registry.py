from theseus.keel.blueprint_engine.models import Blueprint


class BlueprintRegistry:
    """In-memory registry of loaded Blueprints, keyed by full_name (plank.Entity)."""

    def __init__(self) -> None:
        self._blueprints: dict[str, Blueprint] = {}

    def register(self, blueprint: Blueprint) -> None:
        if blueprint.full_name in self._blueprints:
            msg = f"Blueprint '{blueprint.full_name}' is already registered"
            raise ValueError(msg)
        self._blueprints[blueprint.full_name] = blueprint

    def get(self, full_name: str) -> Blueprint | None:
        return self._blueprints.get(full_name)

    def list_by_plank(self, plank: str) -> list[Blueprint]:
        return [bp for bp in self._blueprints.values() if bp.plank == plank]

    def all(self) -> list[Blueprint]:
        return list(self._blueprints.values())
