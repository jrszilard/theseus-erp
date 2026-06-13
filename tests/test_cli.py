import pytest
from sqlalchemy import text

from theseus.cli import run_seed


@pytest.mark.asyncio
async def test_run_seed_seeds_maker(db_session, monkeypatch) -> None:
    # run_seed builds its own registry + tables; redirect its session + skip DDL.
    import theseus.cli as cli

    class _Ctx:
        def __init__(self, s):
            self._s = s
        async def __aenter__(self):
            return self._s
        async def __aexit__(self, *a):
            return False

    def _fake_factory():
        return _Ctx(db_session)

    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(cli, "async_session_factory", _fake_factory)
    monkeypatch.setattr(cli, "create_all_tables", _noop)

    summary = await run_seed("maker")
    # maker formats may already exist from prior tests on the shared session; assert presence not count.
    rows = (await db_session.execute(
        text("SELECT COUNT(*) FROM maker_format WHERE name = 'Sticker'")
    )).scalar()
    assert rows == 1
    assert "maker.Format" in summary
