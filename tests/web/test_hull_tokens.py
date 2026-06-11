import re
from pathlib import Path

import pytest

DESIGN_SYSTEM = Path("hull-ui/design-system")
MAKER_STATIC = Path("hull-ui/shells/maker/static")

# CSS files that must reference tokens only (NOT the tokens files themselves).
STYLE_FILES = [DESIGN_SYSTEM / "hull.css", MAKER_STATIC / "maker.css"]
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# literal color functions (rgb()/rgba()/hsl()/hsla()) must live in tokens, not component CSS
COLOR_FN = re.compile(r"\b(?:rgba?|hsla?)\s*\(")
# raw px other than 0px / 1px (hairlines) — values >1px must come from tokens
RAW_PX = re.compile(r"(?<![\w-])(?!0px|1px)\d+px")

# Jinja templates may use inline style= for *dynamic non-color* values (e.g. a
# flex/width bar), but color must still route through tokens — never a raw hex/rgb.
TEMPLATE_DIRS = [DESIGN_SYSTEM / "components", Path("hull-ui/shells/maker/templates")]
STYLE_ATTR = re.compile(r"""style\s*=\s*(['"])(?P<val>.*?)\1""", re.IGNORECASE | re.DOTALL)


def inline_style_color_violations(html: str) -> list[str]:
    """Inline style="..." values that hardcode a raw color (hex/rgb/hsl) instead of
    a var(--token). Dynamic, non-color inline styles (flex/width) are allowed."""
    return [
        m.group("val")
        for m in STYLE_ATTR.finditer(html)
        if HEX.search(m.group("val")) or COLOR_FN.search(m.group("val"))
    ]


def _all_templates() -> list[Path]:
    return [p for d in TEMPLATE_DIRS for p in sorted(d.rglob("*.html"))]


def test_token_files_exist() -> None:
    for name in ("tokens.css", "theme-dark.css", "density.css"):
        assert (DESIGN_SYSTEM / "tokens" / name).exists(), name


def test_required_color_role_tokens_defined() -> None:
    css = (DESIGN_SYSTEM / "tokens" / "tokens.css").read_text()
    for role in ("--color-bg", "--color-surface", "--color-border", "--color-text",
                 "--color-text-muted", "--color-primary", "--color-on-primary",
                 "--color-success", "--color-warning", "--color-danger"):
        assert role in css, f"missing token {role}"


@pytest.mark.parametrize("path", STYLE_FILES, ids=lambda p: p.name)
def test_no_hardcoded_colors_or_px(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"{path} not present yet")
    text = path.read_text()
    assert not HEX.search(text), f"hardcoded hex color in {path} — use var(--token)"
    assert not COLOR_FN.search(text), f"literal rgb/hsl color in {path} — use var(--token)"
    assert not RAW_PX.search(text), f"raw px >1px in {path} — use a spacing token"


def test_inline_style_color_detector_flags_raw_colors_only() -> None:
    # A raw hex / rgb color in an inline style= attribute bypasses the tokens — flag it.
    assert inline_style_color_violations('<div style="color:#ff0000">x</div>')
    assert inline_style_color_violations("<i style='background: rgb(1, 2, 3)'></i>")
    # A dynamic, non-color inline style (e.g. a flex/width bar) is allowed.
    assert not inline_style_color_violations('<span style="flex:{{ s.value|float }}"></span>')
    assert not inline_style_color_violations('<div style="width: var(--space-4)"></div>')


def test_templates_have_no_inline_raw_colors() -> None:
    offenders = {
        str(path): hits
        for path in _all_templates()
        if (hits := inline_style_color_violations(path.read_text()))
    }
    assert not offenders, f"raw color in inline style= — use var(--token): {offenders}"
