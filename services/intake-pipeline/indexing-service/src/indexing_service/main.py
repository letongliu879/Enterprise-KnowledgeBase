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

from fastapi import FastAPI, HTTPException

from reality_rag_contracts import (
    HealthResponse,
    IndexJobRequest,
    IndexJobResult,
    IndexSwitchRequest,
    IndexSwitchResult,
)
from reality_rag_indexing import IndexJobError, IndexingService

_indexing_service: IndexingService | None = None


def get_indexing_service() -> IndexingService:
    global _indexing_service
    if _indexing_service is None:
        _indexing_service = IndexingService()
    return _indexing_service


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if os.environ.get("APP_ENV", "development").lower() == "production":
        from reality_rag_indexing import get_index_backend
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
    except IndexJobError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/internal/indexing/activate", response_model=IndexSwitchResult)
async def activate_index(request: IndexSwitchRequest) -> IndexSwitchResult:
    try:
        return get_indexing_service().activate(
            request.collection_id,
            request.index_version,
        )
    except IndexJobError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/internal/indexing/rollback", response_model=IndexSwitchResult)
async def rollback_index(request: IndexSwitchRequest) -> IndexSwitchResult:
    try:
        return get_indexing_service().rollback(
            request.collection_id,
            request.index_version,
        )
    except IndexJobError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
