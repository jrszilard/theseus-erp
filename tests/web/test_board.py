import pytest


@pytest.mark.asyncio
async def test_board_lists_seeded_design(client, maker_seed) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "Loon on Blue Lake" in body          # the seeded design
    assert "Print" in body                       # its format
    assert "/designs/" in body                   # card links to design detail
