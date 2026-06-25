from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, NamedTuple

from sqlalchemy import text

from theseus.keel.blueprint_engine.models import FieldType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FileFieldError(ValueError):
    """Raised when (blueprint, field_name) is not a declared `file` field."""


class FileFieldTarget(NamedTuple):
    """How a Blueprint `file` field stores its asset link(s). Identifiers are
    Blueprint-derived (trusted) — safe to f-string into SQL; values stay bound params."""

    table_name: str
    field_name: str
    multiple: bool

    @property
    def junction_table(self) -> str:
        return f"{self.table_name}_{self.field_name}"

    @property
    def entity_fk(self) -> str:
        return f"{self.table_name}_id"

    @property
    def fk_column(self) -> str:
        return f"{self.field_name}_asset_id"


def resolve_file_field(blueprint: Any, field_name: str) -> FileFieldTarget:
    """Validate `field_name` is a declared FILE field on `blueprint` and describe its
    storage shape. Single source of truth for file-field name derivation — the read
    model and attach/detach all call it, so they cannot drift. Raises FileFieldError."""
    field = blueprint.fields.get(field_name) if blueprint is not None else None
    if field is None or field.type != FieldType.FILE:
        msg = f"{field_name!r} is not a file field"
        raise FileFieldError(msg)
    return FileFieldTarget(
        table_name=blueprint.table_name, field_name=field_name, multiple=field.multiple
    )


async def attach_asset(
    session: AsyncSession, registry: Any, full_name: str,
    entity_id: Any, field_name: str, asset_id: Any,
) -> None:
    """Link an existing asset to entity_id's `field_name`. multiple → append a junction
    row (next sort_order; a duplicate link is a no-op). single → set the FK (replacing
    any prior link). Never creates or deletes asset rows."""
    target = resolve_file_field(registry.get(full_name), field_name)
    if target.multiple:
        existing = (await session.execute(
            text(f"SELECT 1 FROM {target.junction_table} "
                 f"WHERE {target.entity_fk} = :e AND asset_id = :a"),
            {"e": str(entity_id), "a": str(asset_id)},
        )).scalar()
        if existing is not None:
            return
        next_order = (await session.execute(
            text(f"SELECT COALESCE(MAX(sort_order), -1) + 1 FROM {target.junction_table} "
                 f"WHERE {target.entity_fk} = :e"),
            {"e": str(entity_id)},
        )).scalar()
        await session.execute(
            text(f"INSERT INTO {target.junction_table} "
                 f"(id, {target.entity_fk}, asset_id, sort_order) VALUES (:j, :e, :a, :o)"),
            {"j": str(uuid.uuid4()), "e": str(entity_id),
             "a": str(asset_id), "o": next_order},
        )
    else:
        await session.execute(
            text(f"UPDATE {target.table_name} SET {target.fk_column} = :a WHERE id = :e"),
            {"a": str(asset_id), "e": str(entity_id)},
        )


async def detach_asset(
    session: AsyncSession, registry: Any, full_name: str,
    entity_id: Any, field_name: str, asset_id: Any,
) -> None:
    """Unlink an asset from entity_id's `field_name` (detach-only: the asset row +
    stored bytes are left intact). No-op if the link does not exist."""
    target = resolve_file_field(registry.get(full_name), field_name)
    if target.multiple:
        await session.execute(
            text(f"DELETE FROM {target.junction_table} "
                 f"WHERE {target.entity_fk} = :e AND asset_id = :a"),
            {"e": str(entity_id), "a": str(asset_id)},
        )
    else:
        await session.execute(
            text(f"UPDATE {target.table_name} SET {target.fk_column} = NULL "
                 f"WHERE id = :e AND {target.fk_column} = :a"),
            {"e": str(entity_id), "a": str(asset_id)},
        )
