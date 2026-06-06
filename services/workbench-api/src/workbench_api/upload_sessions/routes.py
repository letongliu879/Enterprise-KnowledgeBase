"""Upload session routes."""

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, require_role, CurrentUser
from ..downstream_clients import DocumentServiceClient
from ..errors import not_found, forbidden
from .models import UploadCreateRequest, UploadListResponse
from .repository import UploadSessionRepository
from .service import UploadSessionService

router = APIRouter(prefix="/workbench/uploads")


def _get_service(session: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> UploadSessionService:
    return UploadSessionService(
        UploadSessionRepository(session),
        DocumentServiceClient(),
        actor_id=user.user_id,
        db_session=session,
    )


@router.post("", status_code=201)
async def create_upload(
    req: UploadCreateRequest,
    service: UploadSessionService = Depends(_get_service),
    user: CurrentUser = Depends(require_role("uploader")),
):
    if not user.can_access_collection(req.collection_id):
        raise forbidden("Collection access denied")
    session = await service.create_upload(req.model_dump(), user)
    return session.model_dump()


@router.get("")
def list_uploads(collection_id: str | None = None, status: str | None = None, service: UploadSessionService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    sessions = service.list_uploads(user, collection_id=collection_id, status=status)
    return {"items": [s.model_dump() for s in sessions], "total": len(sessions)}


@router.get("/{upload_id}")
def get_upload(upload_id: str, service: UploadSessionService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    session = service.get_upload(upload_id, user)
    if not session:
        raise not_found("Upload not found")

    # If the upload session is still "uploading" but the task projection
    # has already advanced (e.g. upload succeeded but session wasn't updated),
    # sync the session status from the projection.
    if session.status == "uploading" and session.source_file_id:
        from ..projections.repository import TaskProjectionRepository
        task_repo = TaskProjectionRepository(service._db_session)
        task_proj = task_repo.get_by_upload_id(upload_id)
        if task_proj is not None and task_proj.overall_status not in ("uploading",):
            session.status = task_proj.overall_status

    return session.model_dump()


@router.post("/{upload_id}/content")
async def upload_content(
    upload_id: str,
    file: UploadFile = File(...),
    access_scope_json: str | None = Form(None),
    service: UploadSessionService = Depends(_get_service),
    user: CurrentUser = Depends(require_auth),
):
    session_model = service.get_upload(upload_id, user)
    if not session_model:
        raise not_found("Upload not found")
    access_scope: dict | None = None
    if access_scope_json:
        try:
            parsed = json.loads(access_scope_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="access_scope_json invalid") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="access_scope_json must be an object")
        access_scope = parsed
    content = await file.read()
    updated = await service.upload_content(
        upload_id=upload_id,
        user=user,
        collection_id=session_model.collection_id,
        filename=file.filename or session_model.filename,
        mime_type=file.content_type or session_model.mime_type or "application/octet-stream",
        content_bytes=content,
        access_scope_json=access_scope,
    )
    return updated.model_dump()


@router.delete("/{upload_id}", status_code=204)
def delete_upload(upload_id: str, service: UploadSessionService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    if not service.delete_upload(upload_id, user):
        raise not_found("Upload not found")
