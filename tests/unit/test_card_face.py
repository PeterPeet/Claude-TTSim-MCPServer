"""Unit tests for cutting a card face out of TTSim's cached face sheet (REQ-OBJ-08)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from ttsim_mcp.table import (
    ImageNotCachedError,
    cached_image_path,
    clean_pdf_text,
    crop_card,
    grid_cell,
    pdf_pages_text,
)

SHEET_URL = "https://steamusercontent-a.akamaihd.net/ugc/1234567890123456789/0123456789ABCDEF0123456789ABCDEF01234567/"
# TTSim names a cached file after its URL with only letters and digits left (spike 2026-10-05).
CACHED_NAME = (
    "httpssteamusercontentaakamaihdnetugc12345678901234567890123456789ABCDEF0123456789ABCDEF01234567"
)


def test_req_obj_08_cache_name_drops_punctuation(tmp_path: Path) -> None:
    (tmp_path / f"{CACHED_NAME}.png").write_bytes(b"")
    assert cached_image_path(SHEET_URL, [tmp_path]) == tmp_path / f"{CACHED_NAME}.png"


def test_req_obj_08_cache_finds_jpg_in_later_directory(tmp_path: Path) -> None:
    first, second = tmp_path / "Images", tmp_path / "Images Raw"
    first.mkdir()
    second.mkdir()
    (second / f"{CACHED_NAME}.jpg").write_bytes(b"")
    assert cached_image_path(f"  {SHEET_URL}  ", [first, second]) == second / f"{CACHED_NAME}.jpg"


def test_req_obj_08_not_cached_is_readable_error(tmp_path: Path) -> None:
    with pytest.raises(ImageNotCachedError, match="not in TTSim's image/PDF cache"):
        cached_image_path(SHEET_URL, [tmp_path])


@pytest.mark.parametrize(
    ("index", "cell"),
    [
        (0, (0, 0)),  # top left
        (1, (1, 0)),
        (3, (3, 0)),  # end of the first row of a 4-wide sheet
        (4, (0, 1)),
        (11, (3, 2)),  # last cell of a 4 x 3 sheet
    ],
)
def test_req_obj_08_grid_cell_runs_row_by_row(index: int, cell: tuple[int, int]) -> None:
    assert grid_cell(index, columns=4, rows=3) == cell


def test_req_obj_08_grid_cell_outside_sheet_is_error() -> None:
    with pytest.raises(ValueError, match="outside"):
        grid_cell(12, columns=4, rows=3)


def sheet(columns: int, rows: int, cell: tuple[int, int]) -> Image.Image:
    """A sheet of 30 x 40 px cards, each filled with a colour that encodes its position."""
    img = Image.new("RGB", (columns * cell[0], rows * cell[1]))
    for r in range(rows):
        for c in range(columns):
            img.paste((c * 50, r * 50, 200), (c * cell[0], r * cell[1], (c + 1) * cell[0], (r + 1) * cell[1]))
    return img


def test_req_obj_08_crop_card_returns_only_that_card(tmp_path: Path) -> None:
    path = tmp_path / "sheet.png"
    sheet(4, 3, (30, 40)).save(path)
    card = Image.open(io.BytesIO(crop_card(path, index=6, columns=4, rows=3)))
    assert card.format == "JPEG"
    assert card.size == (30, 40)
    # Column 2, row 1 (JPEG may shift colours slightly).
    assert all(abs(a - b) <= 8 for a, b in zip(card.getpixel((15, 20)), (100, 50, 200), strict=True))


def test_req_obj_08_crop_whole_image_when_one_cell(tmp_path: Path) -> None:
    path = tmp_path / "tile.jpg"
    sheet(1, 1, (60, 80)).save(path)
    card = Image.open(io.BytesIO(crop_card(path, index=0, columns=1, rows=1)))
    assert card.size == (60, 80)


def test_req_obj_08_large_image_is_scaled_down_keeping_shape(tmp_path: Path) -> None:
    # Some mods use a single large image per card, e.g. 3815 x 2528 (spike 2026-10-05).
    path = tmp_path / "large.png"
    Image.new("RGB", (3815, 2528), (255, 255, 255)).save(path)
    card = Image.open(io.BytesIO(crop_card(path, index=0, columns=1, rows=1, max_side=2000)))
    assert card.size == (2000, 1325)


# Custom PDF objects


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        # Glyph name forms pypdf produced for real PDFs (spike 2026-10-05).
        ("H/e.sc/r.sc/o.sc, K/n.sc/i.sc/g.sc/h.sc/t.sc", "Hero, Knight"),
        ("/T_his army", "This army"),
        ("A /t_t a c k s", "A tt a c k s"),
        ("/u2022.j RULES /u2022.j", "• RULES •"),
        ("FAR/u002D.jREACHING", "FAR-REACHING"),
        ("/uni00A0End/uni00A0of", "\u00a0End\u00a0of"),
        ("3+ | 2 | -", "3+ | 2 | -"),
    ],
)
def test_req_obj_08_pdf_text_glyph_names_are_cleaned(raw: str, clean: str) -> None:
    assert clean_pdf_text(raw) == clean


def make_pdf(path: Path, pages: list[str]) -> None:
    """A minimal PDF with one line of Helvetica text per page."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    kids = []
    for text in pages:
        stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET"
        content_no = len(objects) + 2
        kids.append(f"{len(objects) + 1} 0 R")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents {content_no} 0 R "
            f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


def test_req_obj_08_pdf_pages_text(tmp_path: Path) -> None:
    path = tmp_path / "rules.pdf"
    make_pdf(path, ["PAGE ONE 5 inch", "PAGE TWO 12 inch"])
    assert pdf_pages_text(path) == ["PAGE ONE 5 inch", "PAGE TWO 12 inch"]
