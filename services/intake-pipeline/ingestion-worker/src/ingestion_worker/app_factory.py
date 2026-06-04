"""Application factory for the ingestion worker."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Response

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

logger = logging.getLogger(__name__)

_pipeline: Any | None = None
_indexing_service: Any | None = None
_outbox_dispatcher_task: asyncio.Task[None] | None = None


def _default_pipeline_factory():
    from intake_runtime.converters.ragflow_converter import RAGFlowConverter
    from reality_rag_persistence.telemetry import TelemetryStore

    from .pipeline import IngestionPipeline

    return IngestionPipeline(
        converters=[RAGFlowConverter()],
        telemetry_store=TelemetryStore(),
    )


def _default_indexing_service_factory():
    from .indexing_service import get_indexing_service

    return get_indexing_service()


def _get_pipeline_for_app(app: FastAPI):
    pipeline = getattr(app.state, "pipeline_instance", None)
    if pipeline is None:
        pipeline = app.state.pipeline_factory()
        app.state.pipeline_instance = pipeline
    return pipeline


def _get_indexing_service_for_app(app: FastAPI):
    indexing_service = getattr(app.state, "indexing_service_instance", None)
    if indexing_service is None:
        indexing_service = app.state.indexing_service_factory()
        app.state.indexing_service_instance = indexing_service
    return indexing_service


def _build_lifespan(*, start_background_poller: bool):
    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        global _outbox_dispatcher_task
        if not start_background_poller:
            yield
            return

        from reality_rag_persistence.database import get_session
        from reality_rag_persistence.outbox import OutboxDispatcher

        from .outbox_deliver import make_deliver_callback

        async def _outbox_poll_loop() -> None:
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
                _outbox_dispatcher_task = None

    return _lifespan


def create_app(
    *,
    pipeline_factory: Callable[[], Any] | None = None,
    indexing_service_factory: Callable[[], Any] | None = None,
    include_indexing_routes: bool = True,
    start_background_poller: bool = True,
) -> FastAPI:
    app = FastAPI(
        title="Ingestion Worker",
        description="Knowledge ingestion service for canonical markdown conversion and hybrid indexing",
        version="0.1.0",
        lifespan=_build_lifespan(start_background_poller=start_background_poller),
    )

    app.state.pipeline_factory = pipeline_factory or _default_pipeline_factory
    app.state.indexing_service_factory = indexing_service_factory or _default_indexing_service_factory
    app.state.pipeline_instance = None
    app.state.indexing_service_instance = None

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="ingestion-worker", version="0.1.0")

    @app.get("/metrics")
    async def metrics() -> Response:
        body, content_type = intake_metrics.metrics_response()
        return Response(content=body, media_type=content_type)

    @app.post("/internal/ingestion/convert", response_model=IngestionJob)
    async def convert(request: ConversionRequest) -> IngestionJob:
        from intake_runtime.agent_reviewer import AgentReviewError

        try:
            return _get_pipeline_for_app(app).run(
                collection_id=request.collection_id,
                source_files=[request.source_file_path],
            )
        except AgentReviewError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/internal/intake-jobs/{job_id}")
    async def get_intake_job(job_id: str) -> dict:
        from reality_rag_persistence.database import get_session
        from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository

        session = get_session()
        try:
            repo = IntakeJobRepository(session)
            job = repo.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail=f"Intake job {job_id} not found")
            return job.model_dump(mode="json")
        finally:
            session.close()

    if include_indexing_routes:
        @app.post("/internal/indexing/run", response_model=IndexJobResult)
        async def run_index_job(request: IndexJobRequest) -> IndexJobResult:
            from .indexing_service import IndexJobError

            try:
                return await _get_indexing_service_for_app(app).run(request)
            except IndexJobError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/internal/indexing/activate", response_model=IndexSwitchResult)
        async def activate_index(request: IndexSwitchRequest) -> IndexSwitchResult:
            from .indexing_service import IndexJobError

            try:
                return await _get_indexing_service_for_app(app).activate(
                    request.collection_id,
                    request.index_version,
                )
            except IndexJobError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/internal/indexing/rollback", response_model=IndexSwitchResult)
        async def rollback_index(request: IndexSwitchRequest) -> IndexSwitchResult:
            from .indexing_service import IndexJobError

            try:
                return await _get_indexing_service_for_app(app).rollback(
                    request.collection_id,
                    request.index_version,
                )
            except IndexJobError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def bind_default_runtime_app(app: FastAPI):
    global _pipeline, _indexing_service

    def get_pipeline():
        nonlocal app
        global _pipeline
        _pipeline = _get_pipeline_for_app(app)
        return _pipeline

    def get_indexing_service():
        nonlocal app
        global _indexing_service
        _indexing_service = _get_indexing_service_for_app(app)
        return _indexing_service

    return get_pipeline, get_indexing_service
