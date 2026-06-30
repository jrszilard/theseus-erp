from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from theseus.config import settings


async def require_service_token(
    authorization: str | None = Header(default=None),
) -> None:
    """Gate a router on the configured integration service token.

    Disabled (503) when no token is configured; 401 on a missing/non-Bearer/invalid
    token (constant-time compare). The token is never logged.
    """
    configured = settings.integration_api_token
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="integration disabled"
        )
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )
    presented = authorization[len(prefix):].strip()
    if not hmac.compare_digest(presented.encode(), configured.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
