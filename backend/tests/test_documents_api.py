import io

import pytest
from pypdf import PdfWriter

from app.deps import get_ingestion, get_vector_store
from app.main import app
from app.services.ingestion import IngestionService
from tests.conftest import make_token
from tests.fakes import FakeEmbedder, FakeStore


@pytest.fixture
def store():
    s = FakeStore()
    app.dependency_overrides[get_vector_store] = lambda: s
    app.dependency_overrides[get_ingestion] = lambda: IngestionService(s, FakeEmbedder())
    return s


def headers(user="user-a"):
    return {"Authorization": f"Bearer {make_token(sub=user)}"}


def upload(client, name, data, user="user-a"):
    return client.post("/documents", files={"file": (name, data)}, headers=headers(user))


def test_endpoints_require_auth(client):
    assert client.get("/documents").status_code == 401
    assert client.post("/documents", files={"file": ("a.txt", b"x")}).status_code == 401
    assert client.delete("/documents/3f2b1c1e-0000-4000-8000-000000000000").status_code == 401


def test_upload_processes_and_lists(client, store):
    r = upload(client, "jinx.txt", ("Jinx es de Zaun. " * 50).encode())
    assert r.status_code == 202
    doc_id = r.json()["id"]
    listed = client.get("/documents", headers=headers()).json()
    item = next(d for d in listed if d["id"] == doc_id)
    assert item["status"] == "ready" and item["name"] == "jinx.txt"


def test_unsupported_type_is_415(client, store):
    assert upload(client, "virus.exe", b"MZ").status_code == 415
    assert store.docs == {}


def test_empty_file_is_400(client, store):
    assert upload(client, "vacio.txt", b"").status_code == 400
    assert store.docs == {}


def test_oversized_file_is_413(client, store):
    big = b"a" * (10 * 1024 * 1024 + 1)
    assert upload(client, "grande.txt", big).status_code == 413
    assert store.docs == {}


def test_blank_pdf_ends_in_error_state(client, store):
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    w.write(buf)
    doc_id = upload(client, "escaneado.pdf", buf.getvalue()).json()["id"]
    item = next(d for d in client.get("/documents", headers=headers()).json() if d["id"] == doc_id)
    assert item["status"] == "error" and "texto" in item["error"].lower()


def test_user_cannot_see_or_delete_foreign_documents(client, store):
    doc_id = upload(client, "a.txt", b"contenido de A", user="user-a").json()["id"]
    assert client.get("/documents", headers=headers("user-b")).json() == []
    assert client.delete(f"/documents/{doc_id}", headers=headers("user-b")).status_code == 404
    assert client.delete(f"/documents/{doc_id}", headers=headers("user-a")).status_code == 204


def test_path_traversal_filename_is_sanitized(client, store):
    r = upload(client, "../../etc/passwd.txt", b"hola mundo")
    assert r.status_code == 202
    assert r.json()["name"] == "passwd.txt"


def test_duplicate_content_same_user_is_409_and_not_reprocessed(client, store):
    assert upload(client, "a.txt", b"mismo contenido").status_code == 202
    r = upload(client, "copia.txt", b"mismo contenido")
    assert r.status_code == 409 and "mismo contenido" in r.json()["detail"] and "a.txt" in r.json()["detail"]
    assert len(store.docs) == 1


def test_duplicate_content_other_user_is_allowed(client, store):
    assert upload(client, "a.txt", b"mismo contenido", user="user-a").status_code == 202
    assert upload(client, "a.txt", b"mismo contenido", user="user-b").status_code == 202


def test_failed_document_can_be_reuploaded(client, store):
    doc_id = upload(client, "a.txt", b"   ").json()["id"]
    assert store.docs[doc_id]["status"] == "error"
    assert upload(client, "a.txt", b"   ").status_code == 202


def test_document_limit_per_user_is_409(client, store):
    from app.config import Settings, get_settings
    from tests.conftest import SECRET
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, supabase_jwt_secret=SECRET, supabase_jwks_url="", max_docs_per_user=2)
    assert upload(client, "1.txt", b"uno").status_code == 202
    assert upload(client, "2.txt", b"dos").status_code == 202
    r = upload(client, "3.txt", b"tres")
    assert r.status_code == 409 and "límite de 2" in r.json()["detail"]
    assert upload(client, "3.txt", b"tres", user="user-b").status_code == 202


def test_upload_rate_limit_returns_429(client, store):
    from app.config import Settings, get_settings
    from tests.conftest import SECRET
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, supabase_jwt_secret=SECRET, supabase_jwks_url="", rate_limit_upload_per_min=2)
    assert upload(client, "1.txt", b"uno").status_code == 202
    assert upload(client, "2.txt", b"dos").status_code == 202
    r = upload(client, "3.txt", b"tres")
    assert r.status_code == 429 and "Demasiadas" in r.json()["detail"]


def test_upload_and_delete_invalidate_catalog_cache(client, store):
    from app.deps import make_catalog
    catalog = make_catalog(store, 30)
    assert catalog("user-a") == []
    doc_id = upload(client, "a.txt", b"contenido de A").json()["id"]
    assert catalog("user-a") == ["a.txt"]
    assert client.delete(f"/documents/{doc_id}", headers=headers()).status_code == 204
    assert catalog("user-a") == []
