"""Task projection routes — read from SQL projection, with auto-recovery
for projections stuck in terminal upload states due to missed events."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from reality_rag_persistence.database import get_session

from ..deps import get_db, require_auth, CurrentUser
from ..downstream_clients import IntakeClient
from ..downstream_clients.errors import DownstreamError
from ..errors import not_found, conflict
from ..projections.projector import ProjectionProjector
from ..projections.repository import TaskProjectionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench/tasks")

# Tasks in these non-terminal states are eligible for read-time recovery if
# their projection is stale. Terminal states are intentionally excluded.
_STUCK_STATUSES = frozenset(
    {
        "uploading",
        "uploaded",
        "ready",
        "parsing",
        "reviewing",
        "approved",
        "publishing",
        "indexing",
    }
)
_AUTO_RECOVER_STALE_SECONDS = 30


@dataclass(frozen=True)
class _RecoveryTarget:
    upload_id: str
    tenant_id: str
    user_id: str
    collection_id: str
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    source_file_id: str
    intake_job_id: str | None
    version: int


def _correct_status(item) -> str:
    """Derive the correct overall_status from individual state fields.

    This is the same logic as _derive_overall_status in projector.py,
    but applied at read time so even projections with stale overall_status
    (written by old buggy code) show the correct status immediately.
    """
    ps = item.published_document_state
    ibs = item.index_build_state
    aiv = item.active_index_version
    ts = item.ticket_state
    ijs = item.intake_job_state
    sfs = item.source_file_state

    if ps == "archived":
        return "archived"
    if ps == "retracted":
        return "retracted"
    if aiv:
        return "published"
    if ibs == "building":
        return "indexing"
    if ps == "publish_succeeded":
        return "published"
    if ts == "approved":
        return "approved"
    if ts == "rejected":
        return "rejected"
    if ts == "pending":
        return "reviewing"
    if ijs == "failed":
        return "failed"
    if ijs in ("created", "conversion_queued", "conversion_running", "parsing", "processing"):
        return "parsing"
    if ijs in ("review_queued", "review_running", "review_succeeded", "approval_requested", "awaiting_approval"):
        return "reviewing"
    if ijs in ("publish_queued", "publish_running"):
        return "publishing"
    if ijs == "published":
        return "published"
    if sfs == "ready":
        return "ready"
    if sfs == "uploaded":
        return "uploaded"
    return item.overall_status or "uploading"


def _task_proj_to_dict(item) -> dict:
    return {
        "upload_id": item.upload_id,
        "status": _correct_status(item),
        "progress_pct": item.progress_pct,
        "source_file_id": item.source_file_id,
        "intake_job_id": item.intake_job_id,
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


def _needs_recovery(proj) -> bool:
    """Check whether a task projection needs recovery (stale or missing data)."""
    if not proj.source_file_id:
        return False
    if _correct_status(proj) not in _STUCK_STATUSES:
        return False
    threshold = datetime.now(timezone.utc) - timedelta(seconds=_AUTO_RECOVER_STALE_SECONDS)
    updated = proj.projection_updated_at.replace(tzinfo=timezone.utc) if proj.projection_updated_at else None
    if updated is not None and updated > threshold:
        return False
    return True


def _to_recovery_target(proj) -> _RecoveryTarget:
    return _RecoveryTarget(
        upload_id=proj.upload_id,
        tenant_id=proj.tenant_id,
        user_id=proj.user_id,
        collection_id=proj.collection_id,
        filename=proj.filename,
        mime_type=proj.mime_type,
        size_bytes=proj.size_bytes,
        source_file_id=proj.source_file_id,
        intake_job_id=proj.intake_job_id,
        version=proj.version,
    )


def _mark_recovery_checked(target: _RecoveryTarget) -> None:
    session = get_session()
    try:
        repo = TaskProjectionRepository(session)
        proj = repo.get_by_upload_id(target.upload_id)
        if proj is not None:
            proj.projection_updated_at = datetime.now(timezone.utc)
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def _try_recover(target: _RecoveryTarget) -> bool:
    """Query downstream services for fresh state and fix the projection."""
    intake_client = IntakeClient()
    now = datetime.now(timezone.utc)

    source_file_state = None
    intake_job_id = target.intake_job_id
    intake_job_state = None

    # Query document-service for source file state.
    try:
        sf = await intake_client.get_source_file(target.source_file_id)
        source_file_state = sf.get("state") or source_file_state
        if not intake_job_id:
            intake_job_id = sf.get("claimed_by") or sf.get("intake_job_id")
    except DownstreamError:
        logger.debug("auto-recovery: source file fetch failed for %s", target.upload_id)
        _mark_recovery_checked(target)
        return False

    # Query ingestion-worker for intake job state.
    if intake_job_id:
        try:
            job = await intake_client.get_intake_job(intake_job_id)
            intake_job_state = job.get("state") or intake_job_state
        except DownstreamError:
            logger.debug("auto-recovery: intake job fetch failed for %s", target.upload_id)

    # Apply everything in one event.
    session = get_session()
    try:
        projector = ProjectionProjector(session)
        event = {
            "event_id": f"autorec_{target.upload_id}_{uuid.uuid4().hex[:8]}",
            "event_type": "AUTO_RECOVERY",
            "tenant_id": target.tenant_id,
            "collection_id": target.collection_id,
            "aggregate_type": "task",
            "aggregate_id": target.upload_id,
            "aggregate_version": target.version + 1,
            "occurred_at": now,
            "payload": {
                "projection_id": target.upload_id,
                "tenant_id": target.tenant_id,
                "user_id": target.user_id,
                "collection_id": target.collection_id,
                "upload_id": target.upload_id,
                "filename": target.filename,
                "mime_type": target.mime_type,
                "size_bytes": target.size_bytes,
                "source_file_id": target.source_file_id,
                "intake_job_id": intake_job_id,
                "source_file_state": source_file_state,
                "intake_job_state": intake_job_state,
            },
            "trace_id": target.upload_id,
        }
        result = projector.record_and_apply(event)
        session.commit()
        if result["applied"]:
            logger.info("auto-recovery: fixed %s", target.upload_id)
        return result["applied"]
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.get("")
async def list_tasks(
    collection_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    repo = TaskProjectionRepository(db)
    items, total = repo.list(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        collection_id=collection_id,
        status=status,
        offset=offset,
        limit=limit,
        order_by=sort_by,
        order_dir=sort_order,
    )

    stale_targets = [_to_recovery_target(i) for i in items if _needs_recovery(i)]
    db.rollback()

    # Auto-recover stale projections (max 3 per call).
    for target in stale_targets[:3]:
        await _try_recover(target)

    if stale_targets:
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

    recovery_target = _to_recovery_target(proj) if _needs_recovery(proj) else None
    db.rollback()

    if recovery_target is not None:
        await _try_recover(recovery_target)
        proj = repo.get_by_upload_id(upload_id)

    return _task_proj_to_dict(proj)


@router.post("/{upload_id}/recover")
async def recover_task(
    upload_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Manually recover a stuck task projection.

    Normally recovery happens automatically on read; this endpoint
    is for cases where you need a synchronous confirmation.
    """
    repo = TaskProjectionRepository(db)
    proj = repo.get_by_upload_id(upload_id)
    if proj is None:
        raise not_found("Task not found")
    if proj.tenant_id != user.tenant_id:
        raise not_found("Task not found")

    if not _needs_recovery(proj) and proj.overall_status not in _STUCK_STATUSES:
        return {
            "recovered": False,
            "reason": f"Task status '{proj.overall_status}' does not need recovery",
        }

    previous_status = proj.overall_status
    recovery_target = _to_recovery_target(proj)
    db.rollback()

    ok = await _try_recover(recovery_target)
    updated = repo.get_by_upload_id(upload_id)
    return {
        "recovered": ok,
        "previous_status": previous_status,
        "current_status": updated.overall_status if updated else previous_status,
    }


