"""Indexing service HTTP facade.

The final-state owner of parsing materialization, chunk registry, index
versions, and backend writes is the modern indexing-service process.  This
facade prepares the intake/publishing lineage payload and submits the canonical
``IndexBuildRequested`` command over HTTP.
"""

from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from reality_rag_contracts import (
    IndexBuildRequestedCommand,
    IndexJobRequest,
    IndexJobResult,
    IndexRequestType,
    IndexStatus,
    IndexSwitchRequest,
    IndexSwitchResult,
    JobStatus,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.approval_audit_log import ApprovalAuditLogRepository
from reality_rag_persistence.repositories.approval_tickets import ApprovalTicketRepository
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.index_registry import IndexRegistryRepository
from reality_rag_persistence.repositories.index_versions import IndexVersionRepository
from reality_rag_persistence.repositories.indexed_documents import IndexedDocumentRepository
from reality_rag_persistence.repositories.ingestion import IngestionRepository
from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository
from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from reality_rag_persistence.models import StageResultModel

if TYPE_CHECKING:
    from reality_rag_contracts import ApprovalAuditLog, ApprovalTicket, CanonicalMetadata, Collection, IngestionJob, ObjectBlob, SourceFile
else:
    IndexBuildInput = Any
    IndexBuildOutput = Any
    PerDocumentIndexResult = Any


class IndexJobError(RuntimeError):
    """Indexing job failure surfaced by the indexing-service owner."""


__all__ = [
    "IndexBuildInput",
    "IndexBuildOutput",
    "IndexJobError",
    "IndexingService",
    "PerDocumentIndexResult",
    "get_indexing_service",
]

_REMOTE_URL: str | None = None


@dataclass(frozen=True)
class _PreparedIndexDocument:
    source_file_id: str
    intake_job_id: str
    tenant_id: str
    collection_id: str
    filename: str
    visibility: str
    trace_id: str
    parse_snapshot_id: str
    final_doc_id: str
    document_version: str
    publish_version: str
    source_binary_ref: str
    canonical_asset_ref: str
    sanitized_asset_ref: str
    quality_report_ref: str | None
    metadata_ref: str
    approval_ref: str
    governance_overlay_ref: str
    source_metadata: dict[str, str]


def _get_remote_url() -> str | None:
    global _REMOTE_URL
    if _REMOTE_URL is None:
        _REMOTE_URL = os.environ.get("INDEXING_SERVICE_URL", "").rstrip("/") or None
    return _REMOTE_URL


def _require_remote_url() -> str:
    remote_url = _get_remote_url()
    if remote_url is None:
        raise IndexJobError("INDEXING_SERVICE_URL is required; indexing must run through the indexing-service owner")
    return remote_url


def _url(path: str) -> str:
    base = _require_remote_url()
    return f"{base}{path}"


def _runtime_dir() -> Path:
    configured = os.environ.get("REALITY_RAG_INTAKE_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[5] / ".verify" / "runtime" / "intake"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _string_map(*payloads: dict[str, object] | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for payload in payloads:
        if not payload:
            continue
        for key, value in payload.items():
            text = _safe_text(value).strip()
            if text:
                merged[str(key)] = text
    return merged


def _guess_mime_type(filename: str, source_binary_ref: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename or source_binary_ref)
    return mime_type or "application/octet-stream"


def _select_approval_ticket(repo: ApprovalTicketRepository, intake_job_id: str, ticket_id: str | None) -> Any:
    if ticket_id:
        ticket = repo.get(ticket_id)
        if ticket is not None:
            return ticket
    tickets = repo.get_by_intake_job(intake_job_id)
    if tickets:
        return tickets[-1]
    return None


def _approval_payload(ticket: Any, *, intake_job_id: str, final_doc_id: str) -> dict[str, object]:
    if ticket is None:
        return {
            "ticket_id": "",
            "intake_job_id": intake_job_id,
            "decision": "approve",
            "actor_id": "system",
            "confirmed_tags": [],
            "final_doc_id": final_doc_id,
            "state": "system_decided",
            "routing_recommendation": "auto_approve",
            "decision_reason": "",
            "approval_round": 1,
            "created_at": _now_iso(),
            "decided_at": _now_iso(),
        }
    return {
        "ticket_id": ticket.ticket_id,
        "intake_job_id": ticket.intake_job_id,
        "decision": ticket.decision or "approve",
        "actor_id": ticket.decision_actor or "system",
        "confirmed_tags": list(ticket.confirmed_tags or []),
        "final_doc_id": ticket.final_doc_id or final_doc_id,
        "state": ticket.state.value,
        "routing_recommendation": ticket.routing_recommendation,
        "decision_reason": ticket.decision_reason or "",
        "approval_round": ticket.approval_round,
        "version_decision": ticket.version_decision.value if ticket.version_decision else "",
        "supersedes_final_doc_id": ticket.supersedes_final_doc_id or "",
        "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
        "decided_at": ticket.decided_at.isoformat() if ticket.decided_at else "",
    }


def _approval_audit_rows(rows: list[Any]) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for row in rows:
        payloads.append(
            {
                "audit_id": row.audit_id,
                "ticket_id": row.ticket_id,
                "intake_job_id": row.intake_job_id,
                "actor_id": row.actor_id,
                "action": row.action.value,
                "before_state": row.before_state or "",
                "after_state": row.after_state or "",
                "reason": row.reason or "",
                "payload_hash": row.payload_hash,
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
        )
    return payloads


def _document_version_text(document: Any, published_document: Any) -> str:
    version = 1
    if published_document is not None and getattr(published_document, "version", None):
        version = int(published_document.version)
    elif document is not None and getattr(document, "version", None):
        version = int(document.version)
    return f"v{version}"


def _publish_version_text(document: Any, published_document: Any) -> str:
    version = 1
    if published_document is not None and getattr(published_document, "version", None):
        version = int(published_document.version)
    elif document is not None and getattr(document, "version", None):
        version = int(document.version)
    return f"pub_{version:03d}"


def _first_existing_document(document_repo: DocumentRepository, *doc_ids: str) -> Any:
    for doc_id in doc_ids:
        text = str(doc_id or "").strip()
        if not text:
            continue
        document = document_repo.get(text)
        if document is not None:
            return document
    return None


def _build_lineage_sidecars(
    *,
    source_file_id: str,
    intake_job_id: str,
    ingestion_job_id: str,
    collection: Any,
    source_file: Any,
    object_blob: Any,
    document: Any,
    final_doc_id: str,
    filename: str,
    document_version: str,
    publish_version: str,
    canonical_asset_ref: str,
    sanitized_asset_ref: str,
    quality_report_ref: str | None,
    approval_payload: dict[str, object],
    approval_audits: list[dict[str, object]],
    trace_id: str,
    parse_snapshot_id: str,
    detail_metadata: dict[str, object] | None,
) -> tuple[str, str, str, dict[str, str]]:
    doc_dir = _runtime_dir() / source_file_id
    metadata_ref = doc_dir / "metadata.json"
    approval_ref = doc_dir / "approval.json"
    overlay_ref = doc_dir / "governance-overlay.json"
    audit_ref = doc_dir / "approval_audit_log.jsonl"

    source_metadata = _string_map(
        detail_metadata or {},
        {
            "filename": filename,
            "original_name": source_file.original_name or filename,
            "sanitized_name": source_file.sanitized_name or filename,
            "visibility": source_file.visibility,
            "source_file_id": source_file_id,
            "intake_job_id": intake_job_id,
            "ingestion_job_id": ingestion_job_id,
            "object_id": source_file.object_id,
            "content_hash": source_file.content_hash,
            "size_bytes": source_file.size_bytes,
            "logical_document_id": document.logical_document_id,
            "final_doc_id": final_doc_id,
            "document_version": document_version,
            "publish_version": publish_version,
            "authority_level": document.authority_level,
            "governance_level": document.governance_level,
            "access_policy": document.access_policy,
            "trace_id": trace_id,
            "parse_snapshot_id": parse_snapshot_id,
        },
    )

    _write_json(
        metadata_ref,
        {
            "source_file_id": source_file_id,
            "intake_job_id": intake_job_id,
            "ingestion_job_id": ingestion_job_id,
            "tenant_id": collection.tenant_id,
            "collection_id": collection.collection_id,
            "filename": filename,
            "source_binary_ref": object_blob.storage_key,
            "final_doc_id": final_doc_id,
            "logical_document_id": document.logical_document_id,
            "document_version": document_version,
            "publish_version": publish_version,
            "visibility": source_file.visibility,
            "canonical_asset_ref": canonical_asset_ref,
            "sanitized_asset_ref": sanitized_asset_ref,
            "quality_report_ref": quality_report_ref or "",
            "document_asset_paths": dict(document.asset_paths or {}),
            "source_metadata": source_metadata,
            "trace_id": trace_id,
            "parse_snapshot_id": parse_snapshot_id,
            "generated_at": _now_iso(),
        },
    )
    _write_json(approval_ref, approval_payload)
    _write_json(
        overlay_ref,
        {
            "source_file_id": source_file_id,
            "intake_job_id": intake_job_id,
            "final_doc_id": final_doc_id,
            "visibility": source_file.visibility,
            "confirmed_tags": list(approval_payload.get("confirmed_tags") or []),
            "publish_version": publish_version,
            "approval_decision_ref": str(approval_ref),
            "approval_audit_ref": str(audit_ref),
            "metadata_ref": str(metadata_ref),
            "canonical_asset_ref": canonical_asset_ref,
            "parse_snapshot_id": parse_snapshot_id,
            "generated_at": _now_iso(),
        },
    )
    _write_jsonl(audit_ref, approval_audits)
    return str(metadata_ref), str(approval_ref), str(overlay_ref), source_metadata


def _conversion_parse_snapshot_id(session, intake_job_id: str) -> str:
    row = (
        session.query(StageResultModel)
        .filter(StageResultModel.intake_job_id == intake_job_id)
        .filter(StageResultModel.stage_name == "conversion")
        .first()
    )
    if row is None or not row.summary_json:
        return ""
    summary = row.summary_json or {}
    parse_snapshot_id = str(summary.get("parse_snapshot_id") or "").strip()
    if parse_snapshot_id:
        return parse_snapshot_id
    conversion_result = summary.get("conversion_result")
    if isinstance(conversion_result, dict):
        metadata = conversion_result.get("metadata")
        if isinstance(metadata, dict):
            return str(metadata.get("parse_snapshot_id") or "").strip()
    return ""


def _update_document_index_state(final_doc_id: str, *, index_version_id: str, status: IndexStatus) -> None:
    session = get_session()
    try:
        document_repo = DocumentRepository(session)
        published_repo = PublishedDocumentRepository(session)
        document = document_repo.get(final_doc_id)
        if document is not None:
            document_repo.save(document.model_copy(update={"index_status": status}))
        published_document = published_repo.get_by_final_doc_id(final_doc_id)
        if published_document is not None and status == IndexStatus.INDEXED:
            published_repo.set_active_index_version(
                published_document.published_document_id,
                index_version_id,
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _build_publish_request_payload(
    *,
    document: _PreparedIndexDocument,
    parse_snapshot_id: str,
    index_profile_id: str,
    target_index_version_id: str | None,
) -> dict[str, object]:
    approval_payload = json.loads(Path(document.approval_ref).read_text(encoding="utf-8"))
    command = IndexBuildRequestedCommand(
        build_request_id=f"ibr_{document.intake_job_id}",
        request_type=IndexRequestType.PUBLISH,
        tenant_id=document.tenant_id,
        collection_id=document.collection_id,
        source_file_id=document.source_file_id,
        final_doc_id=document.final_doc_id,
        document_version=document.document_version,
        publish_version=document.publish_version,
        visibility=document.visibility,
        source_binary_ref=document.source_binary_ref,
        parse_snapshot_id=parse_snapshot_id,
        governance_overlay_ref=document.governance_overlay_ref,
        sanitized_asset_ref=document.sanitized_asset_ref,
        canonical_asset_ref=document.canonical_asset_ref,
        metadata_ref=document.metadata_ref,
        quality_report_ref=document.quality_report_ref or None,
        approval_decision_ref=document.approval_ref,
        confirmed_tags=list(approval_payload.get("confirmed_tags") or []),
        source_metadata=document.source_metadata,
        index_profile_id=index_profile_id,
        target_index_version_id=target_index_version_id,
        idempotency_key=(
            f"{document.final_doc_id}:{document.publish_version}:"
            f"{target_index_version_id or 'active'}"
        ),
        trace_id=document.trace_id,
    )
    return command.model_dump(mode="json", by_alias=True)


def _load_prepared_documents(request: IndexJobRequest) -> list[_PreparedIndexDocument]:
    session = get_session()
    try:
        ingestion_job = IngestionRepository(session).get(request.job_id)
        if ingestion_job is None:
            raise IndexJobError(f"Ingestion job '{request.job_id}' not found")
        collection = CollectionRepository(session).get(request.collection_id)
        if collection is None:
            raise IndexJobError(f"Collection '{request.collection_id}' not found")

        source_repo = SourceFileRepository(session)
        intake_repo = IntakeJobRepository(session)
        object_repo = ObjectBlobRepository(session)
        document_repo = DocumentRepository(session)
        ticket_repo = ApprovalTicketRepository(session)
        audit_repo = ApprovalAuditLogRepository(session)
        published_repo = PublishedDocumentRepository(session)

        details = list(ingestion_job.conversion_report.details) if ingestion_job.conversion_report else []
        detail_by_source_file_id: dict[str, Any] = {}
        for idx, source_file_id in enumerate(ingestion_job.source_file_ids):
            if idx < len(details):
                detail_by_source_file_id[source_file_id] = details[idx]

        prepared: list[_PreparedIndexDocument] = []
        for source_file_id in ingestion_job.source_file_ids:
            source_file = source_repo.get(source_file_id)
            if source_file is None:
                raise IndexJobError(f"Source file '{source_file_id}' not found")
            intake_job = intake_repo.get_by_source_file_id(source_file_id)
            if intake_job is None:
                raise IndexJobError(f"Intake job for source file '{source_file_id}' not found")
            object_blob = object_repo.get(source_file.object_id)
            if object_blob is None:
                raise IndexJobError(f"Object blob '{source_file.object_id}' not found")

            detail = detail_by_source_file_id.get(source_file_id)
            document = _first_existing_document(
                document_repo,
                intake_job.final_doc_id or "",
                (detail.doc_id if detail is not None else ""),
                intake_job.preliminary_doc_id or "",
            )
            if document is None:
                raise IndexJobError(
                    f"Published document for source file '{source_file_id}' was not found after publishing"
                )

            final_doc_id = str(intake_job.final_doc_id or document.doc_id).strip()
            published_document = published_repo.get_by_final_doc_id(final_doc_id)
            canonical_asset_ref = str(
                (document.asset_paths or {}).get("canonical_md")
                or (detail.canonical_asset_path if detail is not None else "")
            ).strip()
            if not canonical_asset_ref:
                raise IndexJobError(f"Document '{final_doc_id}' does not have canonical_md asset")
            sanitized_asset_ref = str((document.asset_paths or {}).get("sanitized_md") or canonical_asset_ref).strip()
            quality_report_ref = str((document.asset_paths or {}).get("quality_report") or "").strip() or None

            ticket = _select_approval_ticket(ticket_repo, intake_job.intake_job_id, intake_job.ticket_id)
            approval_payload = _approval_payload(
                ticket,
                intake_job_id=intake_job.intake_job_id,
                final_doc_id=final_doc_id,
            )
            approval_audits = _approval_audit_rows(
                audit_repo.get_by_ticket(ticket.ticket_id) if ticket is not None else []
            )
            filename = (
                source_file.original_name
                or source_file.sanitized_name
                or Path(object_blob.storage_key).name
            )
            document_version = _document_version_text(document, published_document)
            publish_version = request.options.get("publish_version") or _publish_version_text(
                document,
                published_document,
            )
            parse_snapshot_id = str(
                (
                    (detail.metadata or {}).get("parse_snapshot_id")
                    if detail is not None
                    else ""
                )
                or _conversion_parse_snapshot_id(session, intake_job.intake_job_id)
                or ""
            ).strip()
            metadata_ref, approval_ref, governance_overlay_ref, source_metadata = _build_lineage_sidecars(
                source_file_id=source_file_id,
                intake_job_id=intake_job.intake_job_id,
                ingestion_job_id=request.job_id,
                collection=collection,
                source_file=source_file,
                object_blob=object_blob,
                document=document,
                final_doc_id=final_doc_id,
                filename=filename,
                document_version=document_version,
                publish_version=publish_version,
                canonical_asset_ref=canonical_asset_ref,
                sanitized_asset_ref=sanitized_asset_ref,
                quality_report_ref=quality_report_ref,
                approval_payload=approval_payload,
                approval_audits=approval_audits,
                trace_id=intake_job.trace_id or request.job_id,
                parse_snapshot_id=parse_snapshot_id,
                detail_metadata=(detail.metadata if detail is not None else {}),
            )
            prepared.append(
                _PreparedIndexDocument(
                    source_file_id=source_file_id,
                    intake_job_id=intake_job.intake_job_id,
                    tenant_id=collection.tenant_id,
                    collection_id=collection.collection_id,
                    filename=filename,
                    visibility=source_file.visibility,
                    trace_id=intake_job.trace_id or request.job_id,
                    parse_snapshot_id=parse_snapshot_id,
                    final_doc_id=final_doc_id,
                    document_version=document_version,
                    publish_version=publish_version,
                    source_binary_ref=object_blob.storage_key,
                    canonical_asset_ref=canonical_asset_ref,
                    sanitized_asset_ref=sanitized_asset_ref,
                    quality_report_ref=quality_report_ref,
                    metadata_ref=metadata_ref,
                    approval_ref=approval_ref,
                    governance_overlay_ref=governance_overlay_ref,
                    source_metadata=source_metadata,
                )
            )
        return prepared
    finally:
        session.close()


def _load_prepared_document_for_intake_job(
    intake_job_id: str,
    *,
    publish_version_override: str | None = None,
) -> _PreparedIndexDocument:
    session = get_session()
    try:
        intake_repo = IntakeJobRepository(session)
        source_repo = SourceFileRepository(session)
        object_repo = ObjectBlobRepository(session)
        document_repo = DocumentRepository(session)
        collection_repo = CollectionRepository(session)
        ticket_repo = ApprovalTicketRepository(session)
        audit_repo = ApprovalAuditLogRepository(session)
        published_repo = PublishedDocumentRepository(session)

        intake_job = intake_repo.get(intake_job_id)
        if intake_job is None:
            raise IndexJobError(f"Intake job '{intake_job_id}' not found")
        collection = collection_repo.get(intake_job.collection_id)
        if collection is None:
            raise IndexJobError(f"Collection '{intake_job.collection_id}' not found")
        source_file = source_repo.get(intake_job.source_file_id)
        if source_file is None:
            raise IndexJobError(f"Source file '{intake_job.source_file_id}' not found")
        object_blob = object_repo.get(source_file.object_id)
        if object_blob is None:
            raise IndexJobError(f"Object blob '{source_file.object_id}' not found")

        document = _first_existing_document(
            document_repo,
            intake_job.final_doc_id or "",
            intake_job.preliminary_doc_id or "",
        )
        if document is None:
            raise IndexJobError(
                f"Published document for intake job '{intake_job_id}' was not found after publishing"
            )

        final_doc_id = str(intake_job.final_doc_id or document.doc_id).strip()
        published_document = published_repo.get_by_final_doc_id(final_doc_id)
        canonical_asset_ref = str((document.asset_paths or {}).get("canonical_md") or "").strip()
        if not canonical_asset_ref:
            raise IndexJobError(f"Document '{final_doc_id}' does not have canonical_md asset")
        sanitized_asset_ref = str((document.asset_paths or {}).get("sanitized_md") or canonical_asset_ref).strip()
        quality_report_ref = str((document.asset_paths or {}).get("quality_report") or "").strip() or None

        ticket = _select_approval_ticket(ticket_repo, intake_job.intake_job_id, intake_job.ticket_id)
        approval_payload = _approval_payload(
            ticket,
            intake_job_id=intake_job.intake_job_id,
            final_doc_id=final_doc_id,
        )
        approval_audits = _approval_audit_rows(
            audit_repo.get_by_ticket(ticket.ticket_id) if ticket is not None else []
        )
        filename = (
            source_file.original_name
            or source_file.sanitized_name
            or Path(object_blob.storage_key).name
        )
        document_version = _document_version_text(document, published_document)
        publish_version = publish_version_override or _publish_version_text(document, published_document)
        parse_snapshot_id = _conversion_parse_snapshot_id(session, intake_job.intake_job_id)
        detail_metadata = {
            "parse_snapshot_id": parse_snapshot_id,
            "intake_job_id": intake_job.intake_job_id,
            "ticket_id": intake_job.ticket_id or "",
        }
        metadata_ref, approval_ref, governance_overlay_ref, source_metadata = _build_lineage_sidecars(
            source_file_id=source_file.source_file_id,
            intake_job_id=intake_job.intake_job_id,
            ingestion_job_id=intake_job.intake_job_id,
            collection=collection,
            source_file=source_file,
            object_blob=object_blob,
            document=document,
            final_doc_id=final_doc_id,
            filename=filename,
            document_version=document_version,
            publish_version=publish_version,
            canonical_asset_ref=canonical_asset_ref,
            sanitized_asset_ref=sanitized_asset_ref,
            quality_report_ref=quality_report_ref,
            approval_payload=approval_payload,
            approval_audits=approval_audits,
            trace_id=intake_job.trace_id or intake_job.intake_job_id,
            parse_snapshot_id=parse_snapshot_id,
            detail_metadata=detail_metadata,
        )
        return _PreparedIndexDocument(
            source_file_id=source_file.source_file_id,
            intake_job_id=intake_job.intake_job_id,
            tenant_id=collection.tenant_id,
            collection_id=collection.collection_id,
            filename=filename,
            visibility=source_file.visibility,
            trace_id=intake_job.trace_id or intake_job.intake_job_id,
            parse_snapshot_id=parse_snapshot_id,
            final_doc_id=final_doc_id,
            document_version=document_version,
            publish_version=publish_version,
            source_binary_ref=object_blob.storage_key,
            canonical_asset_ref=canonical_asset_ref,
            sanitized_asset_ref=sanitized_asset_ref,
            quality_report_ref=quality_report_ref,
            metadata_ref=metadata_ref,
            approval_ref=approval_ref,
            governance_overlay_ref=governance_overlay_ref,
            source_metadata=source_metadata,
        )
    finally:
        session.close()


class _RemoteIndexingService:
    """HTTP client facade that mirrors the legacy IndexingService API."""

    async def run(self, request: IndexJobRequest) -> IndexJobResult:
        prepared_documents = _load_prepared_documents(request)
        return await self._run_prepared_documents(
            prepared_documents=prepared_documents,
            job_id=request.job_id,
            collection_id=request.collection_id,
            index_version=request.index_version,
            options=request.options,
        )

    async def run_intake_job(
        self,
        *,
        intake_job_id: str,
        collection_id: str,
        index_version: str = "",
        options: dict[str, Any] | None = None,
    ) -> IndexJobResult:
        options = dict(options or {})
        prepared_document = _load_prepared_document_for_intake_job(
            intake_job_id,
            publish_version_override=(
                str(options.get("publish_version")).strip()
                if options.get("publish_version")
                else None
            ),
        )
        return await self._run_prepared_documents(
            prepared_documents=[prepared_document],
            job_id=intake_job_id,
            collection_id=collection_id,
            index_version=index_version,
            options=options,
        )

    async def _run_prepared_documents(
        self,
        *,
        prepared_documents: list[_PreparedIndexDocument],
        job_id: str,
        collection_id: str,
        index_version: str = "",
        options: dict[str, Any] | None = None,
    ) -> IndexJobResult:
        options = dict(options or {})
        index_profile_id = str(options.get("index_profile_id") or "ragflow").strip() or "ragflow"
        activate_index_version = bool(options.get("activate_index_version", True))
        total_chunks = 0
        total_documents = 0
        resulting_index_version = index_version

        async with httpx.AsyncClient(timeout=180.0) as client:
            for prepared in prepared_documents:
                parse_snapshot_id = prepared.parse_snapshot_id
                if not parse_snapshot_id:
                    preview_response = await client.post(
                        _url("/internal/parse-previews"),
                        json={
                            "request_id": f"req_{prepared.source_file_id}",
                            "tenant_id": prepared.tenant_id,
                            "collection_id": prepared.collection_id,
                            "source_file_id": prepared.source_file_id,
                            "source_binary_ref": prepared.source_binary_ref,
                            "filename": prepared.filename,
                            "mime_type": _guess_mime_type(prepared.filename, prepared.source_binary_ref),
                            "source_system": "ingestion-worker",
                            "metadata": prepared.source_metadata,
                            "trace_id": prepared.trace_id,
                        },
                    )
                    if preview_response.status_code >= 400:
                        raise IndexJobError(preview_response.text)
                    preview_payload = preview_response.json()
                    parse_snapshot_id = str(preview_payload["parse_snapshot_id"])

                build_payload = _build_publish_request_payload(
                    document=prepared,
                    parse_snapshot_id=parse_snapshot_id,
                    index_profile_id=index_profile_id,
                    target_index_version_id=(index_version or None),
                )
                build_response = await client.post(
                    _url("/internal/index-jobs"),
                    json=build_payload,
                )
                if build_response.status_code >= 400:
                    raise IndexJobError(build_response.text)
                build_started = build_response.json()

                job_response = await client.get(
                    _url(f"/internal/index-jobs/{build_started['build_job_id']}")
                )
                if job_response.status_code >= 400:
                    raise IndexJobError(job_response.text)
                job_payload = job_response.json()
                if str(job_payload.get("status") or "").upper() != "READY":
                    raise IndexJobError(
                        f"Modern indexing job '{job_payload.get('build_job_id')}' "
                        f"did not finish successfully: {job_payload}"
                    )

                index_version_id = str(job_payload.get("index_version_id") or index_version).strip()
                if activate_index_version and index_version_id:
                    activate_response = await client.post(
                        _url(f"/internal/index-versions/{index_version_id}/activate")
                    )
                    if activate_response.status_code >= 400:
                        raise IndexJobError(activate_response.text)
                resulting_index_version = index_version_id or resulting_index_version

                session = get_session()
                try:
                    indexed_document = IndexedDocumentRepository(session).get_by_final_doc_and_version(
                        prepared.final_doc_id,
                        resulting_index_version,
                    )
                finally:
                    session.close()
                total_documents += 1
                total_chunks += indexed_document.chunk_count if indexed_document is not None else 0
                _update_document_index_state(
                    prepared.final_doc_id,
                    index_version_id=resulting_index_version,
                    status=IndexStatus.INDEXED,
                )

        return IndexJobResult(
            job_id=job_id,
            collection_id=collection_id,
            index_version=resulting_index_version,
            status=JobStatus.COMPLETED,
            documents_indexed=total_documents,
            chunks_indexed=total_chunks,
            backend_mode="modern-indexing-service",
        )

    def activate(self, collection_id: str, index_version: str | None = None) -> IndexSwitchResult:
        req = IndexSwitchRequest(
            collection_id=collection_id,
            index_version=index_version,
        )
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self._activate_async(req))

    async def _activate_async(self, request: IndexSwitchRequest) -> IndexSwitchResult:
        target_index_version = request.index_version or self._latest_index_version(request.collection_id)
        if not target_index_version:
            raise IndexJobError(f"No index version found for collection '{request.collection_id}'")
        previous_index_version = self._active_index_version(request.collection_id)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _url(f"/internal/index-versions/{target_index_version}/activate")
            )
            if resp.status_code >= 400:
                raise IndexJobError(resp.text)
        return IndexSwitchResult(
            collection_id=request.collection_id,
            active_index_version=target_index_version,
            previous_index_version=previous_index_version,
            target_index_version=target_index_version,
            status="indexed",
        )

    def rollback(self, collection_id: str, index_version: str | None = None) -> IndexSwitchResult:
        req = IndexSwitchRequest(
            collection_id=collection_id,
            index_version=index_version,
        )
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self._rollback_async(req))

    async def _rollback_async(self, request: IndexSwitchRequest) -> IndexSwitchResult:
        target_index_version = request.index_version or self._active_index_version(request.collection_id)
        if not target_index_version:
            raise IndexJobError(f"No active index version found for collection '{request.collection_id}'")
        fallback_index_version = self._previous_index_version(target_index_version)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _url(f"/internal/index-versions/{target_index_version}/rollback")
            )
            if resp.status_code >= 400:
                raise IndexJobError(resp.text)
        return IndexSwitchResult(
            collection_id=request.collection_id,
            active_index_version=fallback_index_version or target_index_version,
            previous_index_version=target_index_version,
            target_index_version=fallback_index_version,
            status="indexed",
        )

    @staticmethod
    def _active_index_version(collection_id: str) -> str | None:
        session = get_session()
        try:
            registry = IndexRegistryRepository(session).get(collection_id)
            if registry is None:
                return None
            return registry.index_version
        finally:
            session.close()

    @staticmethod
    def _latest_index_version(collection_id: str) -> str | None:
        session = get_session()
        try:
            versions = IndexVersionRepository(session).list_by_collection(collection_id)
            if not versions:
                return None
            return versions[-1].index_version_id
        finally:
            session.close()

    @staticmethod
    def _previous_index_version(index_version_id: str) -> str | None:
        session = get_session()
        try:
            version = IndexVersionRepository(session).get(index_version_id)
            if version is None:
                return None
            return version.previous_active_index_version_id
        finally:
            session.close()


