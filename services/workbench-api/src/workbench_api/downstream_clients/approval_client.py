"""Approval-service downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class ApprovalClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.approval_base_url).rstrip("/")
        self._timeout = config.default_http_timeout

    async def list_tickets(self, tenant_id: str, collection_id: str | None = None, status: str | None = None) -> list[dict]:
        url = f"{self._base_url}/internal/tickets"
        params: dict = {"tenant_id": tenant_id}
        if collection_id:
            params["collection_id"] = collection_id
        if status:
            params["state"] = status
        return await self._get(url, params)

    async def get_ticket(self, ticket_id: str) -> dict:
        url = f"{self._base_url}/internal/tickets/{ticket_id}"
        return await self._get(url)

    async def decide_ticket(self, ticket_id: str, command: dict) -> dict:
        url = f"{self._base_url}/internal/tickets/{ticket_id}/decide"
        return await self._post(url, command)

    async def get_agent_review(self, ticket_id: str) -> dict:
        url = f"{self._base_url}/internal/tickets/{ticket_id}/agent-review"
        return await self._get(url)

    async def _get(self, url: str, params: dict | None = None) -> dict | list:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Approval service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Approval service timeout: {e}")
        return self._handle_response(response, url)

    async def _post(self, url: str, json: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=json)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Approval service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Approval service timeout: {e}")
        return self._handle_response(response, url)

    def _handle_response(self, response: httpx.Response, url: str) -> dict | list:
        if response.status_code == 404:
            raise DownstreamError.not_implemented(f"Approval endpoint not implemented: {url}")
        if response.status_code == 501:
            raise DownstreamError.not_implemented(f"Approval endpoint not implemented: {url}")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"Approval conflict: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Approval service returned {response.status_code}: {response.text}", response.status_code)
        return response.json()