@router.post("/{upload_id}/cancel")
async def cancel_task(
    upload_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Cancel a task that is not in a terminal state.

    Validates the task exists, belongs to the current user,
    and is still eligible for cancellation.
    """
    repo = TaskProjectionRepository(db)
    proj = repo.get_by_upload_id(upload_id)
    if proj is None:
        raise not_found("Task not found")
    if proj.tenant_id != user.tenant_id or proj.user_id != user.user_id:
        raise not_found("Task not found")

    terminal_statuses = frozenset({"completed", "cancelled", "failed", "archived", "retracted"})
    if proj.overall_status in terminal_statuses:
        raise conflict(f"Task is already in terminal state '{proj.overall_status}'")

    projector = ProjectionProjector(db)
    event = {
        "event_id": f"cancel_{upload_id}_{uuid.uuid4().hex[:8]}",
        "event_type": "TASK_CANCELLED",
        "tenant_id": proj.tenant_id,
        "collection_id": proj.collection_id,
        "aggregate_type": "task",
        "aggregate_id": upload_id,
        "aggregate_version": proj.version + 1,
        "occurred_at": datetime.now(timezone.utc),
        "payload": {
            "projection_id": upload_id,
            "upload_id": upload_id,
            "user_id": proj.user_id,
            "tenant_id": proj.tenant_id,
            "collection_id": proj.collection_id,
            "overall_status": "cancelled",
        },
        "trace_id": upload_id,
    }
    projector.record_and_apply(event)
    db.commit()

    return {"status": "cancelled", "task_id": upload_id}
