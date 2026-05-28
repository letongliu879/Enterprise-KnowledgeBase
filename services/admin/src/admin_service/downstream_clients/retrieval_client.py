"""Retrieval service downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class RetrievalClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.retrieval_base_url).rstrip("/")

    async def validate_retrieval_profile(self, profile_config: dict) -> dict:
        """POST /internal/retrieval-profiles/validate

        Returns canonical runtime config or raises DownstreamError.
        """
        url = f"{self._base_url}/internal/retrieval-profiles/validate"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=profile_config)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Retrieval service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Retrieval service timeout: {e}")

        if response.status_code == 404:
            raise DownstreamError.not_implemented("Retrieval profile validation not implemented in retrieval service")
        if response.status_code == 501:
            raise DownstreamError.not_implemented("Retrieval profile validation not implemented in retrieval service")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"Retrieval profile validation failed: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Retrieval service returned {response.status_code}: {response.text}", response.status_code)

        return response.json()

    async def sync_retrieval_profile_projection(self, payload: dict) -> dict:
        """POST /internal/retrieval-profile-projections/sync

        Upserts a retrieval profile projection into retrieval runtime DB.
        Raises DownstreamError on failure.
        """
        url = f"{self._base_url}/internal/retrieval-profile-projections/sync"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Retrieval service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Retrieval service timeout: {e}")

        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Retrieval service returned {response.status_code}: {response.text}", response.status_code)

        return response.json()
