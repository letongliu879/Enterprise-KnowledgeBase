"""Access service downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class AccessClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.access_base_url).rstrip("/")

    async def sync_api_key_projection(self, api_key_entry: dict) -> dict:
        """POST /internal/api-key-projections/sync

        Syncs API key state to access service projection.
        Returns projection result or raises DownstreamError.
        """
        url = f"{self._base_url}/internal/api-key-projections/sync"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=api_key_entry)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Access service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Access service timeout: {e}")

        if response.status_code == 404:
            raise DownstreamError.not_implemented("API key projection sync not implemented in access service")
        if response.status_code == 501:
            raise DownstreamError.not_implemented("API key projection sync not implemented in access service")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"API key projection sync failed: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Access service returned {response.status_code}: {response.text}", response.status_code)

        return response.json()
