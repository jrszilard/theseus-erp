import uuid

import pytest
from sqlalchemy import text

from theseus.bootstrap import build_registry
from theseus.keel.entities.writer import (
    find_existing_by_unique,
    insert_entity,
)


@pytest.mark.asyncio
async def test_insert_entity_writes_row_and_is_findable(db_session) -> None:
    registry = build_registry()
    bp = registry.get("maker.Channel")
    assert bp is not None

    name = f"Test-{uuid.uuid4().hex[:8]}"
    row = await insert_entity(db_session, bp, {"name": name, "fee_percent": 5, "fee_fixed": 0.3})
    assert row["name"] == name
    assert "id" in row

    found = await find_existing_by_unique(db_session, bp, {"name": name})
    assert found is not None and found["name"] == name

    missing = await find_existing_by_unique(db_session, bp, {"name": f"Nope-{uuid.uuid4().hex}"})
    assert missing is None

    await db_session.execute(text("DELETE FROM maker_channel WHERE name = :n"), {"n": name})
    await db_session.flush()
