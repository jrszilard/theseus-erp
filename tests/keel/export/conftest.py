import uuid

import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture
async def export_seed(db_session):
    """One design row — enough for the exporter test (the asset is uploaded in the test body)."""
    design_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO maker_design (id, title, slug, status) "
            "VALUES (:i, 'Loon on Blue Lake', :slug, 'released')"
        ),
        {"i": design_id, "slug": f"loon-export-{design_id.hex[:8]}"},
    )
    await db_session.flush()
    return {"design_id": str(design_id)}
