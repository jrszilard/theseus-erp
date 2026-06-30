import pytest
from fastapi import HTTPException

from theseus.config import settings
from theseus.keel.integration.auth import require_service_token

TOKEN = "test-integration-token-1234567890"


@pytest.mark.asyncio
async def test_503_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_token", "")
    with pytest.raises(HTTPException) as exc:
        await require_service_token(authorization=f"Bearer {TOKEN}")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_401_missing_header(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_token", TOKEN)
    with pytest.raises(HTTPException) as exc:
        await require_service_token(authorization=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_401_non_bearer(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_token", TOKEN)
    with pytest.raises(HTTPException) as exc:
        await require_service_token(authorization=f"Basic {TOKEN}")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_401_wrong_token(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_token", TOKEN)
    with pytest.raises(HTTPException) as exc:
        await require_service_token(authorization="Bearer wrong-token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_401_non_ascii_token(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_token", TOKEN)
    # a non-ASCII bearer must be a clean 401, not a 500 from compare_digest
    with pytest.raises(HTTPException) as exc:
        await require_service_token(authorization="Bearer tökén")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_ok_correct_token(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_token", TOKEN)
    assert await require_service_token(authorization=f"Bearer {TOKEN}") is None
