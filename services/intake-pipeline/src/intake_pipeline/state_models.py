from __future__ import annotations

from pydantic import BaseModel, Field

from intake_pipeline._compat import StrEnum


class SourceFileState(StrEnum):
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    SCANNING = "SCANNING"
    READY = "READY"
    CLAIMED = "CLAIMED"
    CONSUMED = "CONSUMED"
    CLEANABLE = "CLEANABLE"
    CLEANED = "CLEANED"
    FAILED = "FAILED"


class IntakeJobState(StrEnum):
    CREATED = "CREATED"
    CONVERSION_QUEUED = "CONVERSION_QUEUED"
    CONVERSION_RUNNING = "CONVERSION_RUNNING"
    CONVERSION_SUCCEEDED = "CONVERSION_SUCCEEDED"
    REVIEW_QUEUED = "REVIEW_QUEUED"
    REVIEW_RUNNING = "REVIEW_RUNNING"
    REVIEW_SUCCEEDED = "REVIEW_SUCCEEDED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVAL_DECIDED = "APPROVAL_DECIDED"
    PUBLISH_QUEUED = "PUBLISH_QUEUED"
    PUBLISH_RUNNING = "PUBLISH_RUNNING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ApprovalTicketState(StrEnum):
    SYSTEM_DECIDED = "SYSTEM_DECIDED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"
    EXPIRED = "EXPIRED"


class PublishState(StrEnum):
    PUBLISH_CREATED = "PUBLISH_CREATED"
    ASSET_WRITING = "ASSET_WRITING"
    ASSET_WRITTEN = "ASSET_WRITTEN"
    PERSISTING = "PERSISTING"
    PERSISTED = "PERSISTED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    PUBLISH_SUCCEEDED = "PUBLISH_SUCCEEDED"
    PUBLISH_RETRY_SCHEDULED = "PUBLISH_RETRY_SCHEDULED"
    PUBLISH_FAILED = "PUBLISH_FAILED"


class PublishedDocumentSnapshot(BaseModel):
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
    approval_decision_ref: str
    confirmed_tags: list[str] = Field(default_factory=list)
    index_profile_id: str
    target_index_version_id: str | None = None
    trace_id: str
    source_metadata: dict[str, str]
