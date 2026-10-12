from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile

from app.config import Settings, get_settings
from app.deps import get_ingestion, get_vector_store
from app.loaders.extract import SUPPORTED
from app.security.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=202)
async def upload_document(
    file: UploadFile,
    background: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
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
    document_id = store.create_document(user.id, name, ext.lstrip("."))
    background.add_task(ingestion.ingest, document_id, name, data)
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
    return Response(status_code=204)
