from __future__ import annotations

import io

from PIL import Image

from theseus.keel.assets.thumbnails import make_thumbnail


def test_make_thumbnail_shrinks_image_and_returns_png() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "blue").save(buf, format="PNG")
    thumb = make_thumbnail(buf.getvalue(), max_px=128)
    assert thumb is not None
    out = Image.open(io.BytesIO(thumb))
    assert max(out.size) <= 128
    assert out.format == "PNG"


def test_make_thumbnail_returns_none_for_non_image() -> None:
    assert make_thumbnail(b"<svg/>", max_px=128) is None
