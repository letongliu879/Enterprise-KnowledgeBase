"""Ticket routes.

List endpoints read from SQL projection (no downstream fan-out).
Detail endpoints read projection first, with optional approval fallback.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, require_role, CurrentUser
from ..downstream_clients import ApprovalClient
from ..errors import not_found
from ..projections.repository import TicketProjectionRepository
from .models import TicketDecisionRequest
from .service import TicketService

router = APIRouter(prefix="/workbench/tickets")


def _get_service() -> TicketService:
    return TicketService(ApprovalClient())


@router.get("")
async def list_tickets(
    collection_id: str | None = None,
    state: str | None = None,
    priority: str | None = None,
    assignee: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """List tickets from SQL projection only. No downstream fan-out."""
    repo = TicketProjectionRepository(db)
    offset = (page - 1) * page_size

    collection_ids = None
    if collection_id:
        if not user.can_access_collection(collection_id):
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        collection_ids = [collection_id]
    else:
        collection_ids = user.allowed_collections or None

    items, total = repo.list(
        tenant_id=user.tenant_id,
        collection_ids=collection_ids,
        state=state,
        offset=offset,
        limit=page_size,
    )

    return {
        "items": [
            {
                "ticket_id": item.ticket_id,
                "collection_id": item.collection_id,
                "state": item.state,
                "priority": item.priority,
                "assignee_user_id": item.assignee_user_id,
                "title": item.title,
                "filename": item.filename,
                "agent_decision": item.agent_decision,
                "agent_risk_level": item.agent_risk_level,
                "agent_finding_count": item.agent_finding_count,
                "agent_blocking_finding_count": item.agent_blocking_finding_count,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                "projection_updated_at": item.projection_updated_at.isoformat() if item.projection_updated_at else None,
                "is_stale": item.is_stale,
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Get ticket details. Reads projection first; falls back to approval if stale/missing."""
    repo = TicketProjectionRepository(db)
    projection = repo.get(ticket_id)

    if projection and not projection.is_stale:
        # Validate access
        if not user.can_access_collection(projection.collection_id):
            raise not_found("Ticket not found")
        return {
            "ticket_id": projection.ticket_id,
            "collection_id": projection.collection_id,
            "state": projection.state,
            "priority": projection.priority,
            "assignee_user_id": projection.assignee_user_id,
            "title": projection.title,
            "filename": projection.filename,
            "upload_id": projection.upload_id,
            "source_file_id": projection.source_file_id,
            "parse_snapshot_id": projection.parse_snapshot_id,
            "doc_id": projection.doc_id,
            "agent_decision": projection.agent_decision,
            "agent_risk_level": projection.agent_risk_level,
            "agent_finding_count": projection.agent_finding_count,
            "agent_blocking_finding_count": projection.agent_blocking_finding_count,
            "created_at": projection.created_at.isoformat() if projection.created_at else None,
            "updated_at": projection.updated_at.isoformat() if projection.updated_at else None,
            "projection_updated_at": projection.projection_updated_at.isoformat() if projection.projection_updated_at else None,
            "is_stale": projection.is_stale,
            "source": "projection",
        }

    # Fallback to approval service
    service = _get_service()
    detail = await service.get_ticket(ticket_id, user)
    return {**detail.model_dump(), "source": "approval"}


@router.post("/{ticket_id}/decide")
async def decide_ticket(
    ticket_id: str,
    req: TicketDecisionRequest,
    user: CurrentUser = Depends(require_role("reviewer")),
):
    """Submit ticket decision. Still calls approval service; projection updated via callback."""
    service = _get_service()
    result = await service.decide_ticket(ticket_id, req, user)
    return result


@router.get("/{ticket_id}/agent-review")
async def get_agent_review(
    ticket_id: str,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Get agent review findings. Reads from projection first."""
    from ..projections.repository import AgentReviewProjectionRepository

    repo = AgentReviewProjectionRepository(db)
    findings = repo.list_by_ticket(ticket_id, user.tenant_id)

    if findings:
        return {
            "ticket_id": ticket_id,
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "severity": f.severity,
                    "category": f.category,
                    "problem_summary": f.problem_summary,
                    "evidence_id": f.evidence_id,
                    "doc_id": f.doc_id,
                    "page_from": f.page_from,
                    "page_to": f.page_to,
                    "state": f.state,
                    "confidence": f.confidence,
                }
                for f in findings
            ],
            "source": "projection",
        }

    # Fallback to approval service
    service = _get_service()
    result = await service.get_agent_review(ticket_id, user)
    return {**result, "source": "approval"}
