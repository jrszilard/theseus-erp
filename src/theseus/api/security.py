from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from theseus.config import Settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_ALLOWED_SITE = {"same-origin", "none"}

_DEFAULT_SECRETS = {
    "secret_key": {"change-me-in-production", "change-me-in-production-use-openssl-rand-hex-32"},
    "storage_access_key": {"minioadmin"},
    "storage_secret_key": {"minioadmin"},
}


class SameOriginMiddleware(BaseHTTPMiddleware):
    """Block cross-site state-changing requests (CSRF defense for ambient basic-auth).

    Unsafe methods are rejected only when the browser explicitly reports the request
    is cross-site via Sec-Fetch-Site. Non-browser clients (curl, old browsers) omit
    the header and are unaffected — auth still gates them.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in _SAFE_METHODS:
            site = request.headers.get("sec-fetch-site")
            if site is not None and site not in _ALLOWED_SITE:
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
    if offenders:
        raise RuntimeError(
            "Refusing to start: default values for "
            + ", ".join(sorted(offenders))
            + ". Set real secrets (openssl rand -hex 32) before enabling enforce_production."
        )
