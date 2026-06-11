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
