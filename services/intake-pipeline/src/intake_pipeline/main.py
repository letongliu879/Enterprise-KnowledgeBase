"""Compatibility-only intake API.

This module remains available for smoke and legacy paths, but it is no longer
the intended owner for the split intake chain.
"""

from __future__ import annotations

import json
import os
import shutil
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from reality_rag_persistence.run_audit_store import PersistentRunAuditStore

from intake_pipeline.lineage import MainChainLineageInspector
from intake_pipeline.publishing_facade import ApprovalDecision, PublishRequest, PublishingFacade
from intake_pipeline.state_models import ApprovalTicketState, IntakeJobState, PublishState, SourceFileState


class CompatConfigurationError(RuntimeError):
    """Compatibility-only root service is missing required explicit configuration."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir() -> Path:
    configured = os.environ.get("REALITY_RAG_INTAKE_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4] / ".verify" / "runtime" / "intake"


def _append_projection(env_name: str, payload: dict[str, object]) -> None:
    raw_path = os.environ.get(env_name, "").strip()
    if not raw_path:
        return
    path = Path(raw_path)
    if path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _size_bucket(size_bytes: int) -> str:
    if size_bytes < 4_096:
        return "tiny"
    if size_bytes < 65_536:
        return "small"
    if size_bytes < 1_048_576:
        return "medium"
    return "large"


def _latency_bucket(duration_ms: int) -> str:
    if duration_ms < 100:
        return "xs"
    if duration_ms < 500:
        return "s"
    if duration_ms < 2_000:
        return "m"
    return "l"


def _payload_hash(*parts: object) -> str:
    digest = sha256()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _compat_writes_enabled() -> bool:
    return _env_flag("REALITY_RAG_ENABLE_COMPAT_WRITES")


def _allow_local_fallback_for_tests() -> bool:
    return _env_flag("ALLOW_LOCAL_FALLBACK_FOR_TESTS")


def _require_compat_service_url(env_name: str, *, default_url: str, purpose: str) -> str:
    explicit = os.environ.get(env_name, "").strip().rstrip("/")
    if explicit:
        return explicit
    if _allow_local_fallback_for_tests():
        return default_url.rstrip("/")
    raise CompatConfigurationError(
        f"{env_name} is required for compatibility-root {purpose}; "
        "local fallback is disabled. Set the URL explicitly, or set "
        "ALLOW_LOCAL_FALLBACK_FOR_TESTS=true only for targeted smoke/tests."
    )


def _require_compat_writes_enabled() -> None:
    if _compat_writes_enabled():
        return
    raise HTTPException(
        status_code=503,
        detail=(
            "compatibility-root write endpoints are disabled by default; "
            "use the split-owner services, or set REALITY_RAG_ENABLE_COMPAT_WRITES=true "
            "for explicit legacy/smoke usage"
        ),
    )


class EnterDocumentRequest(BaseModel):
    tenant_id: str
    collection_id: str
    filename: str
    document_version: str = "v1"
    publish_version: str = "pub_001"
    visibility: str = "internal"
    content_text: str = ""
    source_binary_ref: str = ""
    source_metadata: dict[str, str] = Field(default_factory=dict)
    scan_verdict: str = "clean"
    scan_engine: str = "stub-av"
    scan_engine_version: str = "1.0"


class EnterBinaryDocumentRequest(BaseModel):
    tenant_id: str
    collection_id: str
    filename: str
    source_binary_ref: str
    document_version: str = "v1"
    publish_version: str = "pub_001"
    visibility: str = "internal"
    source_metadata: dict[str, str] = Field(default_factory=dict)
    scan_verdict: str = "clean"
    scan_engine: str = "stub-av"
    scan_engine_version: str = "1.0"


class ApproveAndPublishRequest(BaseModel):
    actor_id: str
    final_doc_id: str | None = None
    confirmed_tags: list[str] = Field(default_factory=list)
    index_profile_id: str = "idx_default"
    target_index_version_id: str | None = "idxv_col_policy_active"
    activate_index_version: bool = True


class SubmitApprovalRequest(BaseModel):
    actor_id: str
    final_doc_id: str | None = None
    confirmed_tags: list[str] = Field(default_factory=list)


class ApproveTicketRequest(BaseModel):
    actor_id: str
    confirmed_tags: list[str] = Field(default_factory=list)
    final_doc_id: str | None = None
    index_profile_id: str = "idx_default"
    target_index_version_id: str | None = "idxv_col_policy_active"
    activate_index_version: bool = True


class IntakeDocumentRecord(BaseModel):
    upload_id: str
    source_file_id: str
    intake_job_id: str
    tenant_id: str
    collection_id: str
    filename: str
    document_version: str
    publish_version: str
    visibility: str
    sanitized_asset_ref: str
    canonical_asset_ref: str
    metadata_ref: str
    source_binary_ref: str
    parse_snapshot_id: str
    trace_id: str
    source_metadata: dict[str, str]
    state: str
    source_file_state: str
    intake_job_state: str
    approval_ticket_id: str | None = None
    claimed_by_job_id: str | None = None
    source_file_claimed_at: str | None = None
    source_file_consumed_at: str | None = None
    source_file_cleaned_at: str | None = None
    upload_state: str = "completed"
    scan_result_id: str | None = None
    scan_verdict: str | None = None
    scan_completed_at: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    publish_state: str | None = None
    published_document_id: str | None = None
    final_doc_id: str | None = None


class ApprovalTicketRecord(BaseModel):
    ticket_id: str
    source_file_id: str
    intake_job_id: str
    tenant_id: str
    collection_id: str
    final_doc_id: str
    actor_id: str
    confirmed_tags: list[str] = Field(default_factory=list)
    state: str
    trace_id: str
    created_at: str
    decided_at: str | None = None
    decision: str | None = None
    approval_audit_ref: str | None = None


class IntakeService:
    def __init__(self) -> None:
        self._documents: dict[str, IntakeDocumentRecord] = {}
        self._tickets: dict[str, ApprovalTicketRecord] = {}
        self._publishing_facade = PublishingFacade()
        self._audit_store = PersistentRunAuditStore()

    def enter_document(self, request: EnterDocumentRequest) -> IntakeDocumentRecord:
        upload_id = f"upl_{uuid4().hex[:12]}"
        source_file_id = f"src_{uuid4().hex[:12]}"
        intake_job_id = f"job_{uuid4().hex[:12]}"
        trace_id = f"trc_{intake_job_id}"
        scan_result_id = f"scan_{uuid4().hex[:12]}"
        doc_dir = _runtime_dir() / source_file_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        sanitized_asset_ref = doc_dir / "sanitized.md"
        canonical_asset_ref = doc_dir / "canonical.md"
        metadata_ref = doc_dir / "metadata.json"
        source_binary_ref = doc_dir / request.filename
        if request.source_binary_ref and request.source_binary_ref.startswith("s3://"):
            import urllib.request as _ur
            import urllib.parse as _up
            s3_ep = _require_compat_service_url(
                "S3_ENDPOINT",
                default_url="http://127.0.0.1:9000",
                purpose="S3 source download",
            )
            _rest = request.source_binary_ref[5:]
            _bucket, _key = _rest.split("/", 1)
            _quoted_key = _up.quote(_key, safe="")
            _data = _ur.urlopen(f"{s3_ep}/{_bucket}/{_quoted_key}").read()
            source_binary_ref.write_bytes(_data)
            sanitized_asset_ref.write_bytes(_data)
            canonical_asset_ref.write_bytes(_data)
        else:
            sanitized_asset_ref.write_text(request.content_text, encoding="utf-8")
            canonical_asset_ref.write_text(request.content_text, encoding="utf-8")
            source_binary_ref.write_text(request.content_text, encoding="utf-8")
        metadata_ref.write_text(
            json.dumps(
                {
                    "upload_id": upload_id,
                    "tenant_id": request.tenant_id,
                    "collection_id": request.collection_id,
                    "filename": request.filename,
                    "entered_at": _utc_now(),
                    "scan_verdict": request.scan_verdict,
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

        source_file_state = SourceFileState.READY.value if request.scan_verdict == "clean" else SourceFileState.FAILED.value
        intake_job_state = IntakeJobState.CREATED.value if request.scan_verdict == "clean" else IntakeJobState.FAILED.value
        state = intake_job_state
        record = IntakeDocumentRecord(
            upload_id=upload_id,
            source_file_id=source_file_id,
            intake_job_id=intake_job_id,
            tenant_id=request.tenant_id,
            collection_id=request.collection_id,
            filename=request.filename,
            document_version=request.document_version,
            publish_version=request.publish_version,
            visibility=request.visibility,
            sanitized_asset_ref=str(sanitized_asset_ref),
            canonical_asset_ref=str(canonical_asset_ref),
            metadata_ref=str(metadata_ref),
            source_binary_ref=str(source_binary_ref),
            parse_snapshot_id="",
            trace_id=trace_id,
            source_metadata={"filename": request.filename, **request.source_metadata},
            state=state,
            source_file_state=source_file_state,
            intake_job_state=intake_job_state,
            scan_result_id=scan_result_id,
            scan_verdict=request.scan_verdict,
            scan_completed_at=_utc_now(),
            failure_code=None if request.scan_verdict == "clean" else "DOCUMENT_SCAN_FAILED",
            failure_message=None if request.scan_verdict == "clean" else f"scan_verdict={request.scan_verdict}",
        )
        self._documents[source_file_id] = record
        self._write_run_trace(
            record,
            root_status="CREATED" if request.scan_verdict == "clean" else "FAILED",
            final_doc_id=None,
            approval_ticket_id=None,
            debug_ref=f"dbg://intake/{record.trace_id}",
            result_count=0,
        )
        self._write_run_step(record.trace_id, "upload", "SUCCEEDED", f"upload_id={upload_id};source_file_state=UPLOADED")
        self._write_run_step(
            record.trace_id,
            "scan",
            "SUCCEEDED" if request.scan_verdict == "clean" else "FAILED",
            f"verdict={request.scan_verdict};engine={request.scan_engine}",
        )
        self._write_run_step(record.trace_id, "upload", "SUCCEEDED", f"source_file_state={record.source_file_state}")
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{record.source_file_id}/metadata",
            "upload_metadata",
            f"filename={record.filename};collection={record.collection_id}",
        )
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{record.scan_result_id}/scan-result",
            "scan_result",
            f"verdict={request.scan_verdict};engine={request.scan_engine};version={request.scan_engine_version}",
        )
        if request.scan_verdict == "clean":
            parse_preview_request = {
                "request_id": f"req_{source_file_id}",
                "tenant_id": request.tenant_id,
                "collection_id": request.collection_id,
                "source_file_id": source_file_id,
                "source_binary_ref": str(source_binary_ref),
                "filename": request.filename,
                "mime_type": "text/markdown",
                "collection_parser_config": {},
                "metadata": {
                    "tenant_id": request.tenant_id,
                    "collection_id": request.collection_id,
                    **request.source_metadata,
                },
                "trace_id": trace_id,
            }
            indexing_base_url = _require_compat_service_url(
                "REALITY_RAG_INDEXING_BASE_URL",
                default_url="http://127.0.0.1:18080",
                purpose="parse preview",
            )
            with httpx.Client(timeout=10.0) as client:
                preview_response = client.post(
                    f"{indexing_base_url}/internal/parse-previews",
                    json=parse_preview_request,
                )
                preview_response.raise_for_status()
                preview_payload = preview_response.json()
            record.parse_snapshot_id = str(preview_payload["parse_snapshot_id"])
            self._write_run_step(
                record.trace_id,
                "parse_preview_ready",
                "SUCCEEDED",
                f"parse_snapshot_id={record.parse_snapshot_id};parser_id={preview_payload['parser_id']}",
            )
            self._write_run_artifact(
                record.trace_id,
                f"art://intake/{record.source_file_id}/parse-snapshot",
                "parse_snapshot_ready",
                f"parse_snapshot_id={record.parse_snapshot_id};parser_id={preview_payload['parser_id']}",
            )
        return record

    def get(self, source_file_id: str) -> IntakeDocumentRecord:
        try:
            return self._documents[source_file_id]
        except KeyError as error:
            raise KeyError(f"Unknown source_file_id: {source_file_id}") from error

    def get_ticket(self, ticket_id: str) -> ApprovalTicketRecord:
        try:
            return self._tickets[ticket_id]
        except KeyError as error:
            raise KeyError(f"Unknown ticket_id: {ticket_id}") from error

    def submit_for_approval(self, source_file_id: str, request: SubmitApprovalRequest) -> ApprovalTicketRecord:
        record = self.get(source_file_id)
        if record.intake_job_state not in {IntakeJobState.CREATED.value, IntakeJobState.AWAITING_APPROVAL.value}:
            raise ValueError(f"Document {source_file_id} is not in an approval-requestable state")

        final_doc_id = request.final_doc_id or f"doc_{Path(record.filename).stem.replace(' ', '_')}"
        ticket_id = f"apv_{uuid4().hex[:12]}"
        ticket = ApprovalTicketRecord(
            ticket_id=ticket_id,
            source_file_id=record.source_file_id,
            intake_job_id=record.intake_job_id,
            tenant_id=record.tenant_id,
            collection_id=record.collection_id,
            final_doc_id=final_doc_id,
            actor_id=request.actor_id,
            confirmed_tags=request.confirmed_tags,
            state=ApprovalTicketState.PENDING.value,
            trace_id=record.trace_id,
            created_at=_utc_now(),
        )
        self._tickets[ticket_id] = ticket
        record.approval_ticket_id = ticket_id
        record.state = ApprovalTicketState.PENDING.value
        record.intake_job_state = IntakeJobState.AWAITING_APPROVAL.value
        self._write_run_trace(
            record,
            root_status="AWAITING_APPROVAL",
            final_doc_id=final_doc_id,
            approval_ticket_id=ticket_id,
            debug_ref=f"dbg://intake/{record.trace_id}",
            result_count=0,
        )
        self._write_run_step(record.trace_id, "approval_requested", "SUCCEEDED", f"ticket_id={ticket_id}")
        self._write_run_step(record.trace_id, "approval_pending", "PENDING", f"ticket_id={ticket_id}")
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{ticket_id}/approval",
            "approval_ticket",
            f"state={ticket.state};final_doc_id={final_doc_id}",
        )
        return ticket

    def approve_ticket(self, ticket_id: str, request: ApproveTicketRequest) -> dict[str, object]:
        ticket = self.get_ticket(ticket_id)
        if ticket.state != ApprovalTicketState.PENDING.value:
            raise ValueError(f"Ticket {ticket_id} is not pending")
        record = self.get(ticket.source_file_id)
        ticket.state = ApprovalTicketState.APPROVED.value
        ticket.actor_id = request.actor_id
        ticket.confirmed_tags = request.confirmed_tags
        ticket.decided_at = _utc_now()
        ticket.decision = "approve"
        record.state = IntakeJobState.APPROVAL_DECIDED.value
        record.intake_job_state = IntakeJobState.APPROVAL_DECIDED.value
        return self._publish_from_ticket(ticket, record, request)

    def approve_and_publish(self, source_file_id: str, request: ApproveAndPublishRequest) -> dict[str, object]:
        record = self.get(source_file_id)
        record.state = IntakeJobState.APPROVAL_DECIDED.value
        record.intake_job_state = IntakeJobState.APPROVAL_DECIDED.value
        ticket = ApprovalTicketRecord(
            ticket_id=f"apv_{uuid4().hex[:12]}",
            source_file_id=record.source_file_id,
            intake_job_id=record.intake_job_id,
            tenant_id=record.tenant_id,
            collection_id=record.collection_id,
            final_doc_id=request.final_doc_id or f"doc_{Path(record.filename).stem.replace(' ', '_')}",
            actor_id=request.actor_id,
            confirmed_tags=request.confirmed_tags,
            state=ApprovalTicketState.SYSTEM_DECIDED.value,
            trace_id=record.trace_id,
            created_at=_utc_now(),
            decided_at=_utc_now(),
            decision="approve",
        )
        self._tickets[ticket.ticket_id] = ticket
        record.approval_ticket_id = ticket.ticket_id
        return self._publish_from_ticket(ticket, record, request)

    def _publish_from_ticket(
        self,
        ticket: ApprovalTicketRecord,
        record: IntakeDocumentRecord,
        request: ApproveAndPublishRequest | ApproveTicketRequest,
    ) -> dict[str, object]:
        final_doc_id = request.final_doc_id or f"doc_{Path(record.filename).stem.replace(' ', '_')}"
        auto_approved = ticket.state == ApprovalTicketState.SYSTEM_DECIDED.value
        approval_ref = Path(record.metadata_ref).with_name("approval.json")
        approved_at = _utc_now()
        approval_ref.write_text(
            json.dumps(
                {
                    "decision": "approve",
                    "actor_id": request.actor_id,
                    "confirmed_tags": request.confirmed_tags,
                    "approved_at": approved_at,
                    "ticket_id": ticket.ticket_id,
                    "auto_approved": auto_approved,
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        audit_id = f"apa_{uuid4().hex[:12]}"
        approval_audit_ref = Path(record.metadata_ref).with_name("approval_audit_log.jsonl")
        approval_audit_entry = {
            "audit_id": audit_id,
            "ticket_id": ticket.ticket_id,
            "source_file_id": record.source_file_id,
            "intake_job_id": record.intake_job_id,
            "tenant_id": record.tenant_id,
            "collection_id": record.collection_id,
            "final_doc_id": final_doc_id,
            "decision": "approve",
            "actor_id": request.actor_id,
            "confirmed_tags": request.confirmed_tags,
            "auto_approved": auto_approved,
            "manual_override": False,
            "approved_at": approved_at,
        }
        with approval_audit_ref.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(approval_audit_entry, ensure_ascii=True) + "\n")
        ticket.approval_audit_ref = str(approval_audit_ref)
        governance_overlay_ref = Path(record.metadata_ref).with_name("governance-overlay.json")
        governance_overlay_ref.write_text(
            json.dumps(
                {
                    "source_file_id": record.source_file_id,
                    "final_doc_id": final_doc_id,
                    "visibility": record.visibility,
                    "confirmed_tags": request.confirmed_tags,
                    "publish_version": record.publish_version,
                    "approval_decision_ref": str(approval_ref),
                    "approval_audit_ref": str(approval_audit_ref),
                    "generated_at": approved_at,
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        publish_request = PublishRequest(
            tenant_id=record.tenant_id,
            collection_id=record.collection_id,
            source_file_id=record.source_file_id,
            final_doc_id=final_doc_id,
            document_version=record.document_version,
            publish_version=record.publish_version,
            visibility=record.visibility,
            source_binary_ref=record.source_binary_ref,
            parse_snapshot_id=record.parse_snapshot_id,
            governance_overlay_ref=str(governance_overlay_ref),
            sanitized_asset_ref=record.sanitized_asset_ref,
            canonical_asset_ref=record.canonical_asset_ref,
            metadata_ref=record.metadata_ref,
            index_profile_id=request.index_profile_id,
            target_index_version_id=request.target_index_version_id,
            trace_id=record.trace_id,
            source_metadata=record.source_metadata,
            approval=ApprovalDecision(
                decision="approve",
                actor_id=request.actor_id,
                confirmed_tags=request.confirmed_tags,
                approval_decision_ref=str(approval_ref),
            ),
        )
        record.state = IntakeJobState.PUBLISH_RUNNING.value
        record.intake_job_state = IntakeJobState.PUBLISH_RUNNING.value
        record.publish_state = PublishState.PUBLISH_CREATED.value
        self._write_run_trace(
            record,
            root_status="PUBLISH_RUNNING",
            final_doc_id=final_doc_id,
            approval_ticket_id=ticket.ticket_id,
            debug_ref=f"dbg://intake/{record.trace_id}",
            result_count=0,
        )
        self._write_run_step(
            record.trace_id,
            "approval_decided",
            "SUCCEEDED",
            f"ticket_id={ticket.ticket_id};decision=approve;auto_approved={str(auto_approved).lower()};manual_override=false",
        )
        command = self._publishing_facade.build_index_command(
            publish_request,
            build_request_id=f"ibr_{record.intake_job_id}",
        )
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{ticket.ticket_id}/approval-decision",
            "approval_decision",
            f"actor_id={request.actor_id};decision=approve;confirmed_tags={','.join(request.confirmed_tags)};auto_approved={str(auto_approved).lower()}",
        )
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{ticket.ticket_id}/approval-audit",
            "approval_audit_log",
            f"audit_id={audit_id};decision=approve;actor_id={request.actor_id};auto_approved={str(auto_approved).lower()}",
        )
        self._write_run_step(
            record.trace_id,
            "publish_started",
            "SUCCEEDED",
            f"publish_state={record.publish_state};final_doc_id={final_doc_id}",
        )
        record.publish_state = PublishState.ASSET_WRITING.value
        asset_files = [
            Path(record.sanitized_asset_ref),
            Path(record.canonical_asset_ref),
            Path(record.metadata_ref),
            approval_ref,
        ]
        total_asset_bytes = sum(path.stat().st_size for path in asset_files)
        try:
            asset_contents = tuple(path.read_bytes() for path in asset_files)
        except Exception:
            asset_contents = tuple(path.read_text(encoding="utf-8") for path in asset_files)
        asset_payload_hash = _payload_hash(*asset_contents)
        record.publish_state = PublishState.ASSET_WRITTEN.value
        self._write_run_step(
            record.trace_id,
            "asset_written",
            "SUCCEEDED",
            f"asset_count={len(asset_files)};asset_bytes_bucket={_size_bucket(total_asset_bytes)};payload_hash={asset_payload_hash}",
        )
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{record.intake_job_id}/publish-assets",
            "publish_assets",
            f"asset_count={len(asset_files)};asset_bytes_bucket={_size_bucket(total_asset_bytes)};payload_hash={asset_payload_hash}",
        )
        record.publish_state = PublishState.PERSISTING.value
        persisted_payload_hash = _payload_hash(
            final_doc_id,
            record.visibility,
            record.publish_version,
            record.document_version,
            ",".join(request.confirmed_tags),
        )
        # Persist published_document to DB so downstream archive/retract work
        from reality_rag_persistence.database import get_session
        from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository
        from reality_rag_contracts import PublishedDocumentState

        session = get_session()
        try:
            pd_repo = PublishedDocumentRepository(session)
            existing_pd = pd_repo.get_by_final_doc_id(final_doc_id)
            if existing_pd is None:
                pd_repo.create(
                    published_document_id=f"pd_{final_doc_id}",
                    final_doc_id=final_doc_id,
                    logical_document_id=final_doc_id,
                    tenant_id=record.tenant_id,
                    collection_id=record.collection_id,
                    version=1,
                    state=PublishedDocumentState.PUBLISHED,
                    created_by_ticket_id=ticket.ticket_id,
                )
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        record.publish_state = PublishState.PERSISTED.value
        self._write_run_step(
            record.trace_id,
            "document_persisted",
            "SUCCEEDED",
            f"final_doc_id={final_doc_id};published_document_state=PUBLISHED;payload_hash={persisted_payload_hash}",
        )
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{final_doc_id}/published-document",
            "published_document",
            f"final_doc_id={final_doc_id};published_document_state=PUBLISHED;payload_hash={persisted_payload_hash}",
        )
        record.publish_state = PublishState.INDEXING.value
        self._write_run_step(
            record.trace_id,
            "index_build_request",
            "SUCCEEDED",
            f"target_index_version_id={command.target_index_version_id}",
        )
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{record.intake_job_id}/index-build-request",
            "index_build_requested",
            f"build_request_id={command.build_request_id};final_doc_id={final_doc_id}",
        )

        indexing_base_url = _require_compat_service_url(
            "REALITY_RAG_INDEXING_BASE_URL",
            default_url="http://127.0.0.1:18080",
            purpose="index build",
        )
        with httpx.Client(timeout=60.0) as client:
            indexing_started_at = datetime.now(timezone.utc)
            response = client.post(
                f"{indexing_base_url}/internal/index-jobs",
                json=command.model_dump(mode="json", by_alias=True),
            )
            response.raise_for_status()
            payload = response.json()
            job_payload = client.get(f"{indexing_base_url}/internal/index-jobs/{payload['build_job_id']}")
            job_payload.raise_for_status()
            job = job_payload.json()
            if request.activate_index_version and command.target_index_version_id:
                activate = client.post(
                    f"{indexing_base_url}/internal/index-versions/{command.target_index_version_id}/activate"
                )
                activate.raise_for_status()
            version_payload = client.get(f"{indexing_base_url}/internal/index-versions/{job['index_version_id']}")
            version_payload.raise_for_status()
            version = version_payload.json()
        index_duration_ms = max(int((datetime.now(timezone.utc) - indexing_started_at).total_seconds() * 1000), 0)
        record.publish_state = PublishState.INDEXED.value
        self._write_run_step(
            record.trace_id,
            "index_upserted",
            "SUCCEEDED",
            "index_version="
            f"{job['index_version_id']};chunk_count_bucket={_size_bucket(int(version['chunk_count']))};"
            f"embedding_model_version={version['embedding_model']};index_latency_bucket={_latency_bucket(index_duration_ms)}",
        )
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{payload['build_job_id']}/index-upsert",
            "index_upsert",
            "index_version="
            f"{job['index_version_id']};chunk_count={version['chunk_count']};"
            f"embedding_model_version={version['embedding_model']};index_latency_bucket={_latency_bucket(index_duration_ms)}",
        )

        record.state = IntakeJobState.PUBLISHED.value
        record.source_file_state = SourceFileState.CLEANABLE.value
        record.intake_job_state = IntakeJobState.PUBLISHED.value
        record.publish_state = PublishState.PUBLISH_SUCCEEDED.value
        record.final_doc_id = final_doc_id
        record.published_document_id = f"pd_{final_doc_id}"
        self._write_run_trace(
            record,
            root_status="SUCCEEDED",
            final_doc_id=final_doc_id,
            approval_ticket_id=ticket.ticket_id,
            debug_ref=f"dbg://intake/{record.trace_id}",
            result_count=1,
        )
        self._write_run_step(
            record.trace_id,
            "publish_completed",
            "SUCCEEDED",
            "build_job_id="
            f"{payload['build_job_id']};index_version={job['index_version_id']};"
            f"chunk_count_bucket={_size_bucket(int(version['chunk_count']))};"
            f"embedding_model_version={version['embedding_model']}",
        )
        self._write_run_artifact(
            record.trace_id,
            f"art://intake/{record.intake_job_id}/publish-result",
            "publish_result",
            f"final_doc_id={final_doc_id};build_job_id={payload['build_job_id']}",
        )
        return {
            "source_file_id": record.source_file_id,
            "intake_job_id": record.intake_job_id,
            "ticket_id": ticket.ticket_id,
            "final_doc_id": final_doc_id,
            "trace_id": record.trace_id,
            "build_job_id": payload["build_job_id"],
            "index_version_id": command.target_index_version_id,
            "status": "PUBLISHED",
        }

    def _write_run_trace(
        self,
        record: IntakeDocumentRecord,
        *,
        root_status: str,
        final_doc_id: str | None,
        approval_ticket_id: str | None,
        debug_ref: str,
        result_count: int,
    ) -> None:
        _append_projection(
            "REALITY_RAG_RUN_TRACES_FILE",
            payload := {
                "trace_id": record.trace_id,
                "run_kind": "intake",
                "tenant_id": record.tenant_id,
                "collection_id": record.collection_id,
                "principal_id": approval_ticket_id or "system",
                "query_id": record.intake_job_id,
                "index_version_id": "pending",
                "profile_id": "intake",
                "root_status": root_status,
                "debug_ref": debug_ref,
                "result_count": result_count,
                "source_file_id": record.source_file_id,
                "intake_job_id": record.intake_job_id,
                "final_doc_id": final_doc_id,
                "approval_ticket_id": approval_ticket_id,
            },
        )
        self._audit_store.upsert_trace(
            trace_id=record.trace_id,
            run_kind="intake",
            tenant_id=record.tenant_id,
            collection_id=record.collection_id,
            principal_id=approval_ticket_id or "system",
            query_id=record.intake_job_id,
            index_version_id="pending",
            profile_id="intake",
            root_status=root_status,
            debug_ref=debug_ref,
            result_count=result_count,
            source_file_id=record.source_file_id,
            intake_job_id=record.intake_job_id,
            final_doc_id=final_doc_id,
            approval_ticket_id=approval_ticket_id,
            extra_json={},
        )

    def _write_run_step(self, trace_id: str, step_name: str, status: str, summary: str) -> None:
        payload = {
            "trace_id": trace_id,
            "step_name": step_name,
            "status": status,
            "summary": summary,
        }
        _append_projection("REALITY_RAG_RUN_STEPS_FILE", payload)
        self._audit_store.append_step(**payload)

    def _write_run_artifact(self, trace_id: str, artifact_ref: str, artifact_kind: str, summary: str) -> None:
        payload = {
            "trace_id": trace_id,
            "artifact_ref": artifact_ref,
            "artifact_kind": artifact_kind,
            "summary": summary,
        }
        _append_projection("REALITY_RAG_TRACE_ARTIFACTS_FILE", payload)
        self._audit_store.append_artifact(**payload)


service = IntakeService()
lineage = MainChainLineageInspector(_runtime_dir())
app = FastAPI(
    title="Reality-RAG Intake Pipeline Compat API",
    version="0.1.0",
    description="Compatibility-only intake API for smoke and legacy callers.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "intake-pipeline", "status": "ok"}


@app.post("/v1/documents")
def enter_document(request: EnterDocumentRequest) -> dict[str, object]:
    _require_compat_writes_enabled()
    try:
        record = service.enter_document(request)
    except CompatConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return record.model_dump(mode="json")


@app.get("/v1/documents/{source_file_id}")
def get_document(source_file_id: str) -> dict[str, object]:
    try:
        record = service.get(source_file_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return record.model_dump(mode="json")


@app.get("/internal/lineage/source-files/{source_file_id}")
def get_lineage_by_source_file(source_file_id: str) -> dict[str, object]:
    try:
        return lineage.get_by_source_file_id(source_file_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/internal/lineage/traces/{trace_id}")
def get_lineage_by_trace(trace_id: str) -> dict[str, object]:
    try:
        return lineage.get_by_trace_id(trace_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/v1/documents/{source_file_id}/approval-tickets")
def submit_for_approval(source_file_id: str, request: SubmitApprovalRequest) -> dict[str, object]:
    _require_compat_writes_enabled()
    try:
        ticket = service.submit_for_approval(source_file_id, request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ticket.model_dump(mode="json")


@app.get("/v1/approval-tickets/{ticket_id}")
def get_approval_ticket(ticket_id: str) -> dict[str, object]:
    try:
        ticket = service.get_ticket(ticket_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ticket.model_dump(mode="json")


@app.post("/v1/approval-tickets/{ticket_id}/approve")
def approve_ticket(ticket_id: str, request: ApproveTicketRequest) -> dict[str, object]:
    _require_compat_writes_enabled()
    try:
        return service.approve_ticket(ticket_id, request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CompatConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/v1/documents/{source_file_id}/approve-and-publish")
def approve_and_publish(source_file_id: str, request: ApproveAndPublishRequest) -> dict[str, object]:
    _require_compat_writes_enabled()
    try:
        return service.approve_and_publish(source_file_id, request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CompatConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


# -- New internal owner APIs for workbench consumption --------------------------------


class IntakeJobView(BaseModel):
    intake_job_id: str
    source_file_id: str
    tenant_id: str
    collection_id: str
    state: str
    current_stage: str | None = None
    parse_snapshot_id: str | None = None
    ticket_id: str | None = None
    published_document_id: str | None = None
    final_doc_id: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class PublishedDocumentView(BaseModel):
    published_document_id: str
    final_doc_id: str
    source_file_id: str
    intake_job_id: str
    tenant_id: str
    collection_id: str
    state: str
    version: int
    created_at: str
    updated_at: str


class SourceFileView(BaseModel):
    source_file_id: str
    upload_id: str | None = None
    tenant_id: str
    collection_id: str
    filename: str
    mime_type: str
    size_bytes: int
    state: str
    intake_job_id: str | None = None
    scan_verdict: str | None = None
    created_at: str
    updated_at: str


# Source-file owner mutation APIs were retired from the compat root service.
# document-service is the only supported owner for writes and lifecycle transitions
# on /internal/source-files*. The compat root retains read-only diagnostic views
# until the legacy smoke/helpers are fully retired.


@app.get("/internal/source-files/{source_file_id}")
def get_source_file(source_file_id: str) -> SourceFileView:
    from reality_rag_persistence.repositories.collections import CollectionRepository
    from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
    from reality_rag_persistence.repositories.source_files import SourceFileRepository
    from reality_rag_persistence.repositories.malware_scan_results import MalwareScanResultRepository

    session = get_session()
    try:
        source_file = SourceFileRepository(session).get(source_file_id)
        if source_file is None:
            raise HTTPException(status_code=404, detail=f"Unknown source_file_id: {source_file_id}")
        collection = CollectionRepository(session).get(source_file.collection_id)
        intake_job = IntakeJobRepository(session).get_by_source_file_id(source_file.source_file_id)
        scan_verdict = None
        if source_file.scan_result_id:
            scan_result = MalwareScanResultRepository(session).get(source_file.scan_result_id)
            if scan_result is not None:
                scan_verdict = scan_result.verdict
        return SourceFileView(
            source_file_id=source_file.source_file_id,
            upload_id=source_file.upload_id,
            tenant_id=(collection.tenant_id if collection is not None else "default"),
            collection_id=source_file.collection_id,
            filename=source_file.sanitized_name or source_file.original_name or "",
            mime_type="application/octet-stream",
            size_bytes=source_file.size_bytes,
            state=source_file.state.value,
            intake_job_id=(intake_job.intake_job_id if intake_job is not None else None),
            scan_verdict=scan_verdict,
            created_at=(source_file.created_at.isoformat() if source_file.created_at else _utc_now()),
            updated_at=(source_file.updated_at.isoformat() if source_file.updated_at else _utc_now()),
        )
    finally:
        session.close()


@app.get("/internal/intake-jobs/{intake_job_id}")
def get_intake_job(intake_job_id: str) -> IntakeJobView:
    from reality_rag_persistence.models import StageResultModel
    from reality_rag_persistence.repositories.collections import CollectionRepository
    from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
    from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository

    session = get_session()
    try:
        job = IntakeJobRepository(session).get(intake_job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Unknown intake_job_id: {intake_job_id}")
        collection = CollectionRepository(session).get(job.collection_id)
        parse_snapshot_id = None
        conversion_row = (
            session.query(StageResultModel)
            .filter(StageResultModel.intake_job_id == intake_job_id)
            .filter(StageResultModel.stage_name == "conversion")
            .first()
        )
        if conversion_row is not None and conversion_row.summary_json:
            parse_snapshot_id = conversion_row.summary_json.get("parse_snapshot_id")
        published_document = None
        if job.final_doc_id:
            published_document = PublishedDocumentRepository(session).get_by_final_doc_id(job.final_doc_id)
        return IntakeJobView(
            intake_job_id=job.intake_job_id,
            source_file_id=job.source_file_id,
            tenant_id=(collection.tenant_id if collection is not None else "default"),
            collection_id=job.collection_id,
            state=job.state,
            current_stage=job.current_stage,
            parse_snapshot_id=parse_snapshot_id,
            ticket_id=job.ticket_id,
            published_document_id=(
                published_document.published_document_id if published_document is not None else None
            ),
            final_doc_id=job.final_doc_id,
            error_message=job.error_message,
            created_at=(job.created_at.isoformat() if job.created_at else _utc_now()),
            updated_at=(job.updated_at.isoformat() if job.updated_at else _utc_now()),
        )
    finally:
        session.close()


@app.get("/internal/published-documents/{published_document_id}")
def get_published_document(published_document_id: str) -> PublishedDocumentView:
    """Get published document read-only view."""
    from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
    from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository

    session = get_session()
    try:
        published_document = PublishedDocumentRepository(session).get(published_document_id)
        if published_document is None:
            raise HTTPException(status_code=404, detail=f"Published document not found: {published_document_id}")
        intake_job = None
        source_file_id = ""
        for job in IntakeJobRepository(session).list_by_collection(published_document.collection_id):
            if job.final_doc_id == published_document.final_doc_id:
                intake_job = job
                source_file_id = job.source_file_id
                break
        return PublishedDocumentView(
            published_document_id=published_document.published_document_id,
            final_doc_id=published_document.final_doc_id,
            source_file_id=source_file_id,
            intake_job_id=(intake_job.intake_job_id if intake_job is not None else ""),
            tenant_id=published_document.tenant_id,
            collection_id=published_document.collection_id,
            state=published_document.state.value,
            version=published_document.version,
            created_at=(published_document.created_at.isoformat() if published_document.created_at else _utc_now()),
            updated_at=(published_document.updated_at.isoformat() if published_document.updated_at else _utc_now()),
        )
    finally:
        session.close()
