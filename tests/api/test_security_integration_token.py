import pytest

from theseus.api.security import check_production_safety
from theseus.config import Settings

# valid (non-default) secrets so only the integration token can be the offender
_VALID = dict(
    enforce_production=True,
    secret_key="a" * 40,
    storage_access_key="real-access-key",
    storage_secret_key="real-secret-key",
    database_url="postgresql+asyncpg://real:realpw@db:5432/prod",
)


def test_placeholder_token_refuses_boot():
    s = Settings(**_VALID, integration_api_token="REPLACE_WITH_TOKEN")
    with pytest.raises(RuntimeError) as exc:
        check_production_safety(s)
    assert "integration_api_token" in str(exc.value)


def test_short_token_refuses_boot():
    s = Settings(**_VALID, integration_api_token="short")
    with pytest.raises(RuntimeError) as exc:
        check_production_safety(s)
    assert "integration_api_token" in str(exc.value)


def test_unset_token_is_allowed():
    # opt-in: an empty token just disables the API, it must not block boot
    check_production_safety(Settings(**_VALID, integration_api_token=""))


def test_valid_token_is_allowed():
    check_production_safety(Settings(**_VALID, integration_api_token="x" * 32))
