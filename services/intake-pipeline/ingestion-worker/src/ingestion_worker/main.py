"""FastAPI application for the Ingestion Worker."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from reality_rag_persistence.outbox import OutboxDispatcher
from reality_rag_persistence.database import get_session

from reality_rag_contracts import (
    ConversionRequest,
    HealthResponse,
    IngestionJob,
    IndexJobRequest,
    IndexJobResult,
    IndexSwitchRequest,
    IndexSwitchResult,
)
from reality_rag_persistence.metrics import intake_metrics
from reality_rag_persistence.telemetry import TelemetryStore

from .agent_reviewer import AgentReviewError
from .converters.ragflow_converter import RAGFlowConverter
from .indexing_service import get_indexing_service, IndexJobError
from .monitoring import MonitorRunRequest, MonitorRunSummary, MonitoredIngestionService
from .outbox_deliver import make_deliver_callback
from .pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

_converter = RAGFlowConverter()
_pipeline: IngestionPipeline | None = None
_monitored_ingestion_service: MonitoredIngestionService | None = None
_outbox_dispatcher_task: asyncio.Task[None] | None = None


async def _outbox_poll_loop() -> None:
    """Background task that periodically polls and dispatches outbox events."""
    dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_deliver_callback(),
        should_process=lambda event: event.event_type != "StageTaskRequested",
    )
    interval = float(os.environ.get("OUTBOX_POLL_INTERVAL_SECONDS", "5"))
    while True:
        try:
            dispatched = dispatcher.poll_and_dispatch()
            if dispatched > 0:
                logger.debug("outbox: dispatched %d events", dispatched)
        except Exception:
            logger.exception("outbox: poll_and_dispatch failed")
        await asyncio.sleep(interval)


def get_pipeline() -> IngestionPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = IngestionPipeline(
            converters=[_converter],
            telemetry_store=TelemetryStore(),
        )
    return _pipeline


def get_monitored_ingestion_service() -> MonitoredIngestionService:
    global _monitored_ingestion_service
    if _monitored_ingestion_service is None:
        _monitored_ingestion_service = MonitoredIngestionService(
            pipeline=get_pipeline(),
            indexing_service=get_indexing_service(),
        )
    return _monitored_ingestion_service


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _outbox_dispatcher_task
    # Phase 7: Start outbox dispatcher background poller
    _outbox_dispatcher_task = asyncio.create_task(_outbox_poll_loop())
    try:
        yield
    finally:
        if _outbox_dispatcher_task is not None:
            _outbox_dispatcher_task.cancel()
            try:
                await _outbox_dispatcher_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Ingestion Worker",
    description="Knowledge ingestion service for canonical markdown conversion and hybrid indexing",
    version="0.1.0",
    lifespan=_lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="ingestion-worker", version="0.1.0")


@app.get("/metrics")
async def metrics() -> Response:
    body, content_type = intake_metrics.metrics_response()
    return Response(content=body, media_type=content_type)


@app.post("/internal/ingestion/convert", response_model=IngestionJob)
async def convert(request: ConversionRequest) -> IngestionJob:
    try:
        return get_pipeline().run(
            collection_id=request.collection_id,
            source_files=[request.source_file_path],
        )
    except AgentReviewError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/internal/ingestion/monitor/runs", response_model=MonitorRunSummary)
async def start_monitored_run(request: MonitorRunRequest) -> MonitorRunSummary:
    try:
        return get_monitored_ingestion_service().start(request)
    except AgentReviewError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
