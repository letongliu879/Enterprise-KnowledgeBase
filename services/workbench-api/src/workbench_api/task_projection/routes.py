"""Task projection routes — read from SQL projection only."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..errors import not_found
from ..projections.repository import TaskProjectionRepository

router = APIRouter(prefix="/workbench/tasks")


def _task_proj_to_dict(item) -> dict:
    return {
        "upload_id": item.upload_id,
        "status": item.overall_status,
        "progress_pct": item.progress_pct,
        "source_file_state": item.source_file_state,
        "intake_job_state": item.intake_job_state,
        "parse_snapshot_state": item.parse_snapshot_state,
        "ticket_state": item.ticket_state,
        "published_document_state": item.published_document_state,
        "index_build_state": item.index_build_state,
        "active_index_version": item.active_index_version,
        "filename": item.filename,
        "collection_id": item.collection_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.projection_updated_at.isoformat() if item.projection_updated_at else None,
    }


@router.get("")
async def list_tasks(
    collection_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    repo = TaskProjectionRepository(db)
    items, total = repo.list(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        collection_id=collection_id,
        status=status,
        offset=0,
        limit=1000,
    )
    return {"items": [_task_proj_to_dict(i) for i in items], "total": total}


@router.get("/{upload_id}")
async def get_task(
    upload_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    repo = TaskProjectionRepository(db)
    proj = repo.get_by_upload_id(upload_id)
    if proj is None:
        raise not_found("Task not found")
    if proj.tenant_id != user.tenant_id or proj.user_id != user.user_id:
        raise not_found("Task not found")
    return _task_proj_to_dict(proj)
