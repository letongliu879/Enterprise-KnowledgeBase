"""Access service downstream client for workbench retrieval verification."""

import httpx

from ..config import config
from .errors import DownstreamError


class AccessClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.access_base_url).rstrip("/")
        self._timeout = config.default_http_timeout
        self._api_key = getattr(config, "access_internal_api_key", "")

    async def retrieve(self, payload: dict) -> dict:
        url = f"{self._base_url}/v1/retrieve"
        headers = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
            headers["X-Agent-Instance-Id"] = "workbench-internal"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Access service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Access service timeout: {e}")
        return self._handle_response(response, url)

    def _handle_response(self, response: httpx.Response, url: str) -> dict:
        if response.status_code == 404:
            raise DownstreamError.not_implemented(f"Access endpoint not implemented: {url}")
        if response.status_code == 501:
            raise DownstreamError.not_implemented(f"Access endpoint not implemented: {url}")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"Access conflict: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError(
                "DOWNSTREAM_ERROR",
                f"Access service returned {response.status_code}: {response.text}",
                response.status_code,
            )
        return response.json()
