"""FastAPI application for the Indexing Service.

This service owns:
  - chunking / embedding
  - vector index upsert
  - index activate / rollback
  - outbox: IndexReady

API contract is identical to the former ingestion-worker indexing endpoints
so that ingestion-worker can forward requests here when INDEXING_SERVICE_URL
is set.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from reality_rag_contracts import (
    HealthResponse,
    IndexJobRequest,
    IndexJobResult,
    IndexSwitchRequest,
    IndexSwitchResult,
)

_indexing_service: Any | None = None


def _load_runtime():
    from reality_rag_indexing import IndexJobError, IndexingService, get_index_backend

    return IndexJobError, IndexingService, get_index_backend


def get_indexing_service():
    global _indexing_service
    if _indexing_service is None:
        _, IndexingService, _ = _load_runtime()
        _indexing_service = IndexingService()
    return _indexing_service


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if os.environ.get("APP_ENV", "development").lower() == "production":
        _, _, get_index_backend = _load_runtime()
        get_index_backend()
    yield


app = FastAPI(
    title="Indexing Service",
    description="Chunking, embedding, and hybrid index management for Reality-RAG",
    version="0.1.0",
    lifespan=_lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="indexing-service",
        version="0.1.0",
    )


@app.post("/internal/indexing/run", response_model=IndexJobResult)
async def run_index_job(request: IndexJobRequest) -> IndexJobResult:
    try:
        return await get_indexing_service().run(request)
    except Exception as exc:
        IndexJobError, _, _ = _load_runtime()
        if not isinstance(exc, IndexJobError):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/internal/indexing/activate", response_model=IndexSwitchResult)
async def activate_index(request: IndexSwitchRequest) -> IndexSwitchResult:
    try:
        return get_indexing_service().activate(
            request.collection_id,
            request.index_version,
        )
    except Exception as exc:
        IndexJobError, _, _ = _load_runtime()
        if not isinstance(exc, IndexJobError):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/internal/indexing/rollback", response_model=IndexSwitchResult)
async def rollback_index(request: IndexSwitchRequest) -> IndexSwitchResult:
    try:
        return get_indexing_service().rollback(
            request.collection_id,
            request.index_version,
        )
    except Exception as exc:
        IndexJobError, _, _ = _load_runtime()
        if not isinstance(exc, IndexJobError):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc
