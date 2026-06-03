"""Document service client facade.

`document-service` is the only source-file owner. Ingestion code must call it
through its split-service HTTP API instead of silently falling back in-process.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

__all__ = [
    "DocumentServiceClient",
]

_REMOTE_URL: str | None = None


def _get_remote_url() -> str | None:
    global _REMOTE_URL
    if _REMOTE_URL is None:
        _REMOTE_URL = os.environ.get("DOCUMENT_SERVICE_URL", "").rstrip("/") or None
    return _REMOTE_URL


def _require_remote_url() -> str:
    base = _get_remote_url()
    if base is None:
        raise RuntimeError(
            "DOCUMENT_SERVICE_URL is required; document-service must run through its split-service owner."
        )
    return base


def _url(path: str) -> str:
    base = _require_remote_url()
    return f"{base}{path}"


class _RemoteDocumentService:
    """HTTP client facade that mirrors DocumentService API."""

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(_url(path), json=payload, timeout=30.0)
        if resp.status_code >= 400:
            raise RuntimeError(resp.text)
        return resp.json()

    async def _post_async(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(_url(path), json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(resp.text)
            return resp.json()

    def create_source_file(
        self,
        collection_id: str,
        object_id: str,
        content_hash: str,
    ) -> dict[str, Any]:
        return self._post(
            "/internal/source-files",
            {
                "collection_id": collection_id,
                "object_id": object_id,
                "content_hash": content_hash,
            },
        )

    def claim(self, source_file_id: str, job_id: str) -> bool:
        result = self._post(
            f"/internal/source-files/{source_file_id}/claim",
            {"job_id": job_id},
        )
        return result.get("claimed", False)

    def mark_consumed(self, source_file_id: str, job_id: str) -> bool:
        result = self._post(
            f"/internal/source-files/{source_file_id}/mark-consumed",
            {"job_id": job_id},
        )
        return result.get("consumed", False)

    def mark_cleanable(self, source_file_id: str, job_id: str) -> bool:
        result = self._post(
            f"/internal/source-files/{source_file_id}/mark-cleanable",
            {"job_id": job_id},
        )
        return result.get("cleanable", False)

    def find_active_by_content_hash(self, content_hash: str, collection_id: str) -> dict[str, Any] | None:
        # document-service doesn't expose a direct find_active endpoint;
        # use dedup-check as a proxy for active source file detection
        result = self._post(
            "/internal/dedup-check",
            {"content_hash": content_hash, "collection_id": collection_id},
        )
        # dedup-check returns is_duplicate + existing_doc_id;
        # if is_duplicate but no doc_id, it's an active source file
        if result.get("is_duplicate") and result.get("existing_doc_id") is None:
            return {"content_hash": content_hash, "collection_id": collection_id}
        return None

    def get_object_blob(self, object_id: str) -> dict[str, Any] | None:
        return None

    def get_or_create_object_blob(self, content_hash: str, storage_key: str, size_bytes: int = 0) -> dict[str, Any]:
        return self._post(
            "/internal/object-blobs/get-or-create",
            {"content_hash": content_hash, "storage_key": storage_key, "size_bytes": size_bytes},
        )

class DocumentServiceClient:
    """HTTP facade for the document-service owner."""

    def __init__(self, session=None) -> None:
        self._remote: _RemoteDocumentService | None = None

    def _get_remote(self) -> _RemoteDocumentService:
        if self._remote is None:
            self._remote = _RemoteDocumentService()
        return self._remote

    def create_source_file(
        self,
        collection_id: str,
        object_id: str,
        content_hash: str,
    ) -> dict[str, Any]:
        return self._get_remote().create_source_file(collection_id, object_id, content_hash)

    def claim(self, source_file_id: str, job_id: str) -> bool:
        return self._get_remote().claim(source_file_id, job_id)

    def mark_consumed(self, source_file_id: str, job_id: str) -> bool:
        return self._get_remote().mark_consumed(source_file_id, job_id)

    def mark_cleanable(self, source_file_id: str, job_id: str) -> bool:
        return self._get_remote().mark_cleanable(source_file_id, job_id)

    def find_active_by_content_hash(self, content_hash: str, collection_id: str) -> dict[str, Any] | None:
        return self._get_remote().find_active_by_content_hash(content_hash, collection_id)

    def get_object_blob(self, object_id: str) -> dict[str, Any] | None:
        return self._get_remote().get_object_blob(object_id)

    def get_or_create_object_blob(self, content_hash: str, storage_key: str, size_bytes: int = 0) -> dict[str, Any]:
        return self._get_remote().get_or_create_object_blob(content_hash, storage_key, size_bytes)
