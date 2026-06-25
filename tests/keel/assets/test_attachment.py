import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from theseus.database import Base
from theseus.keel.assets.attachment import (
    FileFieldError,
    attach_asset,
    detach_asset,
    resolve_file_field,
)
from theseus.keel.assets.service import AssetService
from theseus.keel.assets.storage import LocalStorageBackend
from theseus.keel.blueprint_engine.models import Blueprint, BlueprintField, FieldType
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.schema_engine.generator import SchemaGenerator


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def attach_setup(test_engine):
    """One synthetic Blueprint (single-FK `cover` + junction `attachments`) with its
    tables created once on the shared engine. Proves the primitive is field-agnostic."""
    bp = Blueprint(
        plank="exp", entity="Attdoc", version=1, description="custom",
        fields={
            "title": BlueprintField(type=FieldType.STRING, required=True),
            "cover": BlueprintField(type=FieldType.FILE),                     # single → FK
            "attachments": BlueprintField(type=FieldType.FILE, multiple=True),  # → junction
        },
    )
    registry = BlueprintRegistry()
    registry.register(bp)
    SchemaGenerator(metadata=Base.metadata).generate_table(bp)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)
    return registry


async def _new_doc(db_session):
    eid = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO exp_attdoc (id, title) VALUES (:i, 'x')"), {"i": str(eid)}
    )
    return eid


async def _upload(db_session, tmp_path, name):
    svc = AssetService(session=db_session, storage=LocalStorageBackend(root=str(tmp_path)))
    return await svc.upload(filename=name, content_type="image/png", data=b"\x89PNG", kind="x")


@pytest.mark.asyncio
async def test_attach_junction_appends_with_sort_order(attach_setup, db_session, tmp_path):
    eid = await _new_doc(db_session)
    a1 = await _upload(db_session, tmp_path, "a.png")
    a2 = await _upload(db_session, tmp_path, "b.png")
    await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "attachments", a1.id)
    await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "attachments", a2.id)
    rows = (await db_session.execute(text(
        "SELECT asset_id, sort_order FROM exp_attdoc_attachments "
        "WHERE exp_attdoc_id = :e ORDER BY sort_order"), {"e": str(eid)})).mappings().all()
    assert [r["sort_order"] for r in rows] == [0, 1]
    assert {str(r["asset_id"]) for r in rows} == {str(a1.id), str(a2.id)}


@pytest.mark.asyncio
async def test_attach_single_fk_sets_then_replaces(attach_setup, db_session, tmp_path):
    eid = await _new_doc(db_session)
    a1 = await _upload(db_session, tmp_path, "c1.png")
    a2 = await _upload(db_session, tmp_path, "c2.png")
    await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "cover", a1.id)
    got = (await db_session.execute(text(
        "SELECT cover_asset_id FROM exp_attdoc WHERE id = :e"), {"e": str(eid)})).scalar()
    assert str(got) == str(a1.id)
    await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "cover", a2.id)
    got = (await db_session.execute(text(
        "SELECT cover_asset_id FROM exp_attdoc WHERE id = :e"), {"e": str(eid)})).scalar()
    assert str(got) == str(a2.id)


@pytest.mark.asyncio
async def test_attach_duplicate_link_is_noop(attach_setup, db_session, tmp_path):
    eid = await _new_doc(db_session)
    a1 = await _upload(db_session, tmp_path, "d.png")
    await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "attachments", a1.id)
    await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "attachments", a1.id)
    count = (await db_session.execute(text(
        "SELECT COUNT(*) FROM exp_attdoc_attachments WHERE exp_attdoc_id = :e"),
        {"e": str(eid)})).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_detach_junction_removes_link_keeps_asset(attach_setup, db_session, tmp_path):
    eid = await _new_doc(db_session)
    a1 = await _upload(db_session, tmp_path, "e.png")
    await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "attachments", a1.id)
    await detach_asset(db_session, attach_setup, "exp.Attdoc", eid, "attachments", a1.id)
    count = (await db_session.execute(text(
        "SELECT COUNT(*) FROM exp_attdoc_attachments WHERE exp_attdoc_id = :e"),
        {"e": str(eid)})).scalar()
    assert count == 0
    still = (await db_session.execute(text(
        "SELECT 1 FROM assets WHERE id = :a"), {"a": str(a1.id)})).scalar()
    assert still == 1   # detach-only: asset row survives


@pytest.mark.asyncio
async def test_detach_single_fk_nulls_keeps_asset(attach_setup, db_session, tmp_path):
    eid = await _new_doc(db_session)
    a1 = await _upload(db_session, tmp_path, "g.png")
    await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "cover", a1.id)
    await detach_asset(db_session, attach_setup, "exp.Attdoc", eid, "cover", a1.id)
    got = (await db_session.execute(text(
        "SELECT cover_asset_id FROM exp_attdoc WHERE id = :e"), {"e": str(eid)})).scalar()
    assert got is None
    still = (await db_session.execute(text(
        "SELECT 1 FROM assets WHERE id = :a"), {"a": str(a1.id)})).scalar()
    assert still == 1


@pytest.mark.asyncio
async def test_non_file_field_raises_and_writes_nothing(attach_setup, db_session, tmp_path):
    eid = await _new_doc(db_session)
    a1 = await _upload(db_session, tmp_path, "h.png")
    with pytest.raises(FileFieldError):
        resolve_file_field(attach_setup.get("exp.Attdoc"), "title")   # STRING, not FILE
    with pytest.raises(FileFieldError):
        await attach_asset(db_session, attach_setup, "exp.Attdoc", eid, "nope", a1.id)
    count = (await db_session.execute(text(
        "SELECT COUNT(*) FROM exp_attdoc_attachments WHERE exp_attdoc_id = :e"),
        {"e": str(eid)})).scalar()
    assert count == 0
