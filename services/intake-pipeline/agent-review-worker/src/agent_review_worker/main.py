"""FastAPI application for the Agent Review Worker.

This service owns:
  - PII span detection
  - Visibility risk fact generation
  - Agent review result persistence
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

from reality_rag_contracts import HealthResponse, StageName
from reality_rag_persistence.database import get_session
from reality_rag_persistence.outbox import OutboxDispatcher

from intake_runtime.stages.schemas import ReviewStageInput, ReviewStageOutput
from intake_runtime.stages.pure_stages import run_review_stage
from intake_runtime.agent_review_cache import get_agent_review_cache
from intake_runtime.agent_reviewer import get_agent_reviewer, AgentReviewConfigurationError
from intake_runtime.stage_runtime import execute_review_task
from intake_runtime.stage_task_worker import make_stage_task_deliver, make_stage_task_filter

logger = logging.getLogger(__name__)
_outbox_dispatcher_task: asyncio.Task[None] | None = None
router = APIRouter()


class ReviewRunRequest(BaseModel):
    intake_job_id: str = ""
    collection_id: str = ""
    preliminary_doc_id: str = ""
    logical_document_id: str = ""
    canonical_content: str = ""
    collection_authority_level: int = 0
    review_model: str = ""

class _ReviewPipeline:
    def __init__(self) -> None:
        self._agent_reviewer = get_agent_reviewer()
        self._agent_review_cache = get_agent_review_cache()


async def _outbox_poll_loop() -> None:
    dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_stage_task_deliver(
            stage_name=StageName.AGENT_REVIEW,
            consumer_id="agent-review-worker:stage-task",
            worker_id="worker-agent-review",
            execute=lambda session, stage_task_id, intake_job_id, worker_id: execute_review_task(
                session,
                stage_task_id,
                intake_job_id,
                _ReviewPipeline(),
                worker_id,
            ),
        ),
        should_process=make_stage_task_filter(StageName.AGENT_REVIEW),
    )
    interval = float(os.environ.get("OUTBOX_POLL_INTERVAL_SECONDS", "5"))
    while True:
        try:
            dispatcher.poll_and_dispatch()
        except Exception:
            logger.exception("agent review outbox poll failed")
        await asyncio.sleep(interval)


def _build_lifespan(*, start_background_poller: bool):
    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        global _outbox_dispatcher_task
        if not start_background_poller:
            yield
            return

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


def create_app(*, start_background_poller: bool = True) -> FastAPI:
    app = FastAPI(
        title="Agent Review Worker",
        description="PII detection and LLM risk review for Reality-RAG",
        version="0.1.0",
        lifespan=_build_lifespan(start_background_poller=start_background_poller),
    )
    app.include_router(router)
    return app


app = create_app()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="agent-review-worker",
        version="0.1.0",
    )


@router.post("/internal/review/run")
async def run_review(request: ReviewRunRequest) -> dict:
    try:
        inp = ReviewStageInput(
            schema_version="v1",
            intake_job_id=request.intake_job_id,
            collection_id=request.collection_id,
            preliminary_doc_id=request.preliminary_doc_id,
            logical_document_id=request.logical_document_id,
            canonical_content=request.canonical_content,
            collection_authority_level=request.collection_authority_level,
            review_model=request.review_model,
        )
        reviewer = get_agent_reviewer()
        cache = get_agent_review_cache()
        out = run_review_stage(inp, reviewer, cache)
        return {
            "schema_version": out.schema_version,
            "input_hash": out.input_hash,
            "result_hash": out.result_hash,
            "decision": out.agent_review.decision.value if out.agent_review and out.agent_review.decision else None,
            "confidence": out.agent_review.confidence if out.agent_review else None,
            "cache_hit": out.cache_hit,
            "llm_call_records": out.review_context.get("llm_call_records", []),
        }
    except AgentReviewConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
