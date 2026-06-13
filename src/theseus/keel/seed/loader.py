from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.entities.writer import find_existing_by_unique, insert_entity

PLANKS_DIR = Path("planks")


async def seed_pack(
    session: AsyncSession,
    registry: BlueprintRegistry,
    pack: str,
    planks_dir: Path = PLANKS_DIR,
) -> dict[str, dict[str, int]]:
    """Load planks/<pack>/seeds/defaults.yaml and insert records idempotently.

    Returns {full_name: {"created": n, "skipped": m}}. Does NOT commit.
    Each seeded blueprint must declare a unique field (used as the idempotency key);
    a missing pack seed file is a no-op returning {}.
    """
    path = planks_dir / pack / "seeds" / "defaults.yaml"
    if not path.exists():
        return {}

    data: dict[str, list[dict[str, Any]]] = yaml.safe_load(path.read_text()) or {}
    summary: dict[str, dict[str, int]] = {}

    for full_name, records in data.items():
        bp = registry.get(full_name)
        if bp is None:
            raise ValueError(f"Seed references unknown blueprint '{full_name}'")
        if not any(f.unique for f in bp.fields.values()):
            raise ValueError(
                f"Cannot idempotently seed '{full_name}': it has no unique field "
                "to use as a natural key."
            )
        created = skipped = 0
        for record in (records or []):
            if await find_existing_by_unique(session, bp, record) is not None:
                skipped += 1
                continue
            await insert_entity(session, bp, record)
            created += 1
        summary[full_name] = {"created": created, "skipped": skipped}

    return summary
