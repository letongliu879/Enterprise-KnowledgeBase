from __future__ import annotations

from pydantic import BaseModel, Field

from indexing_service._compat import StrEnum


class IndexRequestType(StrEnum):
    PUBLISH = "publish"
    REINDEX = "reindex"
    LIFECYCLE_TOMBSTONE = "lifecycle_tombstone"


class IndexBuildRequestedCommand(BaseModel):
    build_request_id: str
    request_type: IndexRequestType
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
    confirmed_tags: list[str] = Field(default_factory=list)
    source_metadata: dict[str, str]
    index_profile_id: str
    target_index_version_id: str | None = None
    idempotency_key: str
    trace_id: str
