"""Ticket service."""

from ..deps import CurrentUser
from ..downstream_clients import ApprovalClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, forbidden
from .models import TicketDecisionRequest, TicketItem, TicketDetail


class TicketService:
    def __init__(self, approval_client: ApprovalClient):
        self._approval_client = approval_client

    @staticmethod
    def _assert_collection_access(collection_id: str, user: CurrentUser) -> None:
        if collection_id and not user.can_access_collection(collection_id):
            raise forbidden("Collection access denied")

    async def _fetch_ticket_raw(self, ticket_id: str) -> dict:
        try:
            return await self._approval_client.get_ticket(ticket_id)
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Approval ticket API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Approval service unavailable")
            raise

    async def list_tickets(self, collection_id: str | None, status: str | None, user: CurrentUser) -> list[TicketItem]:
        self._assert_collection_access(collection_id or "", user)

        try:
            results = await self._approval_client.list_tickets(
                tenant_id=user.tenant_id,
                collection_id=collection_id,
                status=status,
            )
            items = []
            for r in results:
                item_collection_id = r.get("collection_id", "")
                if item_collection_id and not user.can_access_collection(item_collection_id):
                    continue
                items.append(TicketItem(
                    ticket_id=r.get("ticket_id", ""),
                    collection_id=item_collection_id,
                    status=r.get("status") or r.get("state", ""),
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
        r = await self._fetch_ticket_raw(ticket_id)
        collection_id = r.get("collection_id", "")
        self._assert_collection_access(collection_id, user)
        return TicketDetail(
            ticket_id=r.get("ticket_id", ""),
            collection_id=collection_id,
            status=r.get("status") or r.get("state", ""),
            doc_id=r.get("doc_id"),
            source_file_id=r.get("source_file_id"),
            parse_snapshot_id=r.get("parse_snapshot_id"),
            filename=r.get("filename"),
            decision=r.get("decision"),
            decision_reason=r.get("decision_reason"),
            decided_by=r.get("decided_by"),
            tenant_id=r.get("tenant_id", user.tenant_id),
            created_at=r.get("created_at", ""),
            updated_at=r.get("updated_at"),
        )

    async def decide_ticket(self, ticket_id: str, req: TicketDecisionRequest, user: CurrentUser) -> dict:
        ticket = await self._fetch_ticket_raw(ticket_id)
        collection_id = str(ticket.get("collection_id") or req.collection_id or "")
        self._assert_collection_access(collection_id, user)
        tenant_id = str(ticket.get("tenant_id") or user.tenant_id)

        command = {
            "command_id": f"cmd_{req.decision_request_id}",
            "trace_id": f"trc_{req.decision_request_id}",
            "idempotency_key": req.decision_request_id,
            "actor": user.user_id,
            "tenant_id": tenant_id,
            "collection_id": collection_id,
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
        ticket = await self._fetch_ticket_raw(ticket_id)
        collection_id = ticket.get("collection_id", "")
        self._assert_collection_access(collection_id, user)
        try:
            result = await self._approval_client.get_agent_review(ticket_id)
            return result
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("AgentReview API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Approval service unavailable")
            raise
