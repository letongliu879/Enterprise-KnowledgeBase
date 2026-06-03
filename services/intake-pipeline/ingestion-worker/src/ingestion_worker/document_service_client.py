"""Document service client facade.

`document-service` is the source-file owner. `ingestion-worker` may use a
same-process fallback only in tests or explicit compat smoke.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .split_service_policy import require_explicit_owner_url

__all__ = [
    "DocumentServiceClient",
    "get_document_service_client",
]

_REMOTE_URL: str | None = None


def _get_remote_url() -> str | None:
    global _REMOTE_URL
    if _REMOTE_URL is None:
        _REMOTE_URL = os.environ.get("DOCUMENT_SERVICE_URL", "").rstrip("/") or None
    return _REMOTE_URL


def _url(path: str) -> str:
    base = _get_remote_url()
    assert base is not None
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


class _LocalDocumentService:
    """Local same-process DocumentService wrapper."""

    def __init__(self, session=None) -> None:
        self._session = session

    def _get_session(self):
        if self._session is not None:
            return self._session
        from reality_rag_persistence.database import get_session

        return get_session()

    def create_source_file(
        self,
        collection_id: str,
        object_id: str,
        content_hash: str,
    ) -> dict[str, Any]:
        from reality_rag_documents import DocumentService

        session = self._get_session()
        svc = DocumentService(session)
        sf = svc.create_source_file(
            collection_id=collection_id,
            object_id=object_id,
            content_hash=content_hash,
        )
        return {
            "source_file_id": sf.source_file_id,
            "collection_id": sf.collection_id,
            "object_id": sf.object_id,
            "content_hash": sf.content_hash,
            "state": sf.state.value if hasattr(sf.state, "value") else str(sf.state),
        }

    def claim(self, source_file_id: str, job_id: str) -> bool:
        from reality_rag_documents import DocumentService

        session = self._get_session()
        svc = DocumentService(session)
        return svc.claim_source_file(source_file_id, job_id)

    def mark_consumed(self, source_file_id: str, job_id: str) -> bool:
        from reality_rag_documents import DocumentService

        session = self._get_session()
        svc = DocumentService(session)
        return svc.mark_consumed(source_file_id, job_id)

    def mark_cleanable(self, source_file_id: str, job_id: str) -> bool:
        from reality_rag_documents import DocumentService

        session = self._get_session()
        svc = DocumentService(session)
        return svc.mark_cleanable(source_file_id, job_id)

    def find_active_by_content_hash(self, content_hash: str, collection_id: str) -> dict[str, Any] | None:
        from reality_rag_persistence.repositories.source_files import SourceFileRepository

        session = self._get_session()
        repo = SourceFileRepository(session)
        sf = repo.find_active_by_content_hash(content_hash, collection_id)
        if sf is None:
            return None
        return {
            "source_file_id": sf.source_file_id,
            "collection_id": sf.collection_id,
            "object_id": sf.object_id,
            "content_hash": sf.content_hash,
            "state": sf.state.value if hasattr(sf.state, "value") else str(sf.state),
        }

    def get_object_blob(self, object_id: str) -> dict[str, Any] | None:
        from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository

        session = self._get_session()
        obj = ObjectBlobRepository(session).get(object_id)
        if obj is None:
            return None
        return {
            "object_id": obj.object_id,
            "content_hash": obj.content_hash,
            "storage_key": obj.storage_key,
            "ref_count": obj.ref_count,
            "status": obj.status,
            "size_bytes": obj.size_bytes,
        }

    def get_or_create_object_blob(self, content_hash: str, storage_key: str, size_bytes: int = 0) -> dict[str, Any]:
        from reality_rag_documents import DocumentService

        session = self._get_session()
        svc = DocumentService(session)
        obj = svc.get_or_create_object_blob(content_hash, storage_key, size_bytes)
        return {
            "object_id": obj.object_id,
            "content_hash": obj.content_hash,
            "storage_key": obj.storage_key,
            "ref_count": obj.ref_count,
            "status": obj.status,
        }


class DocumentServiceClient:
    """Dispatches to remote HTTP or, only in tests, a local compat fallback."""

    def __init__(self, session=None) -> None:
        self._session = session
        self._local: _LocalDocumentService | None = None
        self._remote: _RemoteDocumentService | None = None

    def _use_remote(self) -> bool:
        return _get_remote_url() is not None

    def _get_local(self) -> _LocalDocumentService:
        if self._local is None:
            require_explicit_owner_url(
                env_var="DOCUMENT_SERVICE_URL",
                owner_name="document-service",
            )
            self._local = _LocalDocumentService(self._session)
        return self._local

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
        if self._use_remote():
            return self._get_remote().create_source_file(collection_id, object_id, content_hash)
        return self._get_local().create_source_file(collection_id, object_id, content_hash)

    def claim(self, source_file_id: str, job_id: str) -> bool:
        if self._use_remote():
            return self._get_remote().claim(source_file_id, job_id)
        return self._get_local().claim(source_file_id, job_id)

    def mark_consumed(self, source_file_id: str, job_id: str) -> bool:
        if self._use_remote():
            return self._get_remote().mark_consumed(source_file_id, job_id)
        return self._get_local().mark_consumed(source_file_id, job_id)

    def mark_cleanable(self, source_file_id: str, job_id: str) -> bool:
        if self._use_remote():
            return self._get_remote().mark_cleanable(source_file_id, job_id)
        return self._get_local().mark_cleanable(source_file_id, job_id)

    def find_active_by_content_hash(self, content_hash: str, collection_id: str) -> dict[str, Any] | None:
        if self._use_remote():
            return self._get_remote().find_active_by_content_hash(content_hash, collection_id)
        return self._get_local().find_active_by_content_hash(content_hash, collection_id)

    def get_object_blob(self, object_id: str) -> dict[str, Any] | None:
        if self._use_remote():
            return self._get_remote().get_object_blob(object_id)
        return self._get_local().get_object_blob(object_id)

    def get_or_create_object_blob(self, content_hash: str, storage_key: str, size_bytes: int = 0) -> dict[str, Any]:
        if self._use_remote():
            return self._get_remote().get_or_create_object_blob(content_hash, storage_key, size_bytes)
        return self._get_local().get_or_create_object_blob(content_hash, storage_key, size_bytes)


# Singleton for ingestion-worker
_fallback_client: DocumentServiceClient | None = None


def get_document_service_client(session=None) -> DocumentServiceClient:
    """Return the document service client facade (remote or local)."""
    global _fallback_client
    if _fallback_client is None:
        _fallback_client = DocumentServiceClient(session)
    return _fallback_client
