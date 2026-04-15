from pathlib import Path
from typing import Protocol

from theseus.keel.blueprint_engine.models import Blueprint


class BlueprintParser(Protocol):
    """Protocol for parsing Blueprint files into validated models."""
    def parse_file(self, path: Path) -> Blueprint: ...
    def parse_directory(self, path: Path) -> list[Blueprint]: ...
