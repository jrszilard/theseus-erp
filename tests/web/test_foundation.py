import pytest


@pytest.mark.asyncio
async def test_root_renders_app_shell(client) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    # the app shell renders: brand + the two nav sections
    assert "Maker Edition" in body
    assert "Ideas" in body
    assert "Markets" in body


@pytest.mark.asyncio
async def test_static_mount_serves_css(client) -> None:
    resp = await client.get("/static/maker/maker.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
