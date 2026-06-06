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

from fastapi import FastAPI

from reality_rag_persistence.database import get_session
from reality_rag_persistence.outbox import OutboxDispatcher

from intake_runtime.stage_runtime import execute_conversion_task
from intake_runtime.stage_task_worker import (
    make_stage_task_deliver, make_stage_task_filter, recover_stuck_stage_tasks,
)
from reality_rag_contracts import StageName

from conversion_worker.routes import router

logger = logging.getLogger(__name__)
_outbox_dispatcher_task: asyncio.Task[None] | None = None


async def _outbox_poll_loop() -> None:
    from conversion_worker.routes import _converter

    class _ConversionPipeline:
        def __init__(self) -> None:
            self._converters = [_converter]

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
        try:
            recovered = recover_stuck_stage_tasks(
                StageName.CONVERSION, "worker-conversion",
                lambda session, stage_task_id, intake_job_id, worker_id: execute_conversion_task(
                    session, stage_task_id, intake_job_id, _ConversionPipeline(), worker_id,
                ),
            )
            if recovered > 0:
                logger.info("conversion recovered %d stuck tasks", recovered)
        except Exception:
            logger.exception("conversion stuck task recovery failed")
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
        title="Conversion Worker",
        description="File conversion, dedup, versioning, and quality assessment for Reality-RAG",
        version="0.1.0",
        lifespan=_build_lifespan(start_background_poller=start_background_poller),
    )
    app.include_router(router)
    return app


app = create_app()
