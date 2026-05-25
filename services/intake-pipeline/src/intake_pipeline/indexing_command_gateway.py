from __future__ import annotations

from pydantic import BaseModel

from intake_pipeline.state_models import PublishedDocumentSnapshot


class IndexBuildRequestedCommand(BaseModel):
    build_request_id: str
    request_type: str
    tenant_id: str
    collection_id: str
    source_file_id: str
    final_doc_id: str
    document_version: str
    publish_version: str
    visibility: str
    source_binary_ref: str
    parse_snapshot_id: str
    governance_overlay_ref: str
    sanitized_asset_ref: str
    canonical_asset_ref: str
    metadata_ref: str
    quality_report_ref: str | None = None
    approval_decision_ref: str
    confirmed_tags: list[str]
    source_metadata: dict[str, str]
    index_profile_id: str
    target_index_version_id: str | None = None
    idempotency_key: str
    trace_id: str


class IndexingCommandGateway:
    """Canonical intake -> indexing seam. No alternate command types are emitted."""

    def build_index_requested(
        self,
        snapshot: PublishedDocumentSnapshot,
        *,
        build_request_id: str,
        request_type: str = "publish",
        quality_report_ref: str | None = None,
    ) -> IndexBuildRequestedCommand:
        target_version = snapshot.target_index_version_id or "active"
        idempotency_key = (
            f"{snapshot.final_doc_id}:{snapshot.publish_version}:{target_version}"
        )
        return IndexBuildRequestedCommand(
            build_request_id=build_request_id,
            request_type=request_type,
            tenant_id=snapshot.tenant_id,
            collection_id=snapshot.collection_id,
            source_file_id=snapshot.source_file_id,
            final_doc_id=snapshot.final_doc_id,
            document_version=snapshot.document_version,
            publish_version=snapshot.publish_version,
            visibility=snapshot.visibility,
            source_binary_ref=snapshot.source_binary_ref,
            parse_snapshot_id=snapshot.parse_snapshot_id,
            governance_overlay_ref=snapshot.governance_overlay_ref,
            sanitized_asset_ref=snapshot.sanitized_asset_ref,
            canonical_asset_ref=snapshot.canonical_asset_ref,
            metadata_ref=snapshot.metadata_ref,
            quality_report_ref=quality_report_ref,
            approval_decision_ref=snapshot.approval_decision_ref,
            confirmed_tags=snapshot.confirmed_tags,
            source_metadata=snapshot.source_metadata,
            index_profile_id=snapshot.index_profile_id,
            target_index_version_id=snapshot.target_index_version_id,
            idempotency_key=idempotency_key,
            trace_id=snapshot.trace_id,
        )
