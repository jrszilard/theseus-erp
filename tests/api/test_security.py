import uuid

import pytest

from theseus.api.security import check_production_safety
from theseus.config import Settings


@pytest.mark.asyncio
async def test_cross_site_post_is_blocked(client) -> None:
    resp = await client.post(
        "/designs", data={"title": "x"},
        headers={"Sec-Fetch-Site": "cross-site"}, follow_redirects=False,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_same_origin_post_allowed(client) -> None:
    resp = await client.post(
        "/designs", data={"title": "Same Origin " + uuid.uuid4().hex[:6]},
        headers={"Sec-Fetch-Site": "same-origin"}, follow_redirects=False,
    )
    assert resp.status_code in (303, 422)  # passes the guard, reaches the handler


@pytest.mark.asyncio
async def test_get_is_never_blocked(client) -> None:
    resp = await client.get("/", headers={"Sec-Fetch-Site": "cross-site"})
    assert resp.status_code == 200


def test_boot_guard_rejects_default_secret_when_enforced() -> None:
    s = Settings(enforce_production=True, secret_key="change-me-in-production")
    with pytest.raises(RuntimeError):
        check_production_safety(s)


def test_boot_guard_passes_with_real_secret() -> None:
    s = Settings(
        enforce_production=True,
        secret_key="a-real-secret-value-not-the-default",
        storage_access_key="real-key",
        storage_secret_key="real-secret",
        database_url="postgresql+asyncpg://real:realpw@localhost:5432/theseus",
    )
    check_production_safety(s)  # must not raise


@pytest.mark.asyncio
async def test_no_sec_fetch_site_header_passes(client) -> None:
    # Absent header (curl/API/old browsers) must pass — this is what keeps the guard API-safe.
    resp = await client.post(
        "/designs", data={"title": f"NoHeader {uuid.uuid4().hex[:6]}"},
        follow_redirects=False,
    )
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_sec_fetch_site_none_is_allowed(client) -> None:
    # 'none' = top-level navigation (bookmark/address bar) — must not be blocked.
    resp = await client.post(
        "/designs", data={"title": f"Nav {uuid.uuid4().hex[:6]}"},
        headers={"Sec-Fetch-Site": "none"}, follow_redirects=False,
    )
    assert resp.status_code in (303, 422)


def test_boot_guard_rejects_longer_default_secret() -> None:
    from theseus.config import Settings
    s = Settings(
        enforce_production=True,
        secret_key="change-me-in-production-use-openssl-rand-hex-32",
        storage_access_key="real", storage_secret_key="real",
    )
    import pytest as _pytest
    with _pytest.raises(RuntimeError):
        check_production_safety(s)
