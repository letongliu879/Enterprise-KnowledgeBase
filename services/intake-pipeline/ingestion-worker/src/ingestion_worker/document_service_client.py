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


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = httpx.post(_url(path), json=payload, timeout=30.0)
    if resp.status_code >= 400:
        raise RuntimeError(resp.text)
    return resp.json()


class DocumentServiceClient:
    """HTTP facade for the document-service owner.

    The ``session`` parameter is accepted for backward compatibility with
callers that pass a database session, but it is intentionally unused because
all calls go through the remote HTTP API.
    """

    def __init__(self, session=None) -> None:
        pass

    def create_source_file(
        self,
        collection_id: str,
        object_id: str,
        content_hash: str,
    ) -> dict[str, Any]:
        return _post(
            "/internal/source-files",
            {
                "collection_id": collection_id,
                "object_id": object_id,
                "content_hash": content_hash,
            },
        )

    def claim(self, source_file_id: str, job_id: str) -> bool:
        result = _post(
            f"/internal/source-files/{source_file_id}/claim",
            {"job_id": job_id},
        )
        return result.get("claimed", False)

    def mark_consumed(self, source_file_id: str, job_id: str) -> bool:
        result = _post(
            f"/internal/source-files/{source_file_id}/mark-consumed",
            {"job_id": job_id},
        )
        return result.get("consumed", False)

    def mark_cleanable(self, source_file_id: str, job_id: str) -> bool:
        result = _post(
            f"/internal/source-files/{source_file_id}/mark-cleanable",
            {"job_id": job_id},
        )
        return result.get("cleanable", False)

    def find_active_by_content_hash(self, content_hash: str, collection_id: str) -> dict[str, Any] | None:
        # document-service doesn't expose a direct find_active endpoint;
        # use dedup-check as a proxy for active source file detection
        result = _post(
            "/internal/dedup-check",
            {"content_hash": content_hash, "collection_id": collection_id},
        )
        # dedup-check returns is_duplicate + existing_doc_id;
        # if is_duplicate but no doc_id, it's an active source file
        if result.get("is_duplicate") and result.get("existing_doc_id") is None:
            return {
                "source_file_id": result.get("source_file_id"),
                "content_hash": content_hash,
                "collection_id": collection_id,
            }
        return None

    def get_object_blob(self, object_id: str) -> dict[str, Any] | None:
        return None

    def get_or_create_object_blob(self, content_hash: str, storage_key: str, size_bytes: int = 0) -> dict[str, Any]:
        return _post(
            "/internal/object-blobs/get-or-create",
            {"content_hash": content_hash, "storage_key": storage_key, "size_bytes": size_bytes},
        )
