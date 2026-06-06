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

from fastapi import FastAPI

from reality_rag_persistence.database import get_session
from reality_rag_persistence.outbox import OutboxDispatcher

from intake_runtime.agent_reviewer import get_agent_reviewer
from intake_runtime.agent_review_cache import get_agent_review_cache
from intake_runtime.stage_runtime import execute_review_task
from intake_runtime.stage_task_worker import make_stage_task_deliver, make_stage_task_filter
from reality_rag_contracts import StageName

from agent_review_worker.routes import router

logger = logging.getLogger(__name__)
_outbox_dispatcher_task: asyncio.Task[None] | None = None


async def _outbox_poll_loop() -> None:
    class _ReviewPipeline:
        def __init__(self) -> None:
            self._agent_reviewer = get_agent_reviewer()
            self._agent_review_cache = get_agent_review_cache()

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
