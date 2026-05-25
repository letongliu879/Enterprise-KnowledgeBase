"""MonitoredIngestionService — thin orchestration layer."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from reality_rag_persistence.ingestion_monitor import IngestionMonitorStore

from .indexing_service import IndexingService
from .monitor_context import MonitorContext
from .monitor_models import MonitorRunDetail, MonitorRunRequest, MonitorRunSummary
from .monitor_processor import MonitorProcessor
from .pipeline import IngestionPipeline


class MonitoredIngestionService:
    """Orchestrate ingestion runs with monitoring and lane-based concurrency."""

    def __init__(
        self,
        *,
        pipeline: IngestionPipeline,
        indexing_service: IndexingService,
        store: IngestionMonitorStore | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._indexing_service = indexing_service
        self._store = store or IngestionMonitorStore()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._processor = MonitorProcessor(
            pipeline=pipeline,
            indexing_service=indexing_service,
            store=self._store,
        )

    def start(self, request: MonitorRunRequest) -> MonitorRunSummary:
        run_id = f"monitor-{uuid4().hex[:8]}"
        index_version = request.index_version or f"{request.collection_id}-v1"
        run = self._store.create_run(
            run_id=run_id,
            collection_id=request.collection_id,
            index_version=index_version,
            concurrency=request.concurrency,
            source_files=request.source_files,
        )
        self._store.append_event(
            run_id,
            lane_id=-1,
            event_type="run.started",
            phase="run",
            message=(
                f"Started monitored ingestion for {len(request.source_files)} files "
                f"with concurrency={request.concurrency}"
            ),
            payload={
                "collection_id": request.collection_id,
                "index_version": index_version,
                "total_files": len(request.source_files),
            },
        )
        task = asyncio.create_task(self._run_batch(run_id, request, index_version))
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run_id, None))
        return MonitorRunSummary.model_validate(run)

    def list_runs(self) -> list[MonitorRunSummary]:
        return [MonitorRunSummary.model_validate(run) for run in self._store.list_runs()]

    def get_run(self, run_id: str) -> MonitorRunDetail | None:
        run = self._store.get_run(run_id)
        if run is None:
            return None
        payload = dict(run)
        payload["events"] = self._store.get_events(run_id)
        return MonitorRunDetail.model_validate(payload)

    def get_store(self) -> IngestionMonitorStore:
        return self._store

    async def _run_batch(self, run_id: str, request: MonitorRunRequest, index_version: str) -> None:
        self._store.update_run(run_id, status="running")
        queue: asyncio.Queue[str] = asyncio.Queue()
        for source_file in request.source_files:
            queue.put_nowait(source_file)

        try:
            workers = [
                asyncio.create_task(
                    self._lane_worker(
                        run_id=run_id,
                        lane_id=lane_id,
                        queue=queue,
                        collection_id=request.collection_id,
                        index_version=index_version,
                    )
                )
                for lane_id in range(request.concurrency)
            ]
            await asyncio.gather(*workers)
            run = self._store.get_run(run_id) or {}
            self._store.update_run(
                run_id,
                status="completed",
                processed_files=run.get("processed_files", 0),
            )
            self._store.append_event(
                run_id,
                lane_id=-1,
                event_type="run.completed",
                phase="run",
                message="Monitored ingestion run completed",
                payload=self._store.get_run(run_id) or {},
            )
        except Exception as exc:
            self._store.update_run(run_id, status="failed")
            self._store.append_event(
                run_id,
                lane_id=-1,
                event_type="run.failed",
                phase="run",
                message=f"Monitored ingestion run failed: {exc}",
                level="error",
                payload={"error": str(exc)},
            )
            raise

    async def _lane_worker(
        self,
        *,
        run_id: str,
        lane_id: int,
        queue: asyncio.Queue[str],
        collection_id: str,
        index_version: str,
    ) -> None:
        while True:
            try:
                source_file_path = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            context = MonitorContext(
                run_id=run_id,
                lane_id=lane_id,
                source_file_path=source_file_path,
                store=self._store,
            )
            try:
                await self._processor.process_one(
                    context=context,
                    collection_id=collection_id,
                    index_version=index_version,
                )
            finally:
                queue.task_done()
