import pytest
from pathlib import Path


def test_htmx_is_vendored() -> None:
    p = Path("hull-ui/design-system/vendor/htmx.min.js")
    assert p.exists() and p.stat().st_size > 1000, "HTMX must be vendored locally (no CDN)"


@pytest.mark.asyncio
async def test_layout_has_sidebar_and_local_htmx(client) -> None:
    resp = await client.get("/")
    body = resp.text
    assert 'class="sw-sidebar"' in body          # Shipwright sidebar slot
    assert "/static/hull/vendor/htmx.min.js" in body  # local HTMX, not a CDN
    assert "cdn" not in body.lower()             # no CDN references anywhere
