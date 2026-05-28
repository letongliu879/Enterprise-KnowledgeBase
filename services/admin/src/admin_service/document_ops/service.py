"""Document lifecycle ops service."""

from __future__ import annotations

import secrets

from reality_rag_contracts import IndexRequestType

from ..downstream_clients.publishing_worker_client import PublishingWorkerClient
from ..downstream_clients.indexing_client import IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..ops_audit.service import OpsAuditService
from .models import DocumentLifecycleRequest, DocumentReindexRequest, DocumentLifecycleResponse


class DocumentOpsService:
    def __init__(
        self,
        publishing_worker_client: PublishingWorkerClient,
        indexing_client: IndexingClient,
        audit_service: OpsAuditService,
    ) -> None:
        self._publishing = publishing_worker_client
        self._indexing = indexing_client
        self._audit = audit_service

    async def archive_document(
        self,
        final_doc_id: str,
        request: DocumentLifecycleRequest,
    ) -> DocumentLifecycleResponse:
        actor_id = request.actor or self._audit._actor_id or "system"
        idempotency_key = request.idempotency_key or f"archive:{final_doc_id}"

        try:
            result = await self._publishing.archive_document(
                final_doc_id,
                actor_id=actor_id,
                reason=request.reason,
                idempotency_key=idempotency_key,
            )
        except DownstreamError as e:
            self._audit.log_action(
                action="archive",
                target_type="document",
                target_id=final_doc_id,
                before_state="PUBLISHED",
                after_state="failed",
                reason=f"{e.code}: {e.message}",
                command_id=request.command_id,
                trace_id=request.trace_id,
                idempotency_key=idempotency_key,
            )
            raise

        self._audit.log_action(
            action="archive",
            target_type="document",
            target_id=final_doc_id,
            before_state=result.get("previous_state"),
            after_state="ARCHIVED",
            reason=request.reason,
            command_id=request.command_id,
            trace_id=request.trace_id,
            idempotency_key=idempotency_key,
        )
        return DocumentLifecycleResponse(
            success=result.get("success", True),
            final_doc_id=final_doc_id,
            previous_state=result.get("previous_state"),
            new_state="ARCHIVED",
        )

    async def retract_document(
        self,
        final_doc_id: str,
        request: DocumentLifecycleRequest,
    ) -> DocumentLifecycleResponse:
        actor_id = request.actor or self._audit._actor_id or "system"
        idempotency_key = request.idempotency_key or f"retract:{final_doc_id}"

        try:
            result = await self._publishing.retract_document(
                final_doc_id,
                actor_id=actor_id,
                reason=request.reason,
                idempotency_key=idempotency_key,
            )
        except DownstreamError as e:
            self._audit.log_action(
                action="retract",
                target_type="document",
                target_id=final_doc_id,
                before_state="PUBLISHED",
                after_state="failed",
                reason=f"{e.code}: {e.message}",
                command_id=request.command_id,
                trace_id=request.trace_id,
                idempotency_key=idempotency_key,
            )
            raise

        self._audit.log_action(
            action="retract",
            target_type="document",
            target_id=final_doc_id,
            before_state=result.get("previous_state"),
            after_state="RETRACTED",
            reason=request.reason,
            command_id=request.command_id,
            trace_id=request.trace_id,
            idempotency_key=idempotency_key,
        )
        return DocumentLifecycleResponse(
            success=result.get("success", True),
            final_doc_id=final_doc_id,
            previous_state=result.get("previous_state"),
            new_state="RETRACTED",
        )

    async def reindex_document(
        self,
        final_doc_id: str,
        request: DocumentReindexRequest,
    ) -> DocumentLifecycleResponse:
        actor_id = request.actor or self._audit._actor_id or "system"
        idempotency_key = request.idempotency_key or f"reindex:{final_doc_id}:{secrets.token_urlsafe(8)}"
        trace_id = request.trace_id or secrets.token_urlsafe(16)

        # Load parse snapshot from indexing service to construct the build command
        try:
            snapshot = await self._indexing.get_parse_snapshot(request.parse_snapshot_id)
        except DownstreamError as e:
            self._audit.log_action(
                action="reindex",
                target_type="document",
                target_id=final_doc_id,
                before_state="PUBLISHED",
                after_state="failed",
                reason=f"snapshot_load_failed: {e.code}: {e.message}",
                tenant_id=request.tenant_id,
                collection_id=request.collection_id,
                command_id=request.command_id,
                trace_id=trace_id,
                idempotency_key=idempotency_key,
            )
            raise

        build_request_id = f"reidx_{final_doc_id}_{secrets.token_urlsafe(8)}"
        command = {
            "build_request_id": build_request_id,
            "request_type": IndexRequestType.REINDEX.value,
            "tenant_id": request.tenant_id,
            "collection_id": request.collection_id,
            "source_file_id": snapshot.get("source_file_id", ""),
            "final_doc_id": final_doc_id,
            "document_version": "v1",
            "publish_version": "pub_001",
            "visibility": "internal",
            "source_binary_ref": snapshot.get("source_binary_ref", ""),
            "parse_snapshot_id": request.parse_snapshot_id,
            "governance_overlay_ref": "",
            "sanitized_asset_ref": "",
            "canonical_asset_ref": "",
            "metadata_ref": "",
            "quality_report_ref": None,
            "approval_decision_ref": "",
            "confirmed_tags": [],
            "source_metadata": {
                "filename": snapshot.get("source_filename", ""),
                "parse_snapshot_id": request.parse_snapshot_id,
            },
            "index_profile_id": request.index_profile_id,
            "target_index_version_id": None,
            "chunk_edit_refs": [],
            "idempotency_key": idempotency_key,
            "trace_id": trace_id,
        }

        try:
            result = await self._indexing.submit_index_job(command)
        except DownstreamError as e:
            self._audit.log_action(
                action="reindex",
                target_type="document",
                target_id=final_doc_id,
                before_state="PUBLISHED",
                after_state="failed",
                reason=f"{e.code}: {e.message}",
                tenant_id=request.tenant_id,
                collection_id=request.collection_id,
                command_id=request.command_id,
                trace_id=trace_id,
                idempotency_key=idempotency_key,
            )
            raise

        self._audit.log_action(
            action="reindex",
            target_type="document",
            target_id=final_doc_id,
            before_state="PUBLISHED",
            after_state="REINDEXING",
            reason=request.reason,
            tenant_id=request.tenant_id,
            collection_id=request.collection_id,
            command_id=request.command_id,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            payload={"build_job_id": result.get("build_job_id"), "build_request_id": build_request_id},
        )
        return DocumentLifecycleResponse(
            success=True,
            final_doc_id=final_doc_id,
            previous_state="PUBLISHED",
            new_state="REINDEXING",
            job_id=result.get("build_job_id"),
        )
