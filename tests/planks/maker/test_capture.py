import pytest

from theseus.planks.maker.capture import ParsedSaleLine, parse_sale_text


class _StubGateway:
    def __init__(self, content: str) -> None:
        self._content = content
    def is_configured(self) -> bool:
        return True
    async def complete(self, *, messages, tools=None, temperature=0.7):
        return {"content": self._content, "tool_calls": [], "configured": True, "error": None}


VARIATIONS = [
    {"id": "11111111-1111-1111-1111-111111111111", "label": "loon-sticker", "price": 4.0},
    {"id": "22222222-2222-2222-2222-222222222222", "label": "loon-magnet", "price": 6.0},
]


@pytest.mark.asyncio
async def test_parse_maps_lines_by_sku() -> None:
    gw = _StubGateway('[{"sku": "loon-sticker", "quantity": 12},'
                      ' {"sku": "loon-magnet", "quantity": 3, "unit_price": 6.5}]')
    lines = await parse_sale_text("sold 12 loon stickers and 3 magnets", VARIATIONS, gw)
    assert lines == [
        ParsedSaleLine("11111111-1111-1111-1111-111111111111", "loon-sticker", 12.0, None),
        ParsedSaleLine("22222222-2222-2222-2222-222222222222", "loon-magnet", 3.0, 6.5),
    ]


@pytest.mark.asyncio
async def test_parse_strips_markdown_fences() -> None:
    gw = _StubGateway('```json\n[{"sku":"loon-magnet","quantity":1}]\n```')
    lines = await parse_sale_text("a magnet", VARIATIONS, gw)
    assert len(lines) == 1 and lines[0].label == "loon-magnet"


@pytest.mark.asyncio
async def test_parse_unparseable_returns_empty() -> None:
    gw = _StubGateway("I could not understand that, sorry!")
    assert await parse_sale_text("???", VARIATIONS, gw) == []


@pytest.mark.asyncio
async def test_parse_drops_unknown_skus() -> None:
    gw = _StubGateway('[{"sku": "nope", "quantity": 5}]')
    assert await parse_sale_text("5 of nothing", VARIATIONS, gw) == []


@pytest.mark.asyncio
async def test_parse_empty_content_returns_empty() -> None:
    class _Empty:
        def is_configured(self): return False
        async def complete(self, *, messages, tools=None, temperature=0.7):
            return {"content": "", "tool_calls": [], "configured": False, "error": None}
    assert await parse_sale_text("anything", VARIATIONS, _Empty()) == []


@pytest.mark.asyncio
async def test_parse_string_unit_price() -> None:
    gw = _StubGateway('[{"sku":"loon-magnet","quantity":1,"unit_price":"6.50"}]')
    lines = await parse_sale_text("a magnet for 6.50", VARIATIONS, gw)
    assert len(lines) == 1 and lines[0].unit_price == 6.5
