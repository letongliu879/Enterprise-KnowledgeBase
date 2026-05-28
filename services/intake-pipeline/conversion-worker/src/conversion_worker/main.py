"""FastAPI application for the Conversion Worker.

This service owns:
  - File format conversion to canonical markdown
  - Content dedup (via injected lookup hints)
  - Version assignment
  - Quality assessment
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from reality_rag_contracts import HealthResponse
from reality_rag_persistence.database import get_session
from reality_rag_persistence.outbox import OutboxDispatcher

from ingestion_worker.stages.schemas import ConversionStageInput, ConversionStageOutput
from ingestion_worker.stages.pure_stages import run_conversion_stage
from ingestion_worker.converters.ragflow_converter import RAGFlowConverter
from ingestion_worker.stage_runtime import execute_conversion_task
from ingestion_worker.stage_task_worker import make_stage_task_deliver, make_stage_task_filter
from reality_rag_contracts import StageName

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Conversion Worker",
    description="File conversion, dedup, versioning, and quality assessment for Reality-RAG",
    version="0.1.0",
)

# Service-local converter instance
_converter = RAGFlowConverter()
_outbox_dispatcher_task: asyncio.Task[None] | None = None


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="conversion-worker",
        version="0.1.0",
    )


class ConversionRunRequest(BaseModel):
    intake_job_id: str = ""
    collection_id: str = ""
    source_file_path: str = ""
    tenant_id: str = "default"
    collection_authority_level: int = 0
    index_version: str = "v1"
    existing_published_doc_id_by_source_hash: str | None = None
    latest_version_by_logical_id: int | None = None


@app.post("/internal/conversion/run")
async def run_conversion(request: ConversionRunRequest) -> dict:
    try:
        inp = ConversionStageInput(
            schema_version="v1",
            intake_job_id=request.intake_job_id,
            collection_id=request.collection_id,
            source_file_path=request.source_file_path,
            tenant_id=request.tenant_id,
            collection_authority_level=request.collection_authority_level,
            index_version=request.index_version,
            existing_published_doc_id_by_source_hash=request.existing_published_doc_id_by_source_hash,
            latest_version_by_logical_id=request.latest_version_by_logical_id,
        )
        out = run_conversion_stage(inp, [_converter])
        return {
            "schema_version": out.schema_version,
            "input_hash": out.input_hash,
            "result_hash": out.result_hash,
            "conversion_status": out.conversion_result.conversion_status.value if out.conversion_result else None,
            "preliminary_doc_id": out.preliminary_doc_id,
            "logical_document_id": out.logical_document_id,
            "version": out.version,
            "dedup_skipped": out.dedup_skipped,
            "skip_reason": out.skip_reason,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class _ConversionPipeline:
    def __init__(self) -> None:
        self._converters = [_converter]


async def _outbox_poll_loop() -> None:
    dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_stage_task_deliver(
            stage_name=StageName.CONVERSION,
            consumer_id="conversion-worker:stage-task",
            worker_id="worker-conversion",
            execute=lambda session, stage_task_id, intake_job_id, worker_id: execute_conversion_task(
                session,
                stage_task_id,
                intake_job_id,
                _ConversionPipeline(),
                worker_id,
            ),
        ),
        should_process=make_stage_task_filter(StageName.CONVERSION),
    )
    interval = float(os.environ.get("OUTBOX_POLL_INTERVAL_SECONDS", "5"))
    while True:
        try:
            dispatcher.poll_and_dispatch()
        except Exception:
            logger.exception("conversion outbox poll failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _outbox_dispatcher_task
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


app.router.lifespan_context = _lifespan
