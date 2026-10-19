import hashlib
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile

from app.config import Settings, get_settings
from app.controllers.ratelimit import limit_upload
from app.deps import catalog_cache, get_ingestion, get_vector_store
from app.loaders.extract import SUPPORTED
from app.repositories.vector_store import DuplicateDocumentError
from app.security.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


def _ingest_and_refresh(ingestion, user_id: str, document_id: str, name: str, data: bytes) -> None:
    try:
        ingestion.ingest(document_id, name, data)
    finally:
        catalog_cache.invalidate(user_id)


@router.post("", status_code=202)
async def upload_document(
    file: UploadFile,
    background: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    _rate: None = Depends(limit_upload),
    store=Depends(get_vector_store),
    ingestion=Depends(get_ingestion),
    settings: Settings = Depends(get_settings),
) -> dict:
    name = Path(file.filename or "").name
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED:
        raise HTTPException(415, f"Formato no soportado. Usa: {', '.join(sorted(SUPPORTED))}")
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"El archivo supera {settings.max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "El archivo está vacío")
    if settings.max_docs_per_user > 0 and store.count_user_documents(user.id) >= settings.max_docs_per_user:
        raise HTTPException(409, f"Alcanzaste el límite de {settings.max_docs_per_user} documentos. Elimina alguno para subir otro.")
    content_hash = hashlib.sha256(data).hexdigest()
    duplicate_msg = "Ya subiste un documento con el mismo contenido: {}"
    existing = store.find_by_hash(user.id, content_hash)
    if existing:
        raise HTTPException(409, duplicate_msg.format(existing))
    try:
        document_id = store.create_document(user.id, name, ext.lstrip("."), content_hash)
    except DuplicateDocumentError:
        raise HTTPException(409, duplicate_msg.format(name))
    catalog_cache.invalidate(user.id)
    background.add_task(_ingest_and_refresh, ingestion, user.id, document_id, name, data)
    return {"id": document_id, "name": name, "status": "processing"}


@router.get("")
def list_documents(user: CurrentUser = Depends(get_current_user), store=Depends(get_vector_store)) -> list[dict]:
    return [asdict(d) for d in store.list_documents(user.id)]


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    store=Depends(get_vector_store),
) -> Response:
    if not store.delete_document(str(document_id), user.id):
        raise HTTPException(404, "Documento no encontrado")
    catalog_cache.invalidate(user.id)
    return Response(status_code=204)
