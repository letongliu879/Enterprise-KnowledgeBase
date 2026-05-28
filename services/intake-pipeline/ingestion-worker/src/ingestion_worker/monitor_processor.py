"""Single-file processing logic for monitored ingestion."""

from __future__ import annotations

import asyncio
from pathlib import Path

from reality_rag_contracts import ConversionStatus, IndexJobRequest, IntakeJobState, PublishStatus
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository

from .monitor_context import MonitorContext


def _counters_for_publish_status(status: PublishStatus) -> dict[str, int]:
    if status == PublishStatus.PUBLISHED:
        return {"approved": 1}
    if status == PublishStatus.REJECTED:
        return {"rejected": 1}
    if status == PublishStatus.QUARANTINED:
        return {"quarantined": 1}
    return {"pending_review": 1}


def _counters_for_intake_state(state: str) -> dict[str, int]:
    if state == IntakeJobState.REJECTED.value:
        return {"rejected": 1}
    if state == IntakeJobState.FAILED.value:
        return {"failed": True}
    if state == IntakeJobState.CANCELLED.value:
        return {"failed": True}
    return {"pending_review": 1}


class MonitorProcessor:
    """Process a single file through conversion and indexing."""

    def __init__(self, *, pipeline, indexing_service, store) -> None:
        self._pipeline = pipeline
        self._indexing_service = indexing_service
        self._store = store

    async def process_one(
        self,
        *,
        context: MonitorContext,
        collection_id: str,
        index_version: str,
    ) -> None:
        source_name = Path(context.source_file_path).name

        # De-duplicate: skip if already published
        logical_id = self._pipeline._logical_document_id(context.source_file_path)
        existing_doc = await asyncio.to_thread(self._load_document_by_logical_id, logical_id)
        if existing_doc is not None and existing_doc.publish_status == PublishStatus.PUBLISHED:
            context.emit(
                event_type="doc.duplicate",
                phase="queue",
                message=f"Skipping duplicate: {source_name} already published as {existing_doc.doc_id}",
                payload={"doc_id": existing_doc.doc_id, "source_file_path": context.source_file_path},
            )
            self._bump_run_counts(run_id=context.run_id, approved=1)
            return

        context.emit(
            event_type="lane.assigned",
            phase="queue",
            message=f"Lane {context.lane_id + 1} picked up {source_name}",
            payload={"source_name": source_name},
        )
        try:
            job = await asyncio.to_thread(
                self._pipeline.run,
                collection_id,
                [context.source_file_path],
                context,
            )
            detail = job.conversion_report.details[0] if job.conversion_report and job.conversion_report.details else None
            if detail is None:
                raise RuntimeError("Conversion finished without detail payload")

            if detail.conversion_status != ConversionStatus.SUCCESS:
                self._bump_run_counts(run_id=context.run_id, failed=True)
                context.emit(
                    event_type="doc.failed",
                    phase="conversion",
                    message=f"Conversion failed for {source_name}",
                    level="error",
                    payload={"job_id": job.job_id, "error_message": detail.error_message},
                )
                return

            intake_job = await asyncio.to_thread(
                self._load_intake_job_by_source_file_id,
                job.source_file_ids[0] if job.source_file_ids else "",
            )
            if intake_job is None:
                raise RuntimeError("Intake job was not persisted before indexing")
            if intake_job.state != IntakeJobState.PUBLISHED.value:
                counters = _counters_for_intake_state(intake_job.state)
                self._bump_run_counts(run_id=context.run_id, **counters)
                context.emit(
                    event_type="doc.completed",
                    phase="approval",
                    message=f"{source_name} stopped at intake_state={intake_job.state}",
                    doc_id=detail.doc_id,
                    payload={
                        "job_id": job.job_id,
                        "intake_job_id": intake_job.intake_job_id,
                        "intake_state": intake_job.state,
                        "ticket_id": intake_job.ticket_id,
                        "final_doc_id": intake_job.final_doc_id,
                        "canonical_asset_path": detail.canonical_asset_path,
                    },
                )
                return

            context.emit(
                event_type="indexing.started",
                phase="indexing",
                message=f"Submitting {source_name} to indexing gate",
                doc_id=detail.doc_id,
                payload={"job_id": job.job_id, "index_version": index_version},
            )
            index_result = await self._indexing_service.run(
                IndexJobRequest(
                    job_id=job.job_id,
                    collection_id=collection_id,
                    index_version=index_version,
                )
            )

            document = await asyncio.to_thread(self._load_document, detail.doc_id)
            publish_status = document.publish_status.value if document is not None else "pending_review"
            counters = _counters_for_publish_status(PublishStatus(publish_status))
            self._bump_run_counts(run_id=context.run_id, **counters)

            context.emit(
                event_type="indexing.completed",
                phase="indexing",
                message=(
                    f"Indexing finished for {source_name}: "
                    f"{index_result.documents_indexed} document(s), {index_result.chunks_indexed} chunk(s)"
                ),
                doc_id=detail.doc_id,
                payload=index_result.model_dump(mode="json"),
            )
            context.emit(
                event_type="doc.completed",
                phase="result",
                message=f"{source_name} completed with publish_status={publish_status}",
                doc_id=detail.doc_id,
                payload={
                    "job_id": job.job_id,
                    "publish_status": publish_status,
                    "index_status": (document.index_status.value if document is not None else "not_indexed"),
                    "report_asset_path": job.report_asset_path,
                    "canonical_asset_path": detail.canonical_asset_path,
                },
            )
        except Exception as exc:
            self._bump_run_counts(run_id=context.run_id, failed=True)
            context.emit(
                event_type="doc.failed",
                phase="result",
                message=f"{source_name} failed: {exc}",
                level="error",
                payload={"error": str(exc)},
            )

    def _load_document(self, doc_id: str):
        session = get_session()
        try:
            return DocumentRepository(session).get(doc_id)
        finally:
            session.close()

    def _load_document_by_logical_id(self, logical_document_id: str):
        session = get_session()
        try:
            return DocumentRepository(session).get_by_logical_id(logical_document_id)
        finally:
            session.close()

    def _load_intake_job_by_source_file_id(self, source_file_id: str):
        if not source_file_id:
            return None
        session = get_session()
        try:
            return IntakeJobRepository(session).get_by_source_file_id(source_file_id)
        finally:
            session.close()

    def _bump_run_counts(
        self,
        *,
        run_id: str,
        approved: int = 0,
        rejected: int = 0,
        quarantined: int = 0,
        pending_review: int = 0,
        failed: bool = False,
    ) -> None:
        run = self._store.get_run(run_id)
        if run is None:
            return
        self._store.update_run(
            run_id,
            processed_files=int(run.get("processed_files", 0)) + 1,
            approved_files=int(run.get("approved_files", 0)) + approved,
            rejected_files=int(run.get("rejected_files", 0)) + rejected,
            quarantined_files=int(run.get("quarantined_files", 0)) + quarantined,
            pending_review_files=int(run.get("pending_review_files", 0)) + pending_review,
            failed_files=int(run.get("failed_files", 0)) + (1 if failed else 0),
        )
