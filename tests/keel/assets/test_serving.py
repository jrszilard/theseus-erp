import pytest

from theseus.keel.assets.serving import disposition_for, is_previewable


@pytest.mark.parametrize("ct", ["image/png", "image/jpeg", "image/gif", "image/webp",
                                "IMAGE/PNG", "image/png; charset=binary"])
def test_raster_types_are_previewable(ct):
    assert is_previewable(ct) is True


@pytest.mark.parametrize("ct", ["image/svg+xml", "application/pdf",
                                "application/octet-stream", "text/html", "model/3mf"])
def test_non_raster_types_are_not_previewable(ct):
    assert is_previewable(ct) is False


def test_disposition_inline_for_raster():
    assert disposition_for("image/png", "art.png") == "inline"


def test_disposition_attachment_for_svg_and_pdf():
    assert disposition_for("image/svg+xml", "loon_cut.svg") == 'attachment; filename="loon_cut.svg"'
    assert disposition_for("application/pdf", "print.pdf") == 'attachment; filename="print.pdf"'


def test_disposition_strips_quotes_from_filename():
    assert disposition_for("application/octet-stream", 'a"b.bin') == 'attachment; filename="ab.bin"'
