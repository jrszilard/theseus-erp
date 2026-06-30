from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from starlette.requests import Request

    from theseus.config import Settings

logger = logging.getLogger("theseus.security")

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_ALLOWED_SITE = {"same-origin", "none"}

_DEFAULT_SECRETS = {
    "secret_key": {"change-me-in-production", "change-me-in-production-use-openssl-rand-hex-32"},
    "storage_access_key": {"minioadmin"},
    "storage_secret_key": {"minioadmin"},
}


class SameOriginMiddleware(BaseHTTPMiddleware):
    """Block cross-site state-changing requests (CSRF defense).

    Defense-in-depth with the current JWT bearer auth (browsers don't auto-attach
    bearer tokens cross-origin); becomes the primary CSRF control once the app sits
    behind Caddy HTTP Basic Auth, whose ambient credentials a browser WOULD auto-send.

    Unsafe methods are rejected only when the browser explicitly reports the request
    is cross-site via Sec-Fetch-Site (a forbidden header page JS cannot forge).
    Non-browser clients (curl, API callers) omit the header and pass — auth gates them.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in _SAFE_METHODS:
            site = request.headers.get("sec-fetch-site")
            if site is not None and site not in _ALLOWED_SITE:
                logger.warning(
                    "cross-site request blocked: %s %s (sec-fetch-site=%s)",
                    request.method, request.url.path, site,
                )
                return JSONResponse({"detail": "cross-site request blocked"}, status_code=403)
        return await call_next(request)


def check_production_safety(settings: Settings) -> None:
    """Raise if production enforcement is on but secrets are still defaults."""
    if not settings.enforce_production:
        return
    offenders = [
        field
        for field, defaults in _DEFAULT_SECRETS.items()
        if getattr(settings, field) in defaults
    ]
    if "theseus:theseus@" in settings.database_url:
        offenders.append("database_url (default password)")
    placeholder = "REPLACE"
    for field in ("secret_key", "storage_access_key", "storage_secret_key", "database_url"):
        value = getattr(settings, field)
        if placeholder in value.upper() and field not in offenders:
            offenders.append(f"{field} (unreplaced placeholder)")
    token = settings.integration_api_token
    if token and (placeholder in token.upper() or len(token) < 16):
        offenders.append("integration_api_token (placeholder or too short)")
    if offenders:
        raise RuntimeError(
            "Refusing to start: default values for "
            + ", ".join(sorted(offenders))
            + ". Set real secrets (openssl rand -hex 32) before enabling enforce_production."
        )
