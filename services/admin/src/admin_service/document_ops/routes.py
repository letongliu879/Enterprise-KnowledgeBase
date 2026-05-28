"""Document lifecycle ops routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser, require_role
from ..errors import not_found, conflict, downstream_unavailable
from ..downstream_clients.publishing_worker_client import PublishingWorkerClient
from ..downstream_clients.indexing_client import IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..ops_audit.service import OpsAuditService
from ..ops_audit.repository import OpsAuditRepository
from .service import DocumentOpsService
from .models import DocumentLifecycleRequest, DocumentReindexRequest, DocumentLifecycleResponse

router = APIRouter()


def _get_service(
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
) -> DocumentOpsService:
    return DocumentOpsService(
        publishing_worker_client=PublishingWorkerClient(),
        indexing_client=IndexingClient(),
        audit_service=OpsAuditService(OpsAuditRepository(session), actor_id=user.user_id),
    )


def _require_knowledge_admin(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    if not user.has_role("knowledge_admin") and not user.has_role("platform_admin"):
        from ..errors import forbidden
        raise forbidden("Knowledge admin or platform admin role required")
    return user


@router.post("/admin/documents/{final_doc_id}/archive", response_model=DocumentLifecycleResponse)
async def archive_document(
    final_doc_id: str,
    req: DocumentLifecycleRequest,
    service: DocumentOpsService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    try:
        return await service.archive_document(final_doc_id, req)
    except DownstreamError as e:
        if e.status_code == 404:
            raise not_found(f"Published document {final_doc_id} not found")
        if e.status_code == 503:
            raise downstream_unavailable(e.message)
        raise conflict(f"Archive failed: {e.code}: {e.message}")


@router.post("/admin/documents/{final_doc_id}/retract", response_model=DocumentLifecycleResponse)
async def retract_document(
    final_doc_id: str,
    req: DocumentLifecycleRequest,
    service: DocumentOpsService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    try:
        return await service.retract_document(final_doc_id, req)
    except DownstreamError as e:
        if e.status_code == 404:
            raise not_found(f"Published document {final_doc_id} not found")
        if e.status_code == 503:
            raise downstream_unavailable(e.message)
        raise conflict(f"Retract failed: {e.code}: {e.message}")


@router.post("/admin/documents/{final_doc_id}/reindex", response_model=DocumentLifecycleResponse)
async def reindex_document(
    final_doc_id: str,
    req: DocumentReindexRequest,
    service: DocumentOpsService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    try:
        return await service.reindex_document(final_doc_id, req)
    except DownstreamError as e:
        if e.status_code == 404:
            raise not_found(f"Document or snapshot not found: {final_doc_id}")
        if e.status_code == 503:
            raise downstream_unavailable(e.message)
        raise conflict(f"Reindex failed: {e.code}: {e.message}")
