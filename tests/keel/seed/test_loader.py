import pytest
from sqlalchemy import text

from theseus.bootstrap import build_registry
from theseus.keel.seed.loader import seed_pack


async def _count(session, table: str) -> int:
    return (await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar()


@pytest.mark.asyncio
async def test_seed_pack_inserts_and_is_idempotent(db_session) -> None:
    registry = build_registry()
    await db_session.execute(text(
        "DELETE FROM maker_channel WHERE name IN ('Etsy','eBay','In-person','Own-site')"))
    await db_session.execute(text(
        "DELETE FROM maker_format WHERE name IN "
        "('Sticker','Postcard','Print','Magnet','Original')"))
    await db_session.flush()

    first = await seed_pack(db_session, registry, "maker")
    await db_session.flush()
    assert first["maker.Channel"]["created"] == 4
    assert first["maker.Format"]["created"] == 5
    assert await _count(db_session, "maker_channel") >= 4

    etsy = (await db_session.execute(
        text("SELECT fee_percent FROM maker_channel WHERE name = 'Etsy'")
    )).scalar()
    assert float(etsy) == 6.5

    chan_before = await _count(db_session, "maker_channel")

    second = await seed_pack(db_session, registry, "maker")
    await db_session.flush()
    assert second["maker.Channel"]["created"] == 0
    assert second["maker.Channel"]["skipped"] == 4
    assert await _count(db_session, "maker_channel") == chan_before
    assert second["maker.Format"]["created"] == 0
    assert second["maker.Format"]["skipped"] == 5


@pytest.mark.asyncio
async def test_seed_pack_missing_file_is_noop(db_session, tmp_path) -> None:
    registry = build_registry()
    # tmp_path has no <pack>/seeds/defaults.yaml → returns {} without error.
    result = await seed_pack(db_session, registry, "maker", planks_dir=tmp_path)
    assert result == {}


@pytest.mark.asyncio
async def test_seed_pack_unknown_blueprint_raises(db_session, tmp_path) -> None:
    registry = build_registry()
    seeds = tmp_path / "fakepack" / "seeds"
    seeds.mkdir(parents=True)
    (seeds / "defaults.yaml").write_text("nonexistent.Entity:\n  - name: x\n")
    with pytest.raises(ValueError):
        await seed_pack(db_session, registry, "fakepack", planks_dir=tmp_path)
