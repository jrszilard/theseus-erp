import pytest
from pydantic import ValidationError

from theseus.keel.blueprint_engine.models import (
    BlueprintField,
    BlueprintRelation,
    BlueprintBehavior,
    Blueprint,
    FieldType,
    RelationType,
)


class TestBlueprintField:
    def test_valid_string_field(self) -> None:
        field = BlueprintField(type=FieldType.STRING, required=True)
        assert field.type == FieldType.STRING
        assert field.required is True
        assert field.unique is False

    def test_valid_enum_field_with_values(self) -> None:
        field = BlueprintField(
            type=FieldType.ENUM,
            values=["draft", "sent", "paid"],
        )
        assert field.values == ["draft", "sent", "paid"]

    def test_enum_field_requires_values(self) -> None:
        with pytest.raises(ValidationError, match="values"):
            BlueprintField(type=FieldType.ENUM)

    def test_decimal_field_with_default(self) -> None:
        field = BlueprintField(type=FieldType.DECIMAL, default=0)
        assert field.default == 0

    def test_computed_field(self) -> None:
        field = BlueprintField(type=FieldType.DECIMAL, computed=True)
        assert field.computed is True


class TestBlueprintRelation:
    def test_valid_many_to_one(self) -> None:
        rel = BlueprintRelation(
            type=RelationType.MANY_TO_ONE,
            target="contacts.Contact",
        )
        assert rel.type == RelationType.MANY_TO_ONE
        assert rel.target == "contacts.Contact"
        assert rel.target_plank == "contacts"
        assert rel.target_entity == "Contact"

    def test_valid_many_to_many_with_filter(self) -> None:
        rel = BlueprintRelation(
            type=RelationType.MANY_TO_MANY,
            target="contacts.Contact",
            filter={"type": "supplier"},
        )
        assert rel.filter == {"type": "supplier"}

    def test_invalid_target_format(self) -> None:
        with pytest.raises(ValidationError, match="target"):
            BlueprintRelation(
                type=RelationType.MANY_TO_ONE,
                target="no_dot_separator",
            )


class TestBlueprintBehavior:
    def test_valid_behavior(self) -> None:
        behavior = BlueprintBehavior(
            trigger="current_stock < reorder_point",
            action="emit_event",
            event="RestockNeeded",
        )
        assert behavior.trigger == "current_stock < reorder_point"
        assert behavior.event == "RestockNeeded"


class TestBlueprint:
    def test_valid_minimal_blueprint(self) -> None:
        bp = Blueprint(
            plank="test",
            entity="SimpleItem",
            version=1,
            description="A simple test entity",
            fields={
                "name": BlueprintField(type=FieldType.STRING, required=True),
            },
        )
        assert bp.plank == "test"
        assert bp.entity == "SimpleItem"
        assert bp.table_name == "test_simple_item"

    def test_valid_full_blueprint(self) -> None:
        bp = Blueprint(
            plank="inventory",
            entity="StockItem",
            version=1,
            description="A trackable item in inventory",
            fields={
                "sku": BlueprintField(type=FieldType.STRING, required=True, unique=True),
                "name": BlueprintField(type=FieldType.STRING, required=True),
                "category": BlueprintField(
                    type=FieldType.ENUM,
                    values=["raw_material", "component", "finished_good"],
                ),
                "reorder_point": BlueprintField(type=FieldType.DECIMAL, default=0),
            },
            relations={
                "suppliers": BlueprintRelation(
                    type=RelationType.MANY_TO_MANY,
                    target="contacts.Contact",
                    filter={"type": "supplier"},
                ),
            },
            behaviors={
                "on_stock_below_reorder": BlueprintBehavior(
                    trigger="current_stock < reorder_point",
                    action="emit_event",
                    event="RestockNeeded",
                ),
            },
        )
        assert bp.table_name == "inventory_stock_item"
        assert len(bp.fields) == 4
        assert len(bp.relations) == 1
        assert len(bp.behaviors) == 1

    def test_blueprint_requires_at_least_one_field(self) -> None:
        with pytest.raises(ValidationError, match="fields"):
            Blueprint(
                plank="test",
                entity="Empty",
                version=1,
                description="No fields",
                fields={},
            )


def test_file_field_type_and_multiple_flag() -> None:
    from theseus.keel.blueprint_engine.models import BlueprintField, FieldType

    single = BlueprintField(type=FieldType.FILE)
    assert single.type == FieldType.FILE
    assert single.multiple is False

    many = BlueprintField(type=FieldType.FILE, multiple=True)
    assert many.multiple is True
