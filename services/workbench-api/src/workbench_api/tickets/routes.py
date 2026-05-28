"""Ticket routes."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, require_role, CurrentUser
from ..downstream_clients import ApprovalClient
from ..errors import not_found
from .models import TicketDecisionRequest
from .service import TicketService

router = APIRouter(prefix="/workbench/tickets")


def _get_service() -> TicketService:
    return TicketService(ApprovalClient())


@router.get("")
async def list_tickets(collection_id: str | None = None, status: str | None = None, user: CurrentUser = Depends(require_auth)):
    service = _get_service()
    items = await service.list_tickets(collection_id, status, user)
    return {"items": [item.model_dump() for item in items], "total": len(items)}


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str, user: CurrentUser = Depends(require_auth)):
    service = _get_service()
    detail = await service.get_ticket(ticket_id, user)
    return detail.model_dump()


@router.post("/{ticket_id}/decide")
async def decide_ticket(ticket_id: str, req: TicketDecisionRequest, user: CurrentUser = Depends(require_role("reviewer"))):
    service = _get_service()
    result = await service.decide_ticket(ticket_id, req, user)
    return result


@router.get("/{ticket_id}/agent-review")
async def get_agent_review(ticket_id: str, user: CurrentUser = Depends(require_auth)):
    service = _get_service()
    result = await service.get_agent_review(ticket_id, user)
    return result
