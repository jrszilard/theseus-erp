import pytest
from theseus.keel.blueprint_engine.models import (
    Blueprint, BlueprintField, BlueprintRelation, FieldType, RelationType,
)
from theseus.keel.schema_engine.generator import SchemaGenerator


class TestSchemaGenerator:
    def test_generate_simple_table(self) -> None:
        bp = Blueprint(plank="test", entity="Widget", version=1, description="Test widget",
            fields={"name": BlueprintField(type=FieldType.STRING, required=True),
                     "weight": BlueprintField(type=FieldType.DECIMAL, default=0),
                     "is_active": BlueprintField(type=FieldType.BOOLEAN, default=True)})
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        assert table.name == "test_widget"
        column_names = {c.name for c in table.columns}
        assert "id" in column_names
        assert "name" in column_names
        assert "weight" in column_names
        assert "is_active" in column_names
        assert "created_at" in column_names
        assert "updated_at" in column_names

    def test_string_field_nullable(self) -> None:
        bp = Blueprint(plank="test", entity="Thing", version=1, description="Test",
            fields={"required_name": BlueprintField(type=FieldType.STRING, required=True),
                     "optional_note": BlueprintField(type=FieldType.STRING)})
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        assert table.c["required_name"].nullable is False
        assert table.c["optional_note"].nullable is True

    def test_unique_field(self) -> None:
        bp = Blueprint(plank="test", entity="UniqueTest", version=1, description="Test",
            fields={"code": BlueprintField(type=FieldType.STRING, required=True, unique=True)})
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        assert table.c["code"].unique is True

    def test_enum_field_generates_check_constraint(self) -> None:
        bp = Blueprint(plank="test", entity="EnumTest", version=1, description="Test",
            fields={"status": BlueprintField(type=FieldType.ENUM, values=["draft", "sent", "paid"])})
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        assert list(table.c["status"].type.enums) == ["draft", "sent", "paid"]

    def test_field_type_mapping(self) -> None:
        bp = Blueprint(plank="test", entity="AllTypes", version=1, description="Test all types",
            fields={"a_string": BlueprintField(type=FieldType.STRING),
                     "a_text": BlueprintField(type=FieldType.TEXT),
                     "an_int": BlueprintField(type=FieldType.INTEGER),
                     "a_decimal": BlueprintField(type=FieldType.DECIMAL),
                     "a_bool": BlueprintField(type=FieldType.BOOLEAN),
                     "a_date": BlueprintField(type=FieldType.DATE),
                     "a_datetime": BlueprintField(type=FieldType.DATETIME),
                     "a_json": BlueprintField(type=FieldType.JSON)})
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        assert len([c for c in table.columns if c.name not in ("id", "created_at", "updated_at")]) == 8

    def test_computed_fields_are_excluded_from_table(self) -> None:
        bp = Blueprint(plank="test", entity="ComputedTest", version=1, description="Test",
            fields={"name": BlueprintField(type=FieldType.STRING, required=True),
                     "derived_value": BlueprintField(type=FieldType.DECIMAL, computed=True)})
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        column_names = {c.name for c in table.columns}
        assert "name" in column_names
        assert "derived_value" not in column_names

    def test_many_to_one_generates_foreign_key_column(self) -> None:
        bp = Blueprint(plank="test", entity="Order", version=1, description="Test",
            fields={"total": BlueprintField(type=FieldType.DECIMAL)},
            relations={"customer": BlueprintRelation(type=RelationType.MANY_TO_ONE, target="contacts.Contact")})
        generator = SchemaGenerator()
        table = generator.generate_table(bp)
        column_names = {c.name for c in table.columns}
        assert "customer_id" in column_names
