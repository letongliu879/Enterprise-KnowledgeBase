"""Source file proxy routes.

Workbench-api validates JWT and collection scope, then proxies to document-service
or returns a signed URL for object storage. Original binary content is never stored
in workbench SQL.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..downstream_clients import IntakeClient
from ..downstream_clients.errors import DownstreamError
from ..errors import not_found, forbidden, downstream_unavailable
from ..projections.repository import DocumentProjectionRepository

router = APIRouter()


@router.get("/workbench/source-files/{source_file_id}/content")
async def get_source_file_content(
    source_file_id: str,
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Proxy source file content from intake/document-service."""
    # Validate scope via document projection
    doc_repo = DocumentProjectionRepository(session)
    docs = doc_repo.list(
        tenant_id=user.tenant_id,
        collection_ids=user.allowed_collections,
        offset=0,
        limit=1,
    )[0]
    # Filter to source_file_id match
    matching_doc = next((d for d in docs if d.source_file_id == source_file_id), None)
    if matching_doc is None:
        # Fallback: check if any task projection has this source_file_id
        from reality_rag_persistence.models import WorkbenchTaskProjectionModel
        task = session.query(WorkbenchTaskProjectionModel).filter_by(
            tenant_id=user.tenant_id,
            source_file_id=source_file_id,
        ).first()
        if task is None or not user.can_access_collection(task.collection_id):
            raise forbidden("Source file access denied")
        collection_id = task.collection_id
    else:
        collection_id = matching_doc.collection_id
        if not user.can_access_collection(collection_id):
            raise forbidden("Source file access denied")

    intake_client = IntakeClient()
    try:
        source_file = await intake_client.get_source_file(source_file_id)
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_unavailable("Source file content proxy not yet available")
        raise downstream_unavailable(f"Cannot fetch source file: {e.message}")

    # Return metadata and a proxy reference; actual binary served by document-service
    return {
        "source_file_id": source_file_id,
        "collection_id": collection_id,
        "filename": source_file.get("original_name", ""),
        "mime_type": source_file.get("mime_type", "application/octet-stream"),
        "size_bytes": source_file.get("size_bytes", 0),
        "storage_url": source_file.get("storage_url"),
        "download_url": source_file.get("download_url"),
    }


@router.get("/workbench/source-files/{source_file_id}/preview")
async def get_source_file_preview(
    source_file_id: str,
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Return preview descriptor for a source file (no binary in SQL)."""
    from reality_rag_persistence.models import WorkbenchTaskProjectionModel
    task = session.query(WorkbenchTaskProjectionModel).filter_by(
        tenant_id=user.tenant_id,
        source_file_id=source_file_id,
    ).first()
    if task is None or not user.can_access_collection(task.collection_id):
        raise forbidden("Source file access denied")

    intake_client = IntakeClient()
    try:
        source_file = await intake_client.get_source_file(source_file_id)
    except DownstreamError as e:
        raise downstream_unavailable(f"Cannot fetch source file preview: {e.message}")

    return {
        "source_file_id": source_file_id,
        "collection_id": task.collection_id,
        "filename": source_file.get("original_name", ""),
        "mime_type": source_file.get("mime_type", "application/octet-stream"),
        "page_count": source_file.get("page_count"),
        "preview_available": source_file.get("preview_available", False),
        "preview_url": source_file.get("preview_url"),
        "thumbnail_url": source_file.get("thumbnail_url"),
    }
