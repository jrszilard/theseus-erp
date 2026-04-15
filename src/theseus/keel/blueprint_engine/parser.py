from pathlib import Path

import yaml

from theseus.keel.blueprint_engine.models import Blueprint


class BlueprintFileParser:
    """Parses Blueprint YAML files into validated Pydantic models."""

    SUFFIX = ".blueprint.yaml"

    def parse_file(self, path: Path) -> Blueprint:
        if not path.exists():
            msg = f"Blueprint file not found: {path}"
            raise FileNotFoundError(msg)

        with open(path) as f:
            raw = yaml.safe_load(f)

        return Blueprint.model_validate(raw)

    def parse_directory(self, path: Path) -> list[Blueprint]:
        if not path.is_dir():
            msg = f"Blueprint directory not found: {path}"
            raise FileNotFoundError(msg)

        blueprints: list[Blueprint] = []
        for file in sorted(path.glob(f"**/*{self.SUFFIX}")):
            blueprints.append(self.parse_file(file))
        return blueprints
