import io

import pytest
from docx import Document
from pypdf import PdfWriter

from app.loaders.chunking import split_text
from app.loaders.extract import extract_text


def test_txt_and_md():
    assert extract_text("a.txt", "Hola Runeterra".encode()) == "Hola Runeterra"
    assert extract_text("a.md", b"# Titulo") == "# Titulo"


def test_csv_becomes_readable_lines():
    data = "campeon,rol\nAhri,Mago\nGaren,Luchador\n".encode()
    text = extract_text("c.csv", data)
    assert "campeon: Ahri; rol: Mago" in text
    assert "campeon: Garen; rol: Luchador" in text


def test_json_keeps_unicode():
    text = extract_text("d.json", '{"región": "Piltóver"}'.encode())
    assert "Piltóver" in text


def test_docx():
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Demacia es un reino.")
    doc.save(buf)
    assert "Demacia es un reino." in extract_text("r.docx", buf.getvalue())


def test_blank_pdf_has_no_text():
    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buf)
    assert extract_text("blank.pdf", buf.getvalue()).strip() == ""


def test_unsupported_extension():
    with pytest.raises(ValueError):
        extract_text("x.exe", b"data")


def test_split_text_overlaps_and_skips_blank():
    text = "palabra " * 400
    chunks = split_text(text, chunk_size=200, overlap=40)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)
    assert all(len(c) <= 200 for c in chunks)
