import alembic.command

from theseus.cli import run_migrate


def test_run_migrate_calls_upgrade_head(monkeypatch):
    captured = {}

    def fake_upgrade(cfg, revision):
        captured["revision"] = revision

    monkeypatch.setattr(alembic.command, "upgrade", fake_upgrade)
    run_migrate()
    assert captured["revision"] == "head"
