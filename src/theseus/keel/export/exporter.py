from __future__ import annotations

import csv
import io
import zipfile

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.assets.factory import build_storage
from theseus.keel.assets.protocols import StorageBackend
from theseus.keel.blueprint_engine.registry import BlueprintRegistry


async def export_all(
    session: AsyncSession,
    registry: BlueprintRegistry,
    out_path: str,
    storage: StorageBackend | None = None,
) -> None:
    """Write a zip: one CSV per Blueprint table + every asset file under assets/."""
    if storage is None:
        storage = build_storage()
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for bp in registry.all():
            rows = (
                await session.execute(text(f"SELECT * FROM {bp.table_name}"))
            ).mappings().all()
            buf = io.StringIO()
            writer = csv.writer(buf)
            if rows:
                writer.writerow(rows[0].keys())
                for row in rows:
                    writer.writerow(["" if v is None else str(v) for v in row.values()])
            else:
                writer.writerow(["id", *bp.fields.keys()])
            zf.writestr(f"{bp.table_name}.csv", buf.getvalue())

        keys = (
            await session.execute(text("SELECT storage_key FROM asset_versions"))
        ).scalars().all()
        for key in keys:
            try:
                data = await storage.get(key)
            except Exception:  # noqa: BLE001 — a missing object must not abort the export
                continue
            zf.writestr(f"assets/{key}", data)
