"""Task projection routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..downstream_clients import IntakeClient, ApprovalClient, IndexingClient
from ..errors import not_found
from ..upload_sessions.repository import UploadSessionRepository
from .service import TaskProjectionService

router = APIRouter(prefix="/workbench/tasks")


def _get_service(
    session: Session = Depends(get_db),
    intake_client: IntakeClient = Depends(IntakeClient),
    approval_client: ApprovalClient = Depends(ApprovalClient),
    indexing_client: IndexingClient = Depends(IndexingClient),
) -> TaskProjectionService:
    return TaskProjectionService(
        UploadSessionRepository(session),
        intake_client,
        approval_client,
        indexing_client,
    )


@router.get("")
async def list_tasks(
    collection_id: str | None = None,
    status: str | None = None,
    service: TaskProjectionService = Depends(_get_service),
    user: CurrentUser = Depends(require_auth),
):
    tasks = await service.list_tasks(user, collection_id=collection_id, status=status)
    return {"items": [t.model_dump() for t in tasks], "total": len(tasks)}


@router.get("/{upload_id}")
async def get_task(
    upload_id: str,
    service: TaskProjectionService = Depends(_get_service),
    user: CurrentUser = Depends(require_auth),
):
    task = await service.get_task(upload_id, user)
    if not task:
        raise not_found("Task not found")
    return task.model_dump()
