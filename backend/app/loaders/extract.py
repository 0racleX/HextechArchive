import csv
import io
import json
from pathlib import Path

from docx import Document
from pypdf import PdfReader

SUPPORTED = {".pdf", ".txt", ".md", ".csv", ".docx", ".json"}


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == ".docx":
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if ext == ".csv":
        rows = csv.DictReader(io.StringIO(data.decode("utf-8", errors="replace")))
        return "\n".join("; ".join(f"{k}: {v}" for k, v in row.items()) for row in rows)
    if ext == ".json":
        return json.dumps(json.loads(data.decode("utf-8")), ensure_ascii=False, indent=2)
    raise ValueError(f"Formato no soportado: {ext or 'sin extensión'}")