class _IndexingServiceFacade:
    """Dispatch indexing requests to the indexing-service owner."""

    def __init__(self) -> None:
        self._remote: _RemoteIndexingService | None = None

    def _get_remote(self) -> _RemoteIndexingService:
        _require_remote_url()
        if self._remote is None:
            self._remote = _RemoteIndexingService()
        return self._remote

    async def run(self, request: IndexJobRequest) -> IndexJobResult:
        return await self._get_remote().run(request)

    async def run_intake_job(
        self,
        *,
        intake_job_id: str,
        collection_id: str,
        index_version: str = "",
        options: dict[str, Any] | None = None,
    ) -> IndexJobResult:
        return await self._get_remote().run_intake_job(
            intake_job_id=intake_job_id,
            collection_id=collection_id,
            index_version=index_version,
            options=options,
        )

    def activate(self, collection_id: str, index_version: str | None = None) -> IndexSwitchResult:
        return self._get_remote().activate(collection_id, index_version)

    def rollback(self, collection_id: str, index_version: str | None = None) -> IndexSwitchResult:
        return self._get_remote().rollback(collection_id, index_version)


IndexingService = _IndexingServiceFacade


_indexing_svc: _IndexingServiceFacade | None = None


def get_indexing_service() -> _IndexingServiceFacade:
    """Return the indexing-service HTTP facade."""
    global _indexing_svc
    if _indexing_svc is None:
        _indexing_svc = _IndexingServiceFacade()
    return _indexing_svc
