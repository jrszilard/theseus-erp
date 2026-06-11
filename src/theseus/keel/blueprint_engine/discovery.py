from __future__ import annotations

from pathlib import Path

SUFFIX = ".blueprint.yaml"


def discover_blueprint_files(root_blueprints: Path, planks_dir: Path) -> list[Path]:
    """Collect all blueprint YAML files from the root blueprints dir and every
    plank's blueprints dir, skipping any path under a directory named '_test'.
    """
    files: list[Path] = []

    if root_blueprints.is_dir():
        for f in sorted(root_blueprints.glob(f"**/*{SUFFIX}")):
            if not _is_test_path(f):
                files.append(f)

    if planks_dir.is_dir():
        for plank_dir in sorted(planks_dir.iterdir()):
            bp_dir = plank_dir / "blueprints"
            if bp_dir.is_dir():
                for f in sorted(bp_dir.glob(f"**/*{SUFFIX}")):
                    if not _is_test_path(f):
                        files.append(f)

    return files


def _is_test_path(path: Path) -> bool:
    return any(part == "_test" for part in path.parts)
