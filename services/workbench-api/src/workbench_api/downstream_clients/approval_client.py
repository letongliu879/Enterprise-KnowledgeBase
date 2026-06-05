"""Approval-service downstream client."""

from ..config import config
from .base import BaseHttpClient


class ApprovalClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(
            base_url=base_url or config.approval_base_url,
            timeout=config.default_http_timeout,
            service_name="Approval",
        )

    async def list_tickets(self, tenant_id: str, collection_id: str | None = None, status: str | None = None) -> list[dict]:
        params: dict = {"tenant_id": tenant_id}
        if collection_id:
            params["collection_id"] = collection_id
        if status:
            params["state"] = status
        return await self._request("get", "/internal/tickets", params=params)

    async def get_ticket(self, ticket_id: str) -> dict:
        return await self._request("get", f"/internal/tickets/{ticket_id}")

    async def decide_ticket(self, ticket_id: str, command: dict) -> dict:
        return await self._request("post", f"/internal/tickets/{ticket_id}/decide", json=command)

    async def get_agent_review(self, ticket_id: str) -> dict:
        return await self._request("get", f"/internal/tickets/{ticket_id}/agent-review")
