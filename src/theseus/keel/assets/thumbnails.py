from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError


def make_thumbnail(data: bytes, max_px: int = 256) -> bytes | None:
    """Return PNG thumbnail bytes for raster images, or None if not an image."""
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None
    image.thumbnail((max_px, max_px))
    out = io.BytesIO()
    image.convert("RGB").save(out, format="PNG")
    return out.getvalue()
