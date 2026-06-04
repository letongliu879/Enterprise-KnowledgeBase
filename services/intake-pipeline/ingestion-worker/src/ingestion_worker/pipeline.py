"""Event-driven ingestion entrypoint."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from reality_rag_contracts import (
    ConversionReport,
    ConversionResult,
    ConversionStatus,
    IngestionJob,
    JobStatus,
    PublishStatus,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.ingestion import IngestionRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from reality_rag_persistence.telemetry import TelemetryStore
from reality_rag_documents import object_id_from_hash

from intake_runtime.agent_review_cache import get_agent_review_cache
from intake_runtime.agent_reviewer import get_agent_reviewer
from intake_runtime.converters.base import BaseConverter
from intake_runtime.pipeline_utils import report_asset_path, write_json_asset
from intake_runtime.stages.pure_stages import _logical_document_id

from .document_service_client import DocumentServiceClient


class IngestionPipeline:
    """Upload-to-terminal event-driven ingestion facade."""

    def __init__(
        self,
        converters: list[BaseConverter],
        agent_reviewer=None,
        agent_review_cache=None,
        telemetry_store: TelemetryStore | None = None,
    ) -> None:
        self._converters = converters
        self._agent_reviewer = agent_reviewer or get_agent_reviewer()
        self._agent_review_cache = agent_review_cache or get_agent_review_cache()
        self._telemetry_store = telemetry_store

    def run(
        self,
        collection_id: str,
        source_files: list[str],
    ) -> IngestionJob:
        job_id = f"ingest-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        details: list[ConversionResult] = []
        source_file_ids: list[str] = []

        session = get_session()
        try:
            collection = CollectionRepository(session).get(collection_id)
            if collection is None:
                raise ValueError(f"Collection '{collection_id}' not found")
            if collection.authority_level == 0:
                raise ValueError(
                    f"Collection '{collection_id}' authority_level must be explicitly set (>0)"
                )

            document_repo = DocumentRepository(session)
            doc_client = DocumentServiceClient(session)

            for source_file in source_files:
                content_hash = _compute_content_hash(source_file)
                if not content_hash:
                    details.append(
                        ConversionResult(
                            source_file_path=source_file,
                            conversion_status=ConversionStatus.FAILED,
                            error_message=f"File not found: {source_file}",
                        )
                    )
                    continue

                existing_doc = document_repo.get_by_source_content_hash(content_hash, collection_id)
                if existing_doc is not None and existing_doc.publish_status in (
                    PublishStatus.PUBLISHED,
                    PublishStatus.QUARANTINED,
                ):
                    details.append(
                        ConversionResult(
                            source_file_path=source_file,
                            conversion_status=ConversionStatus.SUCCESS,
                            doc_id=existing_doc.doc_id,
                            canonical_asset_path=existing_doc.asset_paths.get("canonical_md", ""),
                            error_message="Skipped: duplicate",
                        )
                    )
                    continue

                active_sf = doc_client.find_active_by_content_hash(content_hash, collection_id)
                if active_sf is not None:
                    source_file_ids.append(active_sf["source_file_id"])
                    continue

                source_path = Path(source_file)
                object_id = object_id_from_hash(content_hash)
                doc_client.get_or_create_object_blob(
                    content_hash,
                    str(source_path),
                    size_bytes=(source_path.stat().st_size if source_path.exists() else 0),
                )
                sf_result = doc_client.create_source_file(collection_id, object_id, content_hash)
                source_file_ids.append(sf_result["source_file_id"])

            session.commit()
        finally:
            session.close()

        # Phase 1: sync pipeline removed. Outbox events now drive real split workers.
        # The caller should poll or wait for projection events to determine terminal state.
        report = _build_report_from_details(
            job_id=job_id,
            source_files=source_files,
            details=details,
        )
        rap_path = report_asset_path(collection_id, job_id)
        write_json_asset(rap_path, report.model_dump(mode="json"))

        job = IngestionJob(
            job_id=job_id,
            job_type="ingestion",
            status=JobStatus.PENDING,
            collection_id=collection_id,
            source_files=source_files,
            source_file_ids=source_file_ids,
            conversion_report=report,
            report_asset_path=rap_path,
            created_at=now,
            updated_at=datetime.now(timezone.utc),
            error_message=None,
        )
        save_session = get_session()
        try:
            IngestionRepository(save_session).save(job)
            save_session.commit()
        finally:
            save_session.close()
        return job

    def _logical_document_id(self, source_file_path: str) -> str:
        return _logical_document_id(source_file_path)

    def _persist_review_telemetry(self, ctx: Any, review_task: Any) -> None:
        if self._telemetry_store is None:
            return
        review_context = getattr(ctx, "review_context", {}) or {}
        llm_records = review_context.get("llm_call_records", [])
        if not llm_records:
            return
        from reality_rag_contracts import LLMCallLog

        for rec in llm_records:
            try:
                log = LLMCallLog(
                    llm_call_id=f"llm-{uuid4().hex[:20]}",
                    trace_id=ctx.job_id,
                    intake_job_id=ctx.intake_job_id or ctx.job_id,
                    stage_task_id=getattr(review_task, "stage_task_id", "") if review_task else "",
                    review_id=getattr(ctx.agent_review, "review_id", None) if ctx.agent_review else None,
                    provider=rec.get("provider", "unknown"),
                    model_name=rec.get("model_name", "unknown"),
                    model_version=rec.get("model_version", ""),
                    prompt_version=rec.get("prompt_version", ""),
                    policy_version=rec.get("policy_version", ""),
                    request_hash=rec.get("request_hash", ""),
                    response_hash=rec.get("response_hash", ""),
                    input_token_count=rec.get("input_token_count"),
                    output_token_count=rec.get("output_token_count"),
                    total_token_count=rec.get("total_token_count"),
                    latency_ms=rec.get("latency_ms"),
                    timeout_ms=rec.get("timeout_ms", 60000),
                    status=rec.get("status", "succeeded"),
                    error_code=rec.get("error_code"),
                    retry_count=rec.get("retry_count", 0),
                    json_parse_success=rec.get("json_parse_success", False),
                    schema_validation_success=rec.get("schema_validation_success", False),
                    redaction_before_send=True,
                    external_model_used=rec.get("external_model_used", False),
                )
                self._telemetry_store.log_llm_call(log)
            except Exception:
                pass

    def _persist_review_feedback(self, ctx: Any) -> None:
        if self._telemetry_store is None or ctx.agent_review is None:
            return
        try:
            from reality_rag_contracts import ReviewQualityFeedback

            pii_items = getattr(ctx.agent_review, "pii_items", []) or []
            pii_by_type: dict[str, int] = {}
            pii_by_severity: dict[str, int] = {}
            for item in pii_items:
                pii_by_type[item.pii_type] = pii_by_type.get(item.pii_type, 0) + 1
                pii_by_severity[item.severity] = pii_by_severity.get(item.severity, 0) + 1
            feedback = ReviewQualityFeedback(
                feedback_id=f"rqf-{uuid4().hex[:20]}",
                review_id=getattr(ctx.agent_review, "review_id", "") or "",
                intake_job_id=ctx.intake_job_id or ctx.job_id,
                ticket_id=ctx.ticket_id or None,
                collection_id=ctx.collection_id,
                visibility=getattr(ctx, "visibility", "INTERNAL"),
                model_name=getattr(ctx.agent_review, "model_name", None),
                model_version=getattr(ctx.agent_review, "model_version", None),
                prompt_version=getattr(ctx.agent_review, "prompt_version", None),
                routing_recommendation=(
                    "require_approval" if ctx.publish_status != "published" else "auto_approve"
                ),
                review_status="succeeded",
                pii_count_by_type=pii_by_type,
                pii_count_by_severity=pii_by_severity,
                approval_decision=("approve" if ctx.publish_status == "published" else "reject"),
                auto_approved=True,
                created_at=datetime.now(timezone.utc),
            )
            self._telemetry_store.record_review_feedback(feedback)
        except Exception:
            pass

    # Sync pipeline helpers removed in Phase 1. Split workers now consume outbox events.


def _build_report_from_details(
    *,
    job_id: str,
    source_files: list[str],
    details: list[ConversionResult],
) -> ConversionReport:
    successful = sum(1 for detail in details if detail.conversion_status == ConversionStatus.SUCCESS)
    failed = sum(1 for detail in details if detail.conversion_status == ConversionStatus.FAILED)
    unsupported = sum(1 for detail in details if detail.conversion_status == ConversionStatus.UNSUPPORTED)
    if not details:
        overall = ConversionStatus.UNSUPPORTED
    elif failed > 0 and successful == 0 and unsupported == 0:
        overall = ConversionStatus.FAILED
    elif unsupported == len(details):
        overall = ConversionStatus.UNSUPPORTED
    elif failed > 0 or unsupported > 0:
        overall = ConversionStatus.PARTIAL
    else:
        overall = ConversionStatus.SUCCESS
    warnings: list[str] = []
    if unsupported > 0:
        warnings.append(f"{unsupported} file(s) have unsupported extensions")
    if failed > 0:
        warnings.append(f"{failed} file(s) failed conversion")
    return ConversionReport(
        report_id=f"rpt-{uuid4().hex[:8]}",
        job_id=job_id,
        source_file_path=source_files[0] if len(source_files) == 1 else f"batch:{len(details)}_files",
        conversion_status=overall,
        total_files=len(details),
        successful=successful,
        failed=failed,
        unsupported=unsupported,
        warnings=warnings,
        details=details,
        created_at=datetime.now(timezone.utc),
    )


def _compute_content_hash(source_file_path: str) -> str:
    path = Path(source_file_path)
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
