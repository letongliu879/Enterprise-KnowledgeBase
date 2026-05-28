"""Admin service downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class AdminClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.admin_base_url).rstrip("/")
        self._timeout = config.default_http_timeout

    async def get_collection(self, collection_id: str) -> dict:
        url = f"{self._base_url}/admin/collections/{collection_id}"
        return await self._get(url)

    async def list_parser_profiles(self) -> list[dict]:
        url = f"{self._base_url}/admin/parser-profiles"
        return await self._get(url)

    async def _get(self, url: str, params: dict | None = None) -> dict | list:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Admin service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Admin service timeout: {e}")
        return self._handle_response(response, url)

    def _handle_response(self, response: httpx.Response, url: str) -> dict | list:
        if response.status_code == 404:
            raise DownstreamError.not_implemented(f"Admin endpoint not implemented: {url}")
        if response.status_code == 501:
            raise DownstreamError.not_implemented(f"Admin endpoint not implemented: {url}")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"Admin conflict: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Admin service returned {response.status_code}: {response.text}", response.status_code)
        return response.json()
