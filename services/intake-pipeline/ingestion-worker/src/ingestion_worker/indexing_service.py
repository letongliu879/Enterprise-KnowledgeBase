"""Indexing service — remote-or-local fallback selector.

If INDEXING_SERVICE_URL is set, HTTP calls are forwarded to the remote
indexing-service process.  Otherwise the local same-process IndexingService
is used.  This lets the monolith run standalone while allowing gradual
splitting of the indexing owner into its own deployable unit.

API contract (request/response models) is unchanged.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from reality_rag_contracts import (
    IndexJobRequest,
    IndexJobResult,
    IndexSwitchRequest,
    IndexSwitchResult,
)
from reality_rag_indexing import (
    IndexBuildInput,
    IndexBuildOutput,
    IndexJobError,
    IndexingService,
    PerDocumentIndexResult,
)

__all__ = [
    "IndexBuildInput",
    "IndexBuildOutput",
    "IndexJobError",
    "IndexingService",
    "PerDocumentIndexResult",
    "get_indexing_service",
]

_REMOTE_URL: str | None = None


def _get_remote_url() -> str | None:
    global _REMOTE_URL
    if _REMOTE_URL is None:
        _REMOTE_URL = os.environ.get("INDEXING_SERVICE_URL", "").rstrip("/") or None
    return _REMOTE_URL


def _url(path: str) -> str:
    base = _get_remote_url()
    assert base is not None
    return f"{base}{path}"


class _RemoteIndexingService:
    """HTTP client facade that mirrors IndexingService API."""

    async def run(self, request: IndexJobRequest) -> IndexJobResult:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                _url("/internal/indexing/run"),
                json=request.model_dump(mode="json"),
            )
            if resp.status_code >= 400:
                raise IndexJobError(resp.text)
            return IndexJobResult.model_validate(resp.json())

    def activate(self, collection_id: str, index_version: str | None = None) -> IndexSwitchResult:
        req = IndexSwitchRequest(
            collection_id=collection_id,
            index_version=index_version,
        )
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self._activate_async(req))

    async def _activate_async(self, request: IndexSwitchRequest) -> IndexSwitchResult:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _url("/internal/indexing/activate"),
                json=request.model_dump(mode="json"),
            )
            if resp.status_code >= 400:
                raise IndexJobError(resp.text)
            return IndexSwitchResult.model_validate(resp.json())

    def rollback(self, collection_id: str, index_version: str | None = None) -> IndexSwitchResult:
        req = IndexSwitchRequest(
            collection_id=collection_id,
            index_version=index_version,
        )
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self._rollback_async(req))

    async def _rollback_async(self, request: IndexSwitchRequest) -> IndexSwitchResult:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _url("/internal/indexing/rollback"),
                json=request.model_dump(mode="json"),
            )
            if resp.status_code >= 400:
                raise IndexJobError(resp.text)
            return IndexSwitchResult.model_validate(resp.json())


class _FallbackIndexingService:
    """Dispatches to remote HTTP when INDEXING_SERVICE_URL is set,
    otherwise delegates to the local same-process IndexingService.
    """

    def __init__(self) -> None:
        self._local = IndexingService()
        self._remote: _RemoteIndexingService | None = None

    def _use_remote(self) -> bool:
        return _get_remote_url() is not None

    def _get_remote(self) -> _RemoteIndexingService:
        if self._remote is None:
            self._remote = _RemoteIndexingService()
        return self._remote

    async def run(self, request: IndexJobRequest) -> IndexJobResult:
        if self._use_remote():
            return await self._get_remote().run(request)
        return await self._local.run(request)

    def activate(self, collection_id: str, index_version: str | None = None) -> IndexSwitchResult:
        if self._use_remote():
            return self._get_remote().activate(collection_id, index_version)
        return self._local.activate(collection_id, index_version)

    def rollback(self, collection_id: str, index_version: str | None = None) -> IndexSwitchResult:
        if self._use_remote():
            return self._get_remote().rollback(collection_id, index_version)
        return self._local.rollback(collection_id, index_version)


# Singleton for ingestion-worker main.py
_fallback_svc: _FallbackIndexingService | None = None


def get_indexing_service() -> _FallbackIndexingService:
    """Return the indexing service facade (remote or local)."""
    global _fallback_svc
    if _fallback_svc is None:
        _fallback_svc = _FallbackIndexingService()
    return _fallback_svc
