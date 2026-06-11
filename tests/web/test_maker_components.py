from pathlib import Path

from jinja2 import Environment, FileSystemLoader

COMPONENTS = Path("hull-ui/design-system/components")


def _render(macro_call: str, **ctx) -> str:
    env = Environment(loader=FileSystemLoader(str(COMPONENTS)), autoescape=True)
    tmpl = env.from_string("{% import 'maker.html' as mk %}" + macro_call)
    return tmpl.render(**ctx)


def test_design_card_shows_title_and_formats() -> None:
    design = {"id": "d1", "title": "Loon on Blue Lake", "status": "released",
              "formats": ["Sticker", "Print"], "units_sold": 61}
    out = _render("{{ mk.design_card(d) }}", d=design)
    assert "Loon on Blue Lake" in out
    assert "Sticker" in out and "Print" in out
    assert 'href="/designs/d1"' in out


def test_variation_row_shows_profit_and_onhand() -> None:
    v = {"id": "v1", "sku": "8x10", "price": 25.0, "cost": 6.43,
         "profit": 18.57, "margin": 74, "sold": 18, "on_hand": 3}
    out = _render("{{ mk.variation_row(v) }}", v=v)
    assert "8x10" in out
    assert "18.57" in out
    assert "/bom/v1" in out  # the -> BOM link


def test_version_badge_current_vs_draft() -> None:
    cur = _render("{{ mk.version_badge(2, 'current') }}")
    draft = _render("{{ mk.version_badge(3, 'draft') }}")
    assert "v2" in cur and "version-current" in cur
    assert "v3" in draft and "version-draft" in draft


def test_tally_tile_has_data_attrs() -> None:
    v = {"id": "v1", "label": "Loon Sticker 3\"", "price": 4.0}
    out = _render("{{ mk.tally_tile(v) }}", v=v)
    assert 'data-variation="v1"' in out
    assert 'data-price="4.0"' in out


def test_variation_row_tolerates_missing_numbers() -> None:
    v = {"id": "v1", "sku": "x", "price": None, "cost": None, "profit": None,
         "margin": None, "sold": None, "on_hand": None}
    out = _render("{{ mk.variation_row(v) }}", v=v)  # must not raise
    assert "0.00" in out
