"""Base HTTP client for downstream services."""

import httpx

from .errors import DownstreamError


class BaseHttpClient:
    """Base HTTP client with unified error handling."""

    def __init__(self, base_url: str, timeout: float, service_name: str, *, api_key: str = ""):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._service_name = service_name
        self._api_key = api_key

    async def _request(self, method: str, path_or_url: str, **kwargs) -> dict | list:
        """Make HTTP request with unified error handling.

        Args:
            method: HTTP method (get, post, put, delete)
            path_or_url: URL path (prefixed with base_url) or full URL
            **kwargs: Additional arguments passed to httpx
        """
        if path_or_url.startswith("http"):
            url = path_or_url
        else:
            url = f"{self._base_url}{path_or_url}"

        headers = kwargs.pop("headers", {})
        if self._api_key:
            headers["X-API-Key"] = self._api_key
            headers["X-Agent-Instance-Id"] = "workbench-internal"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await getattr(client, method)(url, headers=headers, **kwargs)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"{self._service_name} service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"{self._service_name} service timeout: {e}")

        if response.status_code in (404, 501):
            raise DownstreamError.not_implemented(f"{self._service_name} endpoint not implemented: {url}")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"{self._service_name} conflict: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError(
                "DOWNSTREAM_ERROR",
                f"{self._service_name} service returned {response.status_code}: {response.text}",
                response.status_code,
            )
        return response.json()
