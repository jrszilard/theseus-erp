from pathlib import Path

from jinja2 import Environment, FileSystemLoader

COMPONENTS = Path("hull-ui/design-system/components")


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(COMPONENTS)), autoescape=True)


def _render(macro_call: str, **ctx) -> str:
    env = _env()
    tmpl = env.from_string("{% import 'primitives.html' as ui %}" + macro_call)
    return tmpl.render(**ctx)


def test_button_renders_label_and_class() -> None:
    out = _render("{{ ui.button('Run', variant='primary') }}")
    assert "Run" in out
    assert 'class="btn btn-primary"' in out


def test_badge_variant() -> None:
    out = _render("{{ ui.badge('low', variant='warning') }}")
    assert "low" in out
    assert "badge-warning" in out


def test_input_has_name_and_value() -> None:
    out = _render("{{ ui.input(name='qty', value='5', type='number') }}")
    assert 'name="qty"' in out
    assert 'value="5"' in out
    assert 'type="number"' in out


def test_card_wraps_content() -> None:
    out = _render("{% call ui.card() %}INSIDE{% endcall %}")
    assert "INSIDE" in out
    assert 'class="card"' in out


def test_escapes_user_content() -> None:
    out = _render("{{ ui.badge(label) }}", label="<script>x</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_modal_accessibility_attrs() -> None:
    out = _render("{% call ui.modal('dlg', 'My Modal') %}body{% endcall %}")
    assert 'role="dialog"' in out
    assert 'aria-modal="true"' in out
    assert "hidden" in out
    assert "My Modal" in out
    assert "body" in out
