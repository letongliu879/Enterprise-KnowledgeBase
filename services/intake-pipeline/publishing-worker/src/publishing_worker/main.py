"""FastAPI application for the Publishing Worker.

This service owns:
  - Document persistence
  - DocumentPolicy persistence
  - Asset write (sidecar)
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from reality_rag_contracts import CanonicalMetadata, HealthResponse, StageName
from reality_rag_persistence.database import get_session
from reality_rag_persistence.outbox import OutboxDispatcher

from ingestion_worker.stage_runtime import execute_publishing_task
from ingestion_worker.stage_task_worker import make_stage_task_deliver, make_stage_task_filter
from .publishing_domain import PublishingService

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Publishing Worker",
    description="Document and policy persistence for Reality-RAG",
    version="0.1.0",
)
_outbox_dispatcher_task: asyncio.Task[None] | None = None


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="publishing-worker",
        version="0.1.0",
    )


# ── Persist Document and Policy ───────────────────────────────────────

class PersistRequest(BaseModel):
    canonical_metadata: dict
    collection_authority_level: int = 0


@app.post("/internal/publishing/persist")
async def persist(request: PersistRequest) -> dict:
    try:
        metadata = CanonicalMetadata.model_validate(request.canonical_metadata)
        svc = PublishingService()
        document_persisted, policy_persisted = svc.persist(
            metadata,
            collection_authority_level=request.collection_authority_level,
        )
        return {
            "document_persisted": document_persisted,
            "policy_persisted": policy_persisted,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _outbox_poll_loop() -> None:
    dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_stage_task_deliver(
            stage_name=StageName.PUBLISHING,
            consumer_id="publishing-worker:stage-task",
            worker_id="worker-publishing",
            execute=execute_publishing_task,
        ),
        should_process=make_stage_task_filter(StageName.PUBLISHING),
    )
    interval = float(os.environ.get("OUTBOX_POLL_INTERVAL_SECONDS", "5"))
    while True:
        try:
            dispatcher.poll_and_dispatch()
        except Exception:
            logger.exception("publishing outbox poll failed")
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
