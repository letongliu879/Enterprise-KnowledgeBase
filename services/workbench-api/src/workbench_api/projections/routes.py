"""Projection read routes — list endpoints query SQL only, no downstream fan-out.

NOTE: /workbench/tasks and /workbench/tickets are currently served by
      task_projection/routes.py and tickets/routes.py respectively.
      This module only provides /workbench/documents to avoid route conflicts.
      When projection writes are fully integrated, migrate the old routes here.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from .repository import DocumentProjectionRepository

router = APIRouter()


def _document_to_dict(item):
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
    }


@router.get("/workbench/documents/{doc_id}")
async def get_document(
    doc_id: str,
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Get a single document from SQL projection."""
    repo = DocumentProjectionRepository(session)
    item = repo.get(doc_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    if not user.can_access_collection(item.collection_id):
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return _document_to_dict(item)


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
    return {
        "items": [_document_to_dict(item) for item in items],
        "total": total,
    }
