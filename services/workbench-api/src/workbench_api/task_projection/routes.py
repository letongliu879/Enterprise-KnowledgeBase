"""Task projection routes — read from SQL projection, with auto-recovery
for projections stuck in terminal upload states due to missed events."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..downstream_clients import IntakeClient
from ..downstream_clients.errors import DownstreamError
from ..errors import not_found
from ..projections.projector import ProjectionProjector
from ..projections.repository import TaskProjectionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench/tasks")

# Tasks stuck in these states for longer than this are auto-recovered on read.
_STUCK_STATUSES = frozenset({"uploading", "uploaded", "ready"})
_AUTO_RECOVER_STALE_SECONDS = 30


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
    threshold = datetime.now(timezone.utc) - timedelta(seconds=_AUTO_RECOVER_STALE_SECONDS)
    updated = proj.projection_updated_at
    if updated is not None and updated > threshold:
        return False
    return True


async def _try_recover(db: Session, proj) -> bool:
    """Query downstream services for fresh state and fix the projection."""
    intake_client = IntakeClient()
    now = datetime.now(timezone.utc)

    source_file_state = proj.source_file_state
    intake_job_id = proj.intake_job_id
    intake_job_state = proj.intake_job_state

    # Query document-service for source file state.
    try:
        sf = await intake_client.get_source_file(proj.source_file_id)
        source_file_state = sf.get("state") or source_file_state
        if not intake_job_id:
            intake_job_id = sf.get("claimed_by") or sf.get("intake_job_id")
    except DownstreamError:
        logger.debug("auto-recovery: source file fetch failed for %s", proj.upload_id)
        proj.projection_updated_at = datetime.now(timezone.utc)
        db.flush()
        return False

    # Query ingestion-worker for intake job state.
    if intake_job_id:
        try:
            job = await intake_client.get_intake_job(intake_job_id)
            intake_job_state = job.get("state") or intake_job_state
        except DownstreamError:
            logger.debug("auto-recovery: intake job fetch failed for %s", proj.upload_id)

    # Apply everything in one event.
    projector = ProjectionProjector(db)
    event = {
        "event_id": f"autorec_{proj.upload_id}_{uuid.uuid4().hex[:8]}",
        "event_type": "AUTO_RECOVERY",
        "tenant_id": proj.tenant_id,
        "collection_id": proj.collection_id,
        "aggregate_type": "task",
        "aggregate_id": proj.upload_id,
        "aggregate_version": proj.version + 1,
        "occurred_at": now,
        "payload": {
            "projection_id": proj.upload_id,
            "tenant_id": proj.tenant_id,
            "user_id": proj.user_id,
            "collection_id": proj.collection_id,
            "upload_id": proj.upload_id,
            "filename": proj.filename,
            "mime_type": proj.mime_type,
            "size_bytes": proj.size_bytes,
            "source_file_id": proj.source_file_id,
            "intake_job_id": intake_job_id,
            "source_file_state": source_file_state,
            "intake_job_state": intake_job_state,
        },
        "trace_id": proj.upload_id,
    }
    result = projector.record_and_apply(event)
    if result["applied"]:
        logger.info("auto-recovery: fixed %s", proj.upload_id)
    return result["applied"]


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

    # Auto-recover stale projections (max 3 per call).
    stale = [i for i in items if _needs_recovery(i)]
    for proj in stale[:3]:
        await _try_recover(db, proj)

    if stale:
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

    if _needs_recovery(proj):
        await _try_recover(db, proj)
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

    ok = await _try_recover(db, proj)
    updated = repo.get_by_upload_id(upload_id)
    return {
        "recovered": ok,
        "previous_status": proj.overall_status,
        "current_status": updated.overall_status if updated else proj.overall_status,
    }
