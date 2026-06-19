import uuid

import pytest
from sqlalchemy import text

from theseus.database import Base
from theseus.keel.assets.service import AssetService
from theseus.keel.assets.storage import LocalStorageBackend
from theseus.keel.blueprint_engine.models import (
    Blueprint,
    BlueprintField,
    FieldType,
    UIHints,
)
from theseus.keel.blueprint_engine.registry import BlueprintRegistry
from theseus.keel.schema_engine.generator import SchemaGenerator
from theseus.web.read_models import file_groups_for_entity, icon_for


def test_icon_for_is_content_type_derived():
    assert icon_for("application/pdf") == "📄"
    assert icon_for("image/svg+xml") == "📐"
    assert icon_for("image/png") == "🖼"
    assert icon_for("model/3mf") == "📦"
    assert icon_for("application/octet-stream") == "📎"


@pytest.mark.asyncio
async def test_file_groups_for_custom_blueprint_field(test_engine, db_session, tmp_path):
    """Proves the path is Blueprint-driven: custom (non-maker) file fields render —
    both a multiple-file junction field and a single-file FK field — using
    ui.label/ui.icon when present."""
    bp = Blueprint(
        plank="exp", entity="Doc", version=1, description="custom",
        fields={
            "title": BlueprintField(type=FieldType.STRING, required=True),
            "cover": BlueprintField(type=FieldType.FILE),  # single-file → FK column
            "attachments": BlueprintField(
                type=FieldType.FILE, multiple=True,
                ui=UIHints(label="Attachments", icon="📎"),
            ),
        },
    )
    registry = BlueprintRegistry()
    registry.register(bp)

    # Create the synthetic entity's tables on the shared test engine (FKs to `assets`
    # resolve because SchemaGenerator and the asset models share Base.metadata).
    gen = SchemaGenerator(metadata=Base.metadata)
    gen.generate_table(bp)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    svc = AssetService(session=db_session, storage=LocalStorageBackend(root=str(tmp_path)))
    cover_rec = await svc.upload(filename="hero.png", content_type="image/png",
                                 data=b"\x89PNG", kind="cover")
    att_rec = await svc.upload(filename="loon.svg", content_type="image/svg+xml",
                               data=b"<svg/>", kind="cut-file")

    eid = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO exp_doc (id, title, cover_asset_id) VALUES (:i, :t, :c)"),
        {"i": str(eid), "t": "Hello", "c": str(cover_rec.id)},
    )
    await db_session.execute(
        text("INSERT INTO exp_doc_attachments (id, exp_doc_id, asset_id, sort_order) "
             "VALUES (:j, :e, :a, 0)"),
        {"j": str(uuid.uuid4()), "e": str(eid), "a": str(att_rec.id)},
    )
    await db_session.flush()

    groups = {g["field_name"]: g for g in
              await file_groups_for_entity(db_session, registry, "exp.Doc", eid)}
    # single-file FK field (titlecased fallback label, no ui)
    assert groups["cover"]["label"] == "Cover"
    assert groups["cover"]["files"][0]["filename"] == "hero.png"
    assert groups["cover"]["files"][0]["previewable"] is True   # png is inline
    # multiple-file junction field (ui.label/ui.icon honored)
    att = groups["attachments"]
    assert att["label"] == "Attachments"
    assert att["group_icon"] == "📎"
    assert att["files"][0]["filename"] == "loon.svg"
    assert att["files"][0]["url"] == f"/api/v1/assets/raw/{att_rec.versions[0].storage_key}"
    assert att["files"][0]["icon"] == "📐"               # content-type-derived
    assert att["files"][0]["previewable"] is False       # svg never inline


