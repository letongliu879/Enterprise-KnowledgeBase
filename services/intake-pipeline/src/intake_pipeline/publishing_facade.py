from __future__ import annotations

from pydantic import BaseModel, Field

from intake_pipeline.indexing_command_gateway import IndexBuildRequestedCommand, IndexingCommandGateway
from intake_pipeline.state_models import PublishedDocumentSnapshot


class ApprovalDecision(BaseModel):
    decision: str
    actor_id: str
    confirmed_tags: list[str] = Field(default_factory=list)
    approval_decision_ref: str


class PublishRequest(BaseModel):
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
    index_profile_id: str
    target_index_version_id: str | None = None
    trace_id: str
    source_metadata: dict[str, str]
    approval: ApprovalDecision


class PublishingFacade:
    """Final-state intake seam: approved document -> publish snapshot -> indexing command."""

    def __init__(self, gateway: IndexingCommandGateway | None = None) -> None:
        self.gateway = gateway or IndexingCommandGateway()

    def to_published_snapshot(self, request: PublishRequest) -> PublishedDocumentSnapshot:
        if request.approval.decision != "approve":
            raise ValueError("Only approved documents may become publishable snapshots")
        return PublishedDocumentSnapshot(
            tenant_id=request.tenant_id,
            collection_id=request.collection_id,
            source_file_id=request.source_file_id,
            final_doc_id=request.final_doc_id,
            document_version=request.document_version,
            publish_version=request.publish_version,
            visibility=request.visibility,
            source_binary_ref=request.source_binary_ref,
            parse_snapshot_id=request.parse_snapshot_id,
            governance_overlay_ref=request.governance_overlay_ref,
            sanitized_asset_ref=request.sanitized_asset_ref,
            canonical_asset_ref=request.canonical_asset_ref,
            metadata_ref=request.metadata_ref,
            approval_decision_ref=request.approval.approval_decision_ref,
            confirmed_tags=request.approval.confirmed_tags,
            index_profile_id=request.index_profile_id,
            target_index_version_id=request.target_index_version_id,
            trace_id=request.trace_id,
            source_metadata=request.source_metadata,
        )

    def build_index_command(self, request: PublishRequest, *, build_request_id: str) -> IndexBuildRequestedCommand:
        snapshot = self.to_published_snapshot(request)
        return self.gateway.build_index_requested(snapshot, build_request_id=build_request_id)
