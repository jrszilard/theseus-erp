from __future__ import annotations

# Strict raster allowlist: only these are served `inline` (previewable in-browser).
# SVG is excluded on purpose — it can carry script (stored-XSS vector on the app origin).
RASTER_INLINE_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)


def _normalize(content_type: str) -> str:
    return (content_type or "").split(";")[0].strip().lower()


def is_previewable(content_type: str) -> bool:
    """True only for the raster allowlist — everything else downloads."""
    return _normalize(content_type) in RASTER_INLINE_TYPES


def disposition_for(content_type: str, filename: str) -> str:
    """`inline` for the raster allowlist, else `attachment; filename="…"`."""
    if is_previewable(content_type):
        return "inline"
    safe = filename.replace('"', "")
    return f'attachment; filename="{safe}"'
