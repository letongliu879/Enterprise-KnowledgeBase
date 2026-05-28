"""Ticket service."""

from ..deps import CurrentUser
from ..downstream_clients import ApprovalClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, forbidden
from .models import TicketDecisionRequest, TicketItem, TicketDetail


class TicketService:
    def __init__(self, approval_client: ApprovalClient):
        self._approval_client = approval_client

    async def list_tickets(self, collection_id: str | None, status: str | None, user: CurrentUser) -> list[TicketItem]:
        if collection_id and not user.can_access_collection(collection_id):
            raise forbidden("Collection access denied")

        try:
            results = await self._approval_client.list_tickets(
                tenant_id=user.tenant_id,
                collection_id=collection_id,
                status=status,
            )
            items = []
            for r in results:
                items.append(TicketItem(
                    ticket_id=r.get("ticket_id", ""),
                    collection_id=r.get("collection_id", ""),
                    status=r.get("status", ""),
                    doc_id=r.get("doc_id"),
                    source_file_id=r.get("source_file_id"),
                    created_at=r.get("created_at", ""),
                    updated_at=r.get("updated_at"),
                ))
            return items
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Approval tickets API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Approval service unavailable")
            raise

    async def get_ticket(self, ticket_id: str, user: CurrentUser) -> TicketDetail:
        try:
            r = await self._approval_client.get_ticket(ticket_id)
            return TicketDetail(
                ticket_id=r.get("ticket_id", ""),
                collection_id=r.get("collection_id", ""),
                status=r.get("status", ""),
                doc_id=r.get("doc_id"),
                source_file_id=r.get("source_file_id"),
                parse_snapshot_id=r.get("parse_snapshot_id"),
                decision=r.get("decision"),
                decision_reason=r.get("decision_reason"),
                decided_by=r.get("decided_by"),
                created_at=r.get("created_at", ""),
                updated_at=r.get("updated_at"),
            )
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Approval ticket API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Approval service unavailable")
            raise

    async def decide_ticket(self, ticket_id: str, req: TicketDecisionRequest, user: CurrentUser) -> dict:
        if not user.can_access_collection(req.collection_id):
            raise forbidden("Collection access denied")

        command = {
            "command_id": f"cmd_{req.decision_request_id}",
            "trace_id": f"trc_{req.decision_request_id}",
            "idempotency_key": req.decision_request_id,
            "actor": req.actor,
            "tenant_id": req.tenant_id,
            "collection_id": req.collection_id,
            "target_type": "ticket",
            "target_id": ticket_id,
            "payload": {
                "action": req.action,
                "reason": req.reason,
            },
        }

        try:
            result = await self._approval_client.decide_ticket(ticket_id, command)
            return {
                "ticket_id": ticket_id,
                "status": result.get("status", req.action.lower()),
                "decision": req.action,
            }
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Approval ticket decide API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Approval service unavailable")
            raise

    async def get_agent_review(self, ticket_id: str, user: CurrentUser) -> dict:
        try:
            result = await self._approval_client.get_agent_review(ticket_id)
            return result
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("AgentReview API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Approval service unavailable")
            raise
