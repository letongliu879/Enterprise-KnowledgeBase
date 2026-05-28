"""Ops audit routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from .service import OpsAuditService
from .repository import OpsAuditRepository
from .models import AuditLogQueryRequest, AuditLogListResponse

router = APIRouter(prefix="/admin/ops")


def _get_service(session: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> OpsAuditService:
    return OpsAuditService(OpsAuditRepository(session), actor_id=user.user_id)


@router.post("/audit-log", response_model=AuditLogListResponse)
def query_audit_log(
    req: AuditLogQueryRequest,
    service: OpsAuditService = Depends(_get_service),
):
    items, total = service.query(
        actor_id=req.actor_id,
        target_type=req.target_type,
        target_id=req.target_id,
        tenant_id=req.tenant_id,
        collection_id=req.collection_id,
        limit=req.limit,
        offset=req.offset,
    )
    return AuditLogListResponse(
        items=items,
        total=total,
        limit=req.limit,
        offset=req.offset,
    )


@router.get("/audit-log")
def list_audit_log(
    actor_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    tenant_id: str | None = None,
    collection_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    service: OpsAuditService = Depends(_get_service),
):
    items, total = service.query(
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        tenant_id=tenant_id,
        collection_id=collection_id,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
