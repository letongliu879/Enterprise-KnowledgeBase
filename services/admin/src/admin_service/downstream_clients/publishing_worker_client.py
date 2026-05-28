"""Publishing-worker downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class PublishingWorkerClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.publishing_worker_base_url).rstrip("/")

    async def archive_document(
        self,
        final_doc_id: str,
        *,
        actor_id: str = "system",
        reason: str = "",
        idempotency_key: str = "",
    ) -> dict:
        """POST /internal/published-documents/{final_doc_id}/archive"""
        url = f"{self._base_url}/internal/published-documents/{final_doc_id}/archive"
        payload = {
            "state": "ARCHIVED",
            "actor_id": actor_id,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Publishing worker unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Publishing worker timeout: {e}")

        if response.status_code == 404:
            raise DownstreamError("NOT_FOUND", f"Published document not found: {final_doc_id}", 404)
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Publishing worker returned {response.status_code}: {response.text}", response.status_code)

        return response.json()

    async def retract_document(
        self,
        final_doc_id: str,
        *,
        actor_id: str = "system",
        reason: str = "",
        idempotency_key: str = "",
    ) -> dict:
        """POST /internal/published-documents/{final_doc_id}/retract"""
        url = f"{self._base_url}/internal/published-documents/{final_doc_id}/retract"
        payload = {
            "state": "RETRACTED",
            "actor_id": actor_id,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Publishing worker unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Publishing worker timeout: {e}")

        if response.status_code == 404:
            raise DownstreamError("NOT_FOUND", f"Published document not found: {final_doc_id}", 404)
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Publishing worker returned {response.status_code}: {response.text}", response.status_code)

        return response.json()
