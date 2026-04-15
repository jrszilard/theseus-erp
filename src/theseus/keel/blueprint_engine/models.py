from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, field_validator, model_validator


class FieldType(StrEnum):
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"
    JSON = "json"


class RelationType(StrEnum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class UIHints(BaseModel):
    """Optional rendering hints for the Hull design system."""
    component: str | None = None
    colors: dict[str, str] | None = None
    max_height: str | None = None
    highlight_when: str | None = None


class BlueprintField(BaseModel):
    """A field definition within a Blueprint entity."""
    type: FieldType
    required: bool = False
    unique: bool = False
    default: Any = None
    computed: bool = False
    values: list[str] | None = None
    ui: UIHints | None = None

    @model_validator(mode="after")
    def enum_requires_values(self) -> BlueprintField:
        if self.type == FieldType.ENUM and not self.values:
            msg = "Enum fields require 'values' to be specified"
            raise ValueError(msg)
        return self


class BlueprintRelation(BaseModel):
    """A relationship to another entity, possibly in another Plank."""
    type: RelationType
    target: str
    filter: dict[str, Any] | None = None

    @field_validator("target")
    @classmethod
    def validate_target_format(cls, v: str) -> str:
        if "." not in v:
            msg = f"target must be in 'plank.Entity' format, got '{v}'"
            raise ValueError(msg)
        return v

    @property
    def target_plank(self) -> str:
        return self.target.split(".")[0]

    @property
    def target_entity(self) -> str:
        return self.target.split(".")[1]


class BlueprintBehavior(BaseModel):
    """A reactive behavior triggered by entity state changes."""
    trigger: str
    action: str
    event: str | None = None


class Blueprint(BaseModel):
    """The complete definition of a Theseus entity — the core unit of the Plank system."""
    plank: str
    entity: str
    version: int
    description: str
    fields: dict[str, BlueprintField]
    relations: dict[str, BlueprintRelation] | None = None
    behaviors: dict[str, BlueprintBehavior] | None = None

    @field_validator("fields")
    @classmethod
    def require_at_least_one_field(cls, v: dict[str, BlueprintField]) -> dict[str, BlueprintField]:
        if not v:
            msg = "Blueprint must define at least one field"
            raise ValueError(msg)
        return v

    @property
    def table_name(self) -> str:
        """Generate the PostgreSQL table name from plank + entity.
        Example: plank='inventory', entity='StockItem' -> 'inventory_stock_item'
        """
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", self.entity).lower()
        return f"{self.plank}_{snake}"

    @property
    def full_name(self) -> str:
        """Fully qualified entity name: 'plank.Entity'."""
        return f"{self.plank}.{self.entity}"
