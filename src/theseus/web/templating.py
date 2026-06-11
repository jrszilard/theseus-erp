from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import jinja2
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from fastapi import FastAPI

HULL_UI = Path("hull-ui")
DESIGN_SYSTEM = HULL_UI / "design-system"
MAKER_SHELL = HULL_UI / "shells" / "maker"

# Templates resolve from the maker shell first, then the Hull component macros.
_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(str(MAKER_SHELL / "templates")),
    jinja2.FileSystemLoader(str(DESIGN_SYSTEM / "components")),
])
_env = jinja2.Environment(loader=_loader, autoescape=jinja2.select_autoescape())

templates = Jinja2Templates(env=_env)


def mount_static(app: FastAPI) -> None:
    """Serve owned/vendored assets — no CDN, all local."""
    app.mount(
        "/static/maker",
        StaticFiles(directory=str(MAKER_SHELL / "static")),
        name="maker-static",
    )
    app.mount(
        "/static/hull",
        StaticFiles(directory=str(DESIGN_SYSTEM)),
        name="hull-static",
    )
