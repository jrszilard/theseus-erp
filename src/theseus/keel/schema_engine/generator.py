from __future__ import annotations

import re
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
    MetaData, Numeric, String, Table, Text, func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID

from theseus.keel.blueprint_engine.models import (
    Blueprint, BlueprintField, BlueprintRelation, FieldType, RelationType,
)

FIELD_TYPE_MAP = {
    FieldType.STRING: lambda _f: String(255),
    FieldType.TEXT: lambda _f: Text(),
    FieldType.INTEGER: lambda _f: Integer(),
    FieldType.DECIMAL: lambda _f: Numeric(precision=19, scale=4),
    FieldType.BOOLEAN: lambda _f: Boolean(),
    FieldType.DATE: lambda _f: Date(),
    FieldType.DATETIME: lambda _f: DateTime(timezone=True),
    FieldType.ENUM: lambda f: Enum(*f.values, name=f"enum_{f.values[0]}_{len(f.values)}"),
    FieldType.JSON: lambda _f: JSON(),
}


class SchemaGenerator:
    """Generates SQLAlchemy Table objects from Blueprint definitions."""

    def __init__(self, metadata: MetaData | None = None) -> None:
        self._metadata = metadata or MetaData()

    def generate_table(self, blueprint: Blueprint) -> Table:
        columns = self._build_system_columns()
        columns.extend(self._build_field_columns(blueprint))
        columns.extend(self._build_relation_columns(blueprint))
        columns.extend(self._build_file_columns(blueprint))
        table = Table(blueprint.table_name, self._metadata, *columns)
        self._build_file_junctions(blueprint)
        return table

    def _build_system_columns(self) -> list[Column]:
        return [
            Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
            Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        ]

    def _build_field_columns(self, blueprint: Blueprint) -> list[Column]:
        columns: list[Column] = []
        for name, field in blueprint.fields.items():
            if field.computed or field.type == FieldType.FILE:
                continue
            col_type = FIELD_TYPE_MAP[field.type](field)
            columns.append(
                Column(name, col_type, nullable=not field.required, unique=field.unique or None, default=field.default)
            )
        return columns

    def _build_relation_columns(self, blueprint: Blueprint) -> list[Column]:
        columns: list[Column] = []
        if not blueprint.relations:
            return columns
        for name, relation in blueprint.relations.items():
            if relation.type in (RelationType.MANY_TO_ONE, RelationType.ONE_TO_ONE):
                target_table = _relation_target_table_name(relation)
                columns.append(
                    Column(f"{name}_id", UUID(as_uuid=True), ForeignKey(f"{target_table}.id"), nullable=True)
                )
        return columns

    def _build_file_columns(self, blueprint: Blueprint) -> list[Column]:
        columns: list[Column] = []
        for name, field in blueprint.fields.items():
            if field.type == FieldType.FILE and not field.multiple:
                columns.append(
                    Column(
                        f"{name}_asset_id", UUID(as_uuid=True),
                        ForeignKey("assets.id"), nullable=not field.required,
                    )
                )
        return columns

    def _build_file_junctions(self, blueprint: Blueprint) -> None:
        for name, field in blueprint.fields.items():
            if field.type == FieldType.FILE and field.multiple:
                Table(
                    f"{blueprint.table_name}_{name}", self._metadata,
                    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
                    Column(
                        f"{blueprint.table_name}_id", UUID(as_uuid=True),
                        ForeignKey(f"{blueprint.table_name}.id"), nullable=False,
                    ),
                    Column("asset_id", UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False),
                    Column("sort_order", Integer, default=0),
                )


def _relation_target_table_name(relation: BlueprintRelation) -> str:
    """Convert 'contacts.Contact' -> 'contacts_contact'."""
    entity = relation.target_entity
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", entity).lower()
    return f"{relation.target_plank}_{snake}"
