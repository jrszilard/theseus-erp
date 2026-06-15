import csv
import io
import zipfile

import pytest

from theseus.bootstrap import build_registry
from theseus.keel.assets.service import AssetService
from theseus.keel.assets.storage import LocalStorageBackend
from theseus.keel.export.exporter import export_all


@pytest.mark.asyncio
async def test_export_writes_csv_and_assets(db_session, tmp_path, export_seed) -> None:
    storage = LocalStorageBackend(root=str(tmp_path / "assets"))
    svc = AssetService(session=db_session, storage=storage)
    await svc.upload(filename="hello.txt", content_type="text/plain",
                     data=b"hello maker", kind="other")
    await db_session.flush()

    out = tmp_path / "export.zip"
    registry = build_registry()
    await export_all(db_session, registry, str(out), storage=storage)

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "maker_design.csv" in names
        assert any(n.startswith("assets/") for n in names)

        with zf.open("maker_design.csv") as f:
            rows = list(csv.reader(io.TextIOWrapper(f, "utf-8")))
        assert "title" in rows[0]
        assert len(rows) >= 2  # header + the seeded 'Loon on Blue Lake' design
