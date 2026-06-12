"""Trash endpoints — list, restore, and hard-delete documents."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from reality_rag_persistence.models import WorkbenchDocumentProjectionModel

from ..deps import CurrentUser, get_db, require_auth
from ..errors import not_found
from ..projections.repository import DocumentProjectionRepository

router = APIRouter(prefix="/workbench/trash")


@router.get("")
async def list_trash(
    user: CurrentUser = Depends(require_auth),
    session: Session = Depends(get_db),
):
    """List documents with ARCHIVED or RETRACTED document_state."""
    repo = DocumentProjectionRepository(session)
    archived, archived_total = repo.list(
        tenant_id=user.tenant_id,
        document_state="ARCHIVED",
        limit=200,
    )
    retracted, retracted_total = repo.list(
        tenant_id=user.tenant_id,
        document_state="RETRACTED",
        limit=200,
    )

    items = []
    for doc in archived + retracted:
        items.append({
            "doc_id": doc.doc_id,
            "tenant_id": doc.tenant_id,
            "collection_id": doc.collection_id,
            "filename": doc.filename or "",
            "mime_type": doc.mime_type or "",
            "document_state": doc.document_state or "",
            "projection_updated_at": doc.projection_updated_at.isoformat() if doc.projection_updated_at else None,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        })

    return {"items": items, "total": archived_total + retracted_total}


@router.post("/{doc_id}/restore")
async def restore_document(
    doc_id: str,
    user: CurrentUser = Depends(require_auth),
    session: Session = Depends(get_db),
):
    """Mark a trashed document as ACTIVE."""
    repo = DocumentProjectionRepository(session)
    doc = repo.get(doc_id)
    if doc is None:
        raise not_found("Document not found")

    doc.document_state = "ACTIVE"
    session.commit()

    return {
        "doc_id": doc.doc_id,
        "document_state": doc.document_state,
    }


@router.delete("/{doc_id}", status_code=204)
async def hard_delete_document(
    doc_id: str,
    user: CurrentUser = Depends(require_auth),
    session: Session = Depends(get_db),
):
    """Hard delete a document projection from DB."""
    repo = DocumentProjectionRepository(session)
    doc = repo.get(doc_id)
    if doc is None:
        raise not_found("Document not found")

    session.delete(doc)
    session.commit()
