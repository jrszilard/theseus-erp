from theseus.keel.blueprint_engine.models import BlueprintField, FieldType, UIHints


def test_uihints_accepts_label_and_icon():
    ui = UIHints(label="Source art", icon="🎨")
    assert ui.label == "Source art"
    assert ui.icon == "🎨"


def test_uihints_label_icon_default_to_none_backward_compat():
    ui = UIHints(component="file-upload")
    assert ui.label is None
    assert ui.icon is None


def test_blueprint_file_field_carries_ui_label_and_icon():
    f = BlueprintField(
        type=FieldType.FILE, multiple=True, ui=UIHints(label="Mockups", icon="📷")
    )
    assert f.type == FieldType.FILE
    assert f.ui is not None
    assert f.ui.label == "Mockups"
    assert f.ui.icon == "📷"
