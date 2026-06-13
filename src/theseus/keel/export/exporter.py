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
            result = await session.execute(text(f"SELECT * FROM {bp.table_name}"))
            cols = list(result.keys())  # real DB columns, available even with zero rows
            rows = result.mappings().all()
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(cols)
            for row in rows:
                writer.writerow(["" if row[c] is None else str(row[c]) for c in cols])
            zf.writestr(f"{bp.table_name}.csv", buf.getvalue())

        # All asset versions, not just current — a full backup keeps the whole history.
        keys = (
            await session.execute(text("SELECT storage_key FROM asset_versions"))
        ).scalars().all()
        skipped: list[str] = []
        for key in keys:
            try:
                data = await storage.get(key)
            except Exception:  # noqa: BLE001 — one missing object must not abort the whole export
                skipped.append(key)
                continue
            zf.writestr(f"assets/{key}", data)  # NOTE: whole file in memory — fine at maker scale
        if skipped:
            zf.writestr("_missing_assets.txt", "\n".join(skipped))
