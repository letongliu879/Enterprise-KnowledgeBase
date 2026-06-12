"""Ticket transfer routes.

Transfer a ticket to a different assignee.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..errors import not_found, bad_request
from ..projections.repository import TicketProjectionRepository
from ..projections.projector import ProjectionProjector

router = APIRouter()


class TransferRequest(BaseModel):
    assignee_user_id: str


@router.post("/workbench/tickets/{ticket_id}/transfer")
def transfer_ticket(
    ticket_id: str,
    req: TransferRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Transfer a ticket to another user."""
    ticket_repo = TicketProjectionRepository(db)
    ticket = ticket_repo.get(ticket_id)

    if ticket is None:
        raise not_found("Ticket not found")
    if not user.can_access_collection(ticket.collection_id):
        raise not_found("Ticket not found")

    if req.assignee_user_id == ticket.assignee_user_id:
        raise bad_request("Cannot transfer ticket to current assignee")

    projector = ProjectionProjector(db)
    import uuid
    from datetime import datetime, timezone

    event = {
        "event_id": f"transfer_{ticket_id}_{uuid.uuid4().hex[:8]}",
        "event_type": "TICKET_TRANSFERRED",
        "tenant_id": ticket.tenant_id,
        "collection_id": ticket.collection_id,
        "aggregate_type": "ticket",
        "aggregate_id": ticket_id,
        "aggregate_version": ticket.version + 1,
        "occurred_at": datetime.now(timezone.utc),
        "payload": {
            "ticket_id": ticket_id,
            "tenant_id": ticket.tenant_id,
            "collection_id": ticket.collection_id,
            "assignee_user_id": req.assignee_user_id,
            "state": ticket.state,
            "upload_id": ticket.upload_id,
            "source_file_id": ticket.source_file_id,
            "parse_snapshot_id": ticket.parse_snapshot_id,
            "doc_id": ticket.doc_id,
            "title": ticket.title,
            "filename": ticket.filename,
            "priority": ticket.priority,
            "routing_recommendation": ticket.routing_recommendation,
            "agent_decision": ticket.agent_decision,
            "agent_risk_level": ticket.agent_risk_level,
            "agent_finding_count": ticket.agent_finding_count,
            "agent_blocking_finding_count": ticket.agent_blocking_finding_count,
        },
        "trace_id": ticket_id,
    }
    projector.record_and_apply(event)
    db.commit()

    return {
        "ticket_id": ticket_id,
        "assignee_user_id": req.assignee_user_id,
    }