@pytest.mark.asyncio
async def test_file_groups_label_falls_back_to_titlecased_field_name(
    test_engine, db_session, tmp_path
):
    bp = Blueprint(
        plank="exp", entity="Doc2", version=1, description="custom",
        fields={
            "title": BlueprintField(type=FieldType.STRING, required=True),
            "raw_scans": BlueprintField(type=FieldType.FILE, multiple=True),  # no ui
        },
    )
    registry = BlueprintRegistry()
    registry.register(bp)
    gen = SchemaGenerator(metadata=Base.metadata)
    gen.generate_table(bp)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    eid = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO exp_doc2 (id, title) VALUES (:i, :t)"),
        {"i": str(eid), "t": "x"},
    )
    svc = AssetService(session=db_session, storage=LocalStorageBackend(root=str(tmp_path)))
    rec = await svc.upload(filename="s.png", content_type="image/png", data=b"\x89PNG",
                           kind="scan")
    await db_session.execute(
        text("INSERT INTO exp_doc2_raw_scans (id, exp_doc2_id, asset_id, sort_order) "
             "VALUES (:j, :e, :a, 0)"),
        {"j": str(uuid.uuid4()), "e": str(eid), "a": str(rec.id)},
    )
    await db_session.flush()

    groups = await file_groups_for_entity(db_session, registry, "exp.Doc2", eid)
    assert groups[0]["label"] == "Raw Scans"   # titlecased fallback
    assert groups[0]["group_icon"] is None
    assert groups[0]["files"][0]["previewable"] is True  # png is inline


@pytest.mark.asyncio
async def test_get_design_detail_attaches_file_groups(db_session, maker_seed, tmp_path):
    from theseus.web import read_models

    svc = AssetService(session=db_session, storage=LocalStorageBackend(root=str(tmp_path)))
    art = await svc.upload(filename="loon.png", content_type="image/png",
                           data=b"\x89PNG", kind="art")
    mock = await svc.upload(filename="shot.jpg", content_type="image/jpeg",
                            data=b"\xff\xd8", kind="mockup")
    await db_session.execute(
        text("INSERT INTO maker_design_source_art (id, maker_design_id, asset_id, sort_order) "
             "VALUES (:j, :e, :a, 0)"),
        {"j": str(uuid.uuid4()), "e": maker_seed["design_id"], "a": str(art.id)},
    )
    await db_session.execute(
        text(
            "INSERT INTO maker_product_version_mockups "
            "(id, maker_product_version_id, asset_id, sort_order) "
            "VALUES (:j, :e, :a, 0)"
        ),
        {"j": str(uuid.uuid4()), "e": maker_seed["version_id"], "a": str(mock.id)},
    )
    await db_session.flush()

    detail = await read_models.get_design_detail(db_session, uuid.UUID(maker_seed["design_id"]))
    design_files = {f["filename"] for g in detail["file_groups"] for f in g["files"]}
    assert "loon.png" in design_files

    seeded_version = next(
        v for p in detail["products"] for v in p["versions"]
        if v["id"] == maker_seed["version_id"]
    )
    version_files = {f["filename"] for g in seeded_version["file_groups"] for f in g["files"]}
    assert "shot.jpg" in version_files
    # Per-version isolation: a different version carries no mockup it wasn't given.
    assert all(
        "shot.jpg" not in {f["filename"] for g in v["file_groups"] for f in g["files"]}
        for p in detail["products"] for v in p["versions"]
        if v["id"] != maker_seed["version_id"]
    )


@pytest.mark.asyncio
async def test_maker_pack_ui_hints_drive_group_labels_and_icons(db_session, maker_seed, tmp_path):
    from theseus.web import read_models

    svc = AssetService(session=db_session, storage=LocalStorageBackend(root=str(tmp_path)))
    art = await svc.upload(filename="loon.png", content_type="image/png",
                           data=b"\x89PNG", kind="art")
    await db_session.execute(
        text("INSERT INTO maker_design_source_art (id, maker_design_id, asset_id, sort_order) "
             "VALUES (:j, :e, :a, 0)"),
        {"j": str(uuid.uuid4()), "e": maker_seed["design_id"], "a": str(art.id)},
    )
    await db_session.flush()

    detail = await read_models.get_design_detail(db_session, uuid.UUID(maker_seed["design_id"]))
    source_art = next(g for g in detail["file_groups"] if g["field_name"] == "source_art")
    assert source_art["label"] == "Source art"
    assert source_art["group_icon"] == "🎨"
