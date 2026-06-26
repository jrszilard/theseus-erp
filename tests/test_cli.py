import pytest

import theseus.cli as cli


@pytest.mark.asyncio
async def test_run_seed_orchestrates_packs_and_commits_once(monkeypatch) -> None:
    """run_seed splits packs, seeds each, commits once, merges summaries — no real DB."""
    seeded: list[str] = []
    committed = {"count": 0}

    async def fake_seed_pack(session, registry, pack):
        seeded.append(pack)
        return {f"{pack}.Thing": {"created": 1, "skipped": 0}}

    class _Session:
        async def commit(self):
            committed["count"] += 1

    class _Ctx:
        async def __aenter__(self):
            return _Session()
        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(cli, "seed_pack", fake_seed_pack)
    monkeypatch.setattr(cli, "async_session_factory", lambda: _Ctx())

    summary = await cli.run_seed("maker, foo")

    assert seeded == ["maker", "foo"]          # split + stripped + ordered
    assert committed["count"] == 1             # single commit for all packs
    assert summary == {
        "maker.Thing": {"created": 1, "skipped": 0},
        "foo.Thing": {"created": 1, "skipped": 0},
    }


@pytest.mark.asyncio
async def test_run_seed_ignores_blank_pack_tokens(monkeypatch) -> None:
    seeded: list[str] = []

    async def fake_seed_pack(session, registry, pack):
        seeded.append(pack)
        return {}

    class _Ctx:
        async def __aenter__(self):
            class _S:
                async def commit(self_inner):
                    return None
            return _S()
        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(cli, "seed_pack", fake_seed_pack)
    monkeypatch.setattr(cli, "async_session_factory", lambda: _Ctx())

    await cli.run_seed("maker, , ,")
    assert seeded == ["maker"]


def test_main_seed_dispatches_to_run_seed(monkeypatch) -> None:
    called = {}

    async def fake_run_seed(packs):
        called["packs"] = packs

    def fake_run(coro):
        # Capture the packs argument from the coroutine's frame locals before closing it,
        # since closing the coroutine prevents its body from executing.
        called["packs"] = coro.cr_frame.f_locals.get("packs")
        coro.close()
        called["ran"] = True

    monkeypatch.setattr(cli, "run_seed", fake_run_seed)
    monkeypatch.setattr(cli.asyncio, "run", fake_run)

    rc = cli.main(["seed", "--packs", "maker"])
    assert rc == 0
    assert called["ran"] is True
    assert called["packs"] == "maker"


def test_main_returns_1_on_failure(monkeypatch, capsys) -> None:
    async def boom(packs):
        raise ValueError("kaboom")

    monkeypatch.setattr(cli, "run_seed", boom)
    rc = cli.main(["seed", "--packs", "maker"])
    assert rc == 1
    assert "kaboom" in capsys.readouterr().err


def test_main_bad_args_exits_2() -> None:
    import pytest as _pytest
    with _pytest.raises(SystemExit) as exc:
        cli.main([])  # missing required subcommand → argparse exits 2
    assert exc.value.code == 2
