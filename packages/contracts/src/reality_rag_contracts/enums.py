"""Shared enums for Reality-RAG V2 contracts."""

from enum import Enum


class PublishStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    ARCHIVED = "archived"


class IndexStatus(str, Enum):
    NOT_INDEXED = "not_indexed"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    STALE = "stale"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputMode(str, Enum):
    EVIDENCE_ONLY = "evidence_only"
    WITH_METADATA = "with_metadata"
    PROMPT_TEXT = "prompt_text"


class BudgetPolicy(str, Enum):
    FOCUSED = "focused"
    BALANCED = "balanced"
    COMPREHENSIVE = "comprehensive"
    CITATION_ONLY = "citation_only"


class DocumentSupportTier(str, Enum):
    """Tier assigned during quality assessment."""
    A = "A"  # high-confidence automatic ingestion
    B = "B"  # automatic processing with quality scoring
    C = "C"  # OCR or human sampling likely required
    D = "D"  # not recommended for automatic ingestion


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    QUARANTINE = "quarantine"
    REQUEST_CHANGES = "request_changes"


class AdminRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    KNOWLEDGE_ADMIN = "knowledge_admin"
    REVIEWER = "reviewer"
    DEVELOPER_OPERATOR = "developer_operator"
    AUDITOR = "auditor"


class ConversionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"


class GovernanceSource(str, Enum):
    PERSISTED = "persisted"
    STUBBED = "stubbed"
    UNAVAILABLE = "unavailable"


class HumanReviewStatus(str, Enum):
    """Status of human review action on a document."""
    PENDING = "pending"
    APPROVED = "approved"
    DEFERRED = "deferred"


class SourceFileState(str, Enum):
    """Lifecycle states for a source file. Owner: document-service."""

    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    SCANNING = "scanning"
    READY = "ready"
    CLAIMED = "claimed"
    CONSUMED = "consumed"
    CLEANABLE = "cleanable"
    CLEANED = "cleaned"
    FAILED = "failed"


class UploadSessionStatus(str, Enum):
    """Lifecycle states for an upload session. Owner: document-service."""

    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ObjectBlobStatus(str, Enum):
    """Lifecycle states for an object blob. Owner: document-service."""

    ACTIVE = "active"
    GC_PENDING = "gc_pending"
    DELETED = "deleted"


class ScanVerdict(str, Enum):
    """Malware scan verdict. Owner: document-service."""

    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"


class IndexRegistryStatus(str, Enum):
    """Status of an index version in the registry."""
    INDEXING = "indexing"
    INDEXED = "indexed"


class IntakeJobState(str, Enum):
    """Lifecycle states for an intake job. Owner: intake-orchestrator."""

    CREATED = "created"
    CONVERSION_QUEUED = "conversion_queued"
    CONVERSION_RUNNING = "conversion_running"
    CONVERSION_SUCCEEDED = "conversion_succeeded"
    REVIEW_QUEUED = "review_queued"
    REVIEW_RUNNING = "review_running"
    REVIEW_SUCCEEDED = "review_succeeded"
    APPROVAL_REQUESTED = "approval_requested"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVAL_DECIDED = "approval_decided"
    PUBLISH_QUEUED = "publish_queued"
    PUBLISH_RUNNING = "publish_running"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class StageTaskState(str, Enum):
    """Lifecycle states for a stage task. Owner: intake-orchestrator."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    CANCELLED = "cancelled"


class StageAttemptState(str, Enum):
    """Lifecycle states for a single stage attempt. Owner: intake-orchestrator."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class StageName(str, Enum):
    """Logical stage names. Maps current 8 Python stages into 3 logical stages."""

    CONVERSION = "conversion"
    AGENT_REVIEW = "agent_review"
    PUBLISHING = "publishing"


class ApprovalTicketState(str, Enum):
    """Lifecycle states for an approval ticket. Owner: approval-service."""

    SYSTEM_DECIDED = "system_decided"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"
    EXPIRED = "expired"


class ApprovalAction(str, Enum):
    """Actions recorded in the approval audit log."""

    SYSTEM_APPROVE = "system_approve"
    SYSTEM_REJECT = "system_reject"
    APPROVE = "approve"
    REJECT = "reject"
    RETURN = "return"
    EXPIRE = "expire"


