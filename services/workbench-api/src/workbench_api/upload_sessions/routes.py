"""Upload session routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, require_role, CurrentUser
from ..downstream_clients import IntakeClient
from ..errors import not_found, forbidden
from .models import UploadCreateRequest, UploadListResponse
from .repository import UploadSessionRepository
from .service import UploadSessionService

router = APIRouter(prefix="/workbench/uploads")


def _get_service(session: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> UploadSessionService:
    return UploadSessionService(
        UploadSessionRepository(session),
        IntakeClient(),
        actor_id=user.user_id,
    )


@router.post("", status_code=201)
async def create_upload(req: UploadCreateRequest, service: UploadSessionService = Depends(_get_service), user: CurrentUser = Depends(require_role("uploader"))):
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
    return session.model_dump()


@router.delete("/{upload_id}", status_code=204)
def delete_upload(upload_id: str, service: UploadSessionService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    if not service.delete_upload(upload_id, user):
        raise not_found("Upload not found")
