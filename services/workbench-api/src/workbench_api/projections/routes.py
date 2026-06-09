"""Projection read routes — list endpoints query SQL only, no downstream fan-out.

NOTE: /workbench/tasks and /workbench/tickets are currently served by
      task_projection/routes.py and tickets/routes.py respectively.
      This module only provides /workbench/documents to avoid route conflicts.
      When projection writes are fully integrated, migrate the old routes here.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..workspace.service import WorkspaceService
from ..downstream_clients import ApprovalClient, IndexingClient, IntakeClient
from ..chunk_edits.repository import ChunkEditRepository
from .repository import (
    AgentReviewProjectionRepository,
    DocumentProjectionRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)

router = APIRouter()


def _build_workspace_service(session: Session) -> WorkspaceService:
    return WorkspaceService(
        task_repo=TaskProjectionRepository(session),
        ticket_repo=TicketProjectionRepository(session),
        document_repo=DocumentProjectionRepository(session),
        agent_review_repo=AgentReviewProjectionRepository(session),
        chunk_edit_repo=ChunkEditRepository(session),
        intake_client=IntakeClient(),
        approval_client=ApprovalClient(),
        indexing_client=IndexingClient(),
    )


def _document_to_dict(item, *, workspace_service: WorkspaceService | None = None):
    task_proj = None
    ticket_proj = None
    if workspace_service is not None:
        task_proj = workspace_service._resolve_task_projection_for_document(  # noqa: SLF001
            tenant_id=item.tenant_id,
            document_proj=item,
        )
        ticket_proj = workspace_service._resolve_ticket_projection_for_document(  # noqa: SLF001
            tenant_id=item.tenant_id,
            document_proj=item,
            task_proj=task_proj,
        )
    return {
        "doc_id": item.doc_id,
        "tenant_id": item.tenant_id,
        "collection_id": item.collection_id,
        "source_file_id": item.source_file_id,
        "parse_snapshot_id": item.parse_snapshot_id,
        "published_doc_id": item.published_doc_id,
        "upload_id": item.upload_id,
        "filename": item.filename,
        "mime_type": item.mime_type,
        "document_state": item.document_state,
        "publish_state": item.publish_state,
        "active_index_version": item.active_index_version,
        "chunk_count": item.chunk_count,
        "page_count": item.page_count,
        "parser_profile_id": item.parser_profile_id,
        "parser_profile_name": item.parser_profile_name,
        "projection_updated_at": item.projection_updated_at.isoformat() if item.projection_updated_at else None,
        "is_stale": item.is_stale,
        "degraded_reason": item.degraded_reason,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "ticket_id": ticket_proj.ticket_id if ticket_proj is not None else None,
        "ticket_status": ticket_proj.state if ticket_proj is not None else None,
        "task_status": workspace_service._derive_task_status(task_proj) if workspace_service is not None and task_proj is not None else None,  # noqa: SLF001
        "has_source_file": bool(item.source_file_id),
        "has_parse_snapshot": bool(item.parse_snapshot_id),
        "has_active_index": bool(item.active_index_version),
        "latest_updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else item.projection_updated_at.isoformat() if item.projection_updated_at else None
        ),
    }


def _select_task_projection_for_document(item, task_candidates):
    if item.upload_id:
        for candidate in task_candidates:
            if candidate.upload_id == item.upload_id:
                return candidate
    if item.source_file_id:
        for candidate in task_candidates:
            if candidate.source_file_id == item.source_file_id:
                return candidate
    for candidate in task_candidates:
        if candidate.doc_id == item.doc_id:
            return candidate
    return None


def _select_ticket_projection_for_document(item, ticket_candidates):
    if item.doc_id:
        for candidate in ticket_candidates:
            if candidate.doc_id == item.doc_id and candidate.state == "pending":
                return candidate
    if item.source_file_id:
        for candidate in ticket_candidates:
            if candidate.source_file_id == item.source_file_id and candidate.state == "pending":
                return candidate
    if item.doc_id:
        for candidate in ticket_candidates:
            if candidate.doc_id == item.doc_id:
                return candidate
    if item.source_file_id:
        for candidate in ticket_candidates:
            if candidate.source_file_id == item.source_file_id:
                return candidate
    return None


@router.get("/workbench/documents/{doc_id}")
async def get_document(
    doc_id: str,
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Get a single document from SQL projection."""
    repo = DocumentProjectionRepository(session)
    workspace_service = _build_workspace_service(session)
    item = repo.get(doc_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    if not user.can_access_collection(item.collection_id):
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return _document_to_dict(item, workspace_service=workspace_service)


@router.get("/workbench/documents")
async def list_documents(
    collection_id: str | None = None,
    document_state: str | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    order_by: str = Query("projection_updated_at"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """List documents from SQL projection only. No downstream calls."""
    repo = DocumentProjectionRepository(session)
    workspace_service = _build_workspace_service(session)
    collection_ids = None
    if collection_id:
        if not user.can_access_collection(collection_id):
            return {"items": [], "total": 0}
        collection_ids = [collection_id]
    else:
        collection_ids = user.allowed_collections
        if "*" in collection_ids:
            collection_ids = None

    items, total = repo.list(
        tenant_id=user.tenant_id,
        collection_ids=collection_ids,
        document_state=document_state or status,
        offset=offset,
        limit=limit,
        order_by=order_by,
        order_dir=order_dir,
    )
    doc_ids = [item.doc_id for item in items if item.doc_id]
    source_file_ids = [item.source_file_id for item in items if item.source_file_id]
    upload_ids = [item.upload_id for item in items if item.upload_id]
    task_candidates = workspace_service._task_repo.list_by_document_context(  # noqa: SLF001
        tenant_id=user.tenant_id,
        doc_ids=doc_ids,
        source_file_ids=source_file_ids,
        upload_ids=upload_ids,
    )
    ticket_candidates = workspace_service._ticket_repo.list_by_document_context(  # noqa: SLF001
        tenant_id=user.tenant_id,
        doc_ids=doc_ids,
        source_file_ids=source_file_ids,
    )
    return {
        "items": [
            {
                **_document_to_dict(item, workspace_service=None),
                "ticket_id": (
                    selected_ticket.ticket_id
                    if (selected_ticket := _select_ticket_projection_for_document(item, ticket_candidates)) is not None
                    else None
                ),
                "ticket_status": selected_ticket.state if selected_ticket is not None else None,
                "task_status": (
                    workspace_service._derive_task_status(selected_task)  # noqa: SLF001
                    if (selected_task := _select_task_projection_for_document(item, task_candidates)) is not None
                    else None
                ),
            }
            for item in items
        ],
        "total": total,
    }