class PublishedDocumentState(str, Enum):
    """Lifecycle states for a published document. Owner: publishing domain."""

    PUBLISHED = "published"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"
    RETRACTED = "retracted"
    REINDEXING = "reindexing"


class PublishJobState(str, Enum):
    """Lifecycle states for a publish job. Owner: publishing-worker."""

    CREATED = "created"
    ASSET_WRITING = "asset_writing"
    PERSISTING = "persisting"
    INDEX_BUILDING = "index_building"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ReindexJobState(str, Enum):
    """Lifecycle states for a reindex job. Owner: publishing-worker."""

    CREATED = "created"
    INDEX_BUILDING = "index_building"
    ACTIVATING = "activating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IndexBuildJobState(str, Enum):
    """Lifecycle states for an index build job. Owner: indexing-service."""

    CREATED = "created"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    UPSERTING = "upserting"
    ACTIVATING = "activating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IndexedDocumentState(str, Enum):
    """State of a single document in an index version. Owner: indexing-service."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    TOMBSTONED = "tombstoned"


class VersionDecision(str, Enum):
    """Decision when a version conflict exists."""

    NEW_VERSION = "new_version"
    INDEPENDENT_DOCUMENT = "independent_document"
    BUSINESS_DUPLICATE = "business_duplicate"


class OutboxStatus(str, Enum):
    """Lifecycle states for an outbox event."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class EventType(str, Enum):
    """Core cross-owner event types. All cross-service events must use these."""

    FILE_READY = "FileReady"
    STAGE_TASK_REQUESTED = "StageTaskRequested"
    STAGE_COMPLETED = "StageCompleted"
    PARSE_PREVIEW_REQUESTED = "ParsePreviewRequested"
    PARSE_SNAPSHOT_READY = "ParseSnapshotReady"
    APPROVAL_REQUESTED = "ApprovalRequested"
    APPROVAL_PENDING = "ApprovalPending"
    APPROVAL_DECIDED = "ApprovalDecided"
    PUBLISH_REQUESTED = "PublishRequested"
    PUBLISH_COMPLETED = "PublishCompleted"
    INDEX_BUILD_REQUESTED = "IndexBuildRequested"
    INDEX_READY = "IndexReady"
    DOCUMENT_LIFECYCLE_CHANGED = "DocumentLifecycleChanged"


class TelemetryStatus(str, Enum):
    """Status values for telemetry events."""

    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"
    SKIPPED = "skipped"


class TelemetryEventName(str, Enum):
    """Fixed event name enumeration for telemetry_events.

    All stage lifecycle events must use these names.
    """

    # Upload / scan
    UPLOAD_STARTED = "upload_started"
    UPLOAD_COMPLETED = "upload_completed"
    UPLOAD_FAILED = "upload_failed"
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"

    # Conversion
    CONVERSION_STARTED = "conversion_started"
    CONVERSION_COMPLETED = "conversion_completed"
    CONVERSION_FAILED = "conversion_failed"

    # Quality / similarity / version
    QUALITY_SCORED = "quality_scored"
    SIMILARITY_CHECKED = "similarity_checked"
    VERSION_CHECKED = "version_checked"

    # Review
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    REVIEW_DEGRADED = "review_degraded"
    REVIEW_FAILED = "review_failed"

    # Approval
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_PENDING = "approval_pending"
    APPROVAL_DECIDED = "approval_decided"
    APPROVAL_RETURNED = "approval_returned"
    APPROVAL_EXPIRED = "approval_expired"

    # Publish
    PUBLISH_STARTED = "publish_started"
    PUBLISH_COMPLETED = "publish_completed"
    PUBLISH_FAILED = "publish_failed"
    ASSET_WRITTEN = "asset_written"
    DOCUMENT_PERSISTED = "document_persisted"
    INDEX_UPSERTED = "index_upserted"

    # Job
    INTAKE_JOB_COMPLETED = "intake_job_completed"
    INTAKE_JOB_FAILED = "intake_job_failed"
    INTAKE_JOB_CANCELLED = "intake_job_cancelled"


class LLMCallStatus(str, Enum):
    """Status values for llm_call_log entries."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SCHEMA_INVALID = "schema_invalid"
