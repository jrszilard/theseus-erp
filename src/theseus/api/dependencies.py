from __future__ import annotations

from fastapi import HTTPException, status

from theseus.keel.blueprint_engine.models import Blueprint
from theseus.keel.blueprint_engine.registry import BlueprintRegistry

_registry: BlueprintRegistry | None = None


def set_registry(registry: BlueprintRegistry) -> None:
    global _registry
    _registry = registry


def get_registry() -> BlueprintRegistry:
    if _registry is None:
        raise RuntimeError("BlueprintRegistry not initialized")
    return _registry


def get_blueprint(plank: str, entity: str) -> Blueprint:
    registry = get_registry()
    bp = registry.get(f"{plank}.{entity}")
    if bp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Blueprint '{plank}.{entity}' not found")
    return bp
