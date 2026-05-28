"""Indexing service downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class IndexingClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.indexing_base_url).rstrip("/")

    async def get_parse_snapshot(self, parse_snapshot_id: str) -> dict:
        """GET /internal/parse-snapshots/{parse_snapshot_id}"""
        url = f"{self._base_url}/internal/parse-snapshots/{parse_snapshot_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Indexing service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Indexing service timeout: {e}")

        if response.status_code == 404:
            raise DownstreamError("NOT_FOUND", f"Parse snapshot not found: {parse_snapshot_id}", 404)
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Indexing service returned {response.status_code}: {response.text}", response.status_code)

        return response.json()

    async def submit_index_job(self, command: dict) -> dict:
        """POST /internal/index-jobs

        Submits an IndexBuildRequestedCommand. Returns {build_job_id, status} or raises DownstreamError.
        """
        url = f"{self._base_url}/internal/index-jobs"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=command)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Indexing service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Indexing service timeout: {e}")

        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Indexing service returned {response.status_code}: {response.text}", response.status_code)

        return response.json()

    async def get_index_job(self, job_id: str) -> dict:
        """GET /internal/index-jobs/{job_id}"""
        url = f"{self._base_url}/internal/index-jobs/{job_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Indexing service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Indexing service timeout: {e}")

        if response.status_code == 404:
            raise DownstreamError("NOT_FOUND", f"Index job not found: {job_id}", 404)
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Indexing service returned {response.status_code}: {response.text}", response.status_code)

        return response.json()

    async def validate_parser_profile(self, parser_config: dict) -> dict:
        """POST /internal/parser-profiles/validate

        Returns canonical runtime config or raises DownstreamError.
        """
        url = f"{self._base_url}/internal/parser-profiles/validate"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=parser_config)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Indexing service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Indexing service timeout: {e}")

        if response.status_code == 404:
            raise DownstreamError.not_implemented("Parser profile validation not implemented in indexing service")
        if response.status_code == 501:
            raise DownstreamError.not_implemented("Parser profile validation not implemented in indexing service")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"Parser profile validation failed: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Indexing service returned {response.status_code}: {response.text}", response.status_code)

        return response.json()
