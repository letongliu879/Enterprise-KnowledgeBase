"""Core Pydantic models for Reality-RAG V2 contracts.

All cross-service communication MUST use these models.
No service may invent its own field names or shapes for these concepts.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from .enums import (
    AdminRole,
    ApprovalAction,
    ApprovalTicketState,
    BudgetPolicy,
    ConversionStatus,
    DocumentSupportTier,
    GovernanceSource,
    IndexBuildJobState,
    IndexStatus,
    IndexedDocumentState,
    JobStatus,
    OutputMode,
    PublishJobState,
    PublishedDocumentState,
    PublishStatus,
    ReindexJobState,
    ReviewDecision,
    SourceFileState,
    VersionDecision,
)


# ── Tenant & Organisation ────────────────────────────────────────────


class Tenant(BaseModel):
    tenant_id: str = Field(description="Unique tenant identifier")
    name: str = Field(description="Human-readable tenant name")


# ── Collection ────────────────────────────────────────────────────────


class Collection(BaseModel):
    collection_id: str = Field(description="Unique collection identifier")
    tenant_id: str
    name: str
    description: str = ""
    authority_level: int = Field(default=0, ge=0, le=10)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Application Profile ──────────────────────────────────────────────


class ApplicationProfile(BaseModel):
    application_profile_id: str = Field(description="Unique profile identifier")
    tenant_id: str
    name: str
    allowed_collections: list[str] = Field(default_factory=list)
    default_collections: list[str] = Field(default_factory=list)
    allow_cross_collection: bool = False
    default_token_budget: int = Field(default=4096, gt=0)
    default_budget_policy: BudgetPolicy = BudgetPolicy.BALANCED
    metadata_policy: str = "minimal"
    debug_permission: bool = False
    rate_limit: int = Field(default=100, description="Requests per minute")


# ── Permission Context ────────────────────────────────────────────────


class PermissionContext(BaseModel):
    """Captures the resolved permission scope for a single retrieval request."""

    tenant_id: str
    user_id: Optional[str] = None
    application_profile_id: str
    role_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    department_ids: list[str] = Field(default_factory=list)
    clearance_level: int = Field(default=0, ge=0, le=10)
    attributes: dict[str, Any] = Field(default_factory=dict)
    collection_scope: list[str] = Field(
        description="List of collection_ids this caller may search"
    )
    permission_scope_hash: str = Field(
        description="Deterministic hash of the permission scope; participates in cache key"
    )
    policy_snapshot_version: str = "v1"


class PrincipalProfile(BaseModel):
    tenant_id: str
    user_id: str
    role_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    department_ids: list[str] = Field(default_factory=list)
    clearance_level: int = Field(default=0, ge=0, le=10)
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PolicySubject(BaseModel):
    subject_type: str = Field(description="user | role | group | department | tenant")
    subject_id: str


class PolicyCondition(BaseModel):
    field: str = Field(
        description="clearance_level | domain_tag | attribute:<name> | effective_date"
    )
    operator: str = Field(description="eq | in | gte | lte | contains | overlaps")
    value: Any


class DocumentPolicy(BaseModel):
    policy_id: str
    tenant_id: str
    collection_id: str
    doc_id: str
    effect: str = Field(description="allow | deny")
    subjects: list[PolicySubject] = Field(default_factory=list)
    conditions: list[PolicyCondition] = Field(default_factory=list)
    priority: int = Field(default=100, ge=0)
    policy_version: str = "v1"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Trusted Knowledge Asset Metadata ──────────────────────────────────


class CanonicalMetadata(BaseModel):
    """Enterprise governance record attached to every canonical asset."""

    tenant_id: str
    collection_id: str
    doc_id: str = Field(description="Document asset version id")
    logical_document_id: str = Field(
        description="Stable logical id across versions of the same document"
    )
    source_hash: str = Field(description="SHA-256 of the original source file")
    source_content_hash: str = Field(default="", description="Content hash of the source file bytes (for published doc dedup)")
    version: int = Field(default=1, ge=1)
    archived: bool = Field(default=False, description="Soft-delete flag; archived docs are excluded from retrieval")
    publish_status: PublishStatus = PublishStatus.DRAFT
    index_status: IndexStatus = IndexStatus.NOT_INDEXED
    effective_date: Optional[datetime] = None
    authority_level: int = Field(default=0, ge=0, le=10)
    governance_level: str = "standard"
    access_policy: str = "collection_default"
    domain_tags: list[str] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)
    quality_summary: str = ""
    processing_summary: str = ""
    asset_paths: dict[str, str] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Quality Report ────────────────────────────────────────────────────


class QualityReport(BaseModel):
    doc_id: str
    support_tier: DocumentSupportTier = DocumentSupportTier.B
    conversion_score: float = Field(default=1.0, ge=0.0, le=1.0)
    ocr_used: bool = False
    ocr_confidence_summary: dict[str, float] = Field(default_factory=dict)
    garbled_text_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    blank_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    table_extraction_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    image_density: float = Field(default=0.0, ge=0.0)
    source_canonical_length_mismatch: float = Field(default=0.0, ge=0.0)
    truncation_suspicion: bool = False
    recommended_review_status: PublishStatus = PublishStatus.PENDING_REVIEW
    blocking_reasons: list[str] = Field(default_factory=list)


# ── Agent Review ──────────────────────────────────────────────────────


class PIIItem(BaseModel):
    pii_type: str = ""
    description: str = ""
    severity: str = "low"


class AgentReview(BaseModel):
    doc_id: str
    decision: Optional[ReviewDecision] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    publish_recommendation: Optional[PublishStatus] = None
    sections_requiring_review: list[str] = Field(default_factory=list)
    document_type: str = ""
    suggested_authority_level: int = Field(default=0, ge=0, le=10)
    detected_pii: list[PIIItem] = Field(default_factory=list)
    diff_summary: str = ""


class ProcessingRecord(BaseModel):
    doc_id: str
    job_id: str
    collection_id: str
    source_file_path: str
    source_hash: str
    conversion_status: ConversionStatus
    tool_chain: list[str] = Field(default_factory=list)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error_message: str = ""
    published_asset_paths: dict[str, str] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


# ── Retrieval Contracts ───────────────────────────────────────────────


class EvidenceItem(BaseModel):
    """A single piece of evidence returned by retrieval."""

    evidence_id: str
    doc_id: str
    collection_id: str
    canonical_source: str = Field(description="Path to canonical.md within object storage")
    content: str = Field(description="The retrieved text chunk")
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    chunk_metadata: dict[str, Any] = Field(default_factory=dict)


class QueryIntent(BaseModel):
    """Normalized retrieval intent used by strategy and cache layers."""

    normalized_query: str
    keywords: list[str] = Field(default_factory=list)
    time_scope: str = "any"
    query_intent_version: str = "v1"


class RetrievalMetadata(BaseModel):
    retrieval_time_ms: int = Field(default=0, ge=0)
    collections_searched: list[str] = Field(default_factory=list)
    index_versions_used: dict[str, str] = Field(default_factory=dict)
    total_evidence_count: int = Field(default=0, ge=0)
    cache_hit: bool = False
    normalized_query: str = ""
    budget_policy: BudgetPolicy = BudgetPolicy.BALANCED
    applied_token_budget: int = Field(default=0, ge=0)
    query_intent: QueryIntent | None = None


class KnowledgeContext(BaseModel):
    """The primary product output of Reality-RAG."""

    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    assembled_context: str = Field(
        default="",
        description="Assembled text ready for LLM consumption (no final answer)",
    )
    retrieval_metadata: RetrievalMetadata = Field(default_factory=RetrievalMetadata)


# ── Retrieval Request / Response ──────────────────────────────────────


class RetrievalRequest(BaseModel):
    """Full retrieval request as seen by retrieval-service."""

    query: str
    tenant_id: str
    application_profile_id: str
    permission_context: PermissionContext
    resolved_collection_ids: list[str] = Field(default_factory=list)
    token_budget: int = Field(default=4096, gt=0)
    budget_policy: BudgetPolicy = BudgetPolicy.BALANCED
    max_results: int = Field(default=10, gt=0)
    output_mode: OutputMode = OutputMode.EVIDENCE_ONLY
    metadata_policy: str = "minimal"


class RetrievalResponse(BaseModel):
    """Response from retrieval-service /internal/retrieve."""

    knowledge_context: KnowledgeContext


# ── ContextWeaver Adapter Contracts ───────────────────────────────────


class CWSearchRequest(BaseModel):
    """Request to contextweaver-adapter search."""

    collection_id: str
    index_version: str
    query: str
    top_k: int = Field(default=10, gt=0)
    search_params: dict[str, Any] = Field(default_factory=dict)


class CWSearchResponse(BaseModel):
    """Response from contextweaver-adapter search."""

    evidence_items: list[EvidenceItem]


class CWIndexRequest(BaseModel):
    """Request to contextweaver-adapter index (offline only)."""

    collection_id: str
    index_version: str
    canonical_asset_paths: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class CWIndexResponse(BaseModel):
    """Response from contextweaver-adapter index."""

    job_id: str
    status: IndexStatus = IndexStatus.INDEXING
    collection_id: str
    index_version: str


# ── Access API Contracts ──────────────────────────────────────────────


class AccessRetrieveRequest(BaseModel):
    """Request to access-api POST /v1/retrieve."""

    query: str
    tenant_id: str = "default"
    application_profile_id: str
    user_id: Optional[str] = None
    max_results: int = Field(default=10, gt=0)
    token_budget: int = Field(default=4096, gt=0)
    budget_policy: BudgetPolicy = BudgetPolicy.BALANCED
    output_mode: OutputMode = OutputMode.EVIDENCE_ONLY


class AccessRetrieveResponse(BaseModel):
    """Response from access-api POST /v1/retrieve."""

    knowledge_context: KnowledgeContext


# ── Admin API Contracts ───────────────────────────────────────────────


class GovernanceAssetRef(BaseModel):
    """Reference to a governance sidecar asset in object storage."""

    doc_id: str
    asset_type: str = Field(
        description="canonical_md | canonical_meta | quality_report | agent_review | processing_record"
    )
    storage_backend: str = Field(
        default="object_storage", description="object_storage | local_sidecar"
    )
    asset_path: str = Field(description="Path/key within the storage backend")
    content_hash: str = Field(default="", description="SHA-256 of the asset content")
    size_bytes: int = Field(default=0, ge=0)


class DocumentSummary(BaseModel):
    doc_id: str
    logical_document_id: str
    collection_id: str
    publish_status: PublishStatus
    index_status: IndexStatus
    version: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentDetail(BaseModel):
    doc_id: str
    logical_document_id: str
    collection_id: str
    tenant_id: str
    publish_status: PublishStatus
    index_status: IndexStatus
    version: int
    source_hash: str
    canonical_metadata: CanonicalMetadata
    quality_report: Optional[QualityReport] = None
    agent_review: Optional[AgentReview] = None
    governance_assets: list[GovernanceAssetRef] = Field(default_factory=list)
    quality_report_source: GovernanceSource = GovernanceSource.UNAVAILABLE
    agent_review_source: GovernanceSource = GovernanceSource.UNAVAILABLE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CollectionSummary(BaseModel):
    collection_id: str
    tenant_id: str
    name: str
    description: str
    document_count: int = 0
    authority_level: int = 0


class JobInfo(BaseModel):
    job_id: str
    job_type: str
    status: JobStatus
    collection_id: Optional[str] = None
    doc_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None


# ── Health ─────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = ""
    version: str = "0.1.0"


# ── Cache Key ─────────────────────────────────────────────────────────


# ── Ingestion Contracts ────────────────────────────────────────────────


class ConversionRequest(BaseModel):
    """Request to convert a source file to canonical markdown."""

    source_file_path: str = Field(description="Path as string; service layer converts to Path")
    collection_id: str = Field(description="Target collection for this conversion")
    options: dict[str, Any] = Field(default_factory=dict, description="Optional converter hints")


class ConversionResult(BaseModel):
    """Result of converting a single source file.

    Note: `canonical_md` may contain the full markdown body.
    Admin API list endpoints must NOT include `canonical_md` in bulk responses.
    """

    source_file_path: str
    conversion_status: ConversionStatus
    doc_id: str = ""
    canonical_asset_path: str = ""
    canonical_md: str = ""
    error_message: str = ""
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversionReport(BaseModel):
    """Aggregate report for a batch of file conversions."""

    report_id: str = Field(description="Unique report identifier")
    job_id: str = Field(description="Links to parent IngestionJob")
    source_file_path: str
    conversion_status: ConversionStatus
    total_files: int = 1
    successful: int = 0
    failed: int = 0
    unsupported: int = 0
    error_message: str = ""
    warnings: list[str] = Field(default_factory=list)
    details: list[ConversionResult] = Field(default_factory=list, description="Per-file results")
    created_at: Optional[datetime] = None


class UploadSession(BaseModel):
    """An upload session record. Owner: document-service."""

    upload_id: str
    source: str = Field(default="web", description="web / cli / feishu / webhook")
    user_id: Optional[str] = None
    trace_id: str = ""
    status: str = Field(default="active", description="UploadSessionStatus value")
    expected_size: Optional[int] = None
    expected_sha256: Optional[str] = None
    received_size: int = 0
    created_at: Optional[datetime] = None
    last_chunk_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ObjectBlob(BaseModel):
    """A physical object blob record. Owner: document-service."""

    object_id: str = Field(description="PK, e.g. obj_sha256_abcd...")
    content_hash: str = Field(description="SHA-256 of the content, unique")
    storage_key: str = Field(description="Path/key in object storage")
    size_bytes: int = Field(default=0, ge=0)
    ref_count: int = Field(default=0, ge=0)
    status: str = Field(default="active", description="ObjectBlobStatus value")
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class MalwareScanResult(BaseModel):
    """Malware scan result record. Owner: document-service."""

    scan_result_id: str
    source_file_id: str
    engine: str
    engine_version: str
    verdict: str = Field(default="clean", description="ScanVerdict value")
    signature: Optional[str] = None
    scanned_at: Optional[datetime] = None
    raw_result_ref: Optional[str] = None


class SourceFile(BaseModel):
    """A source file record per collection, tracking upload and consumption lifecycle.

    Owner: document-service.
    """

    source_file_id: str
    upload_id: Optional[str] = None
    object_id: str = Field(description="Derived from content_hash, e.g. obj_sha256_abc...")
    collection_id: str
    visibility: str = Field(default="INTERNAL", description="EXTERNAL / INTERNAL")
    original_name: str = ""
    sanitized_name: str = ""
    content_hash: str = Field(description="SHA-256 of the source file bytes")
    size_bytes: int = Field(default=0, ge=0)
    state: SourceFileState = SourceFileState.READY
    claimed_by_job_id: Optional[str] = None
    scan_result_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class IngestionJob(BaseModel):
    """Tracks an ingestion job from file intake through conversion."""

    job_id: str
    job_type: str = "ingestion"
    status: JobStatus  # reuses existing JobStatus enum
    collection_id: str
    source_files: list[str] = Field(default_factory=list)
    source_file_ids: list[str] = Field(default_factory=list, description="Internal source file IDs")
    conversion_report: Optional[ConversionReport] = None
    report_asset_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None


class IndexJobRequest(BaseModel):
    """Request to run an offline index job for an ingestion batch."""

    job_id: str
    collection_id: str
    index_version: str = "v1"
    options: dict[str, Any] = Field(default_factory=dict)


class IndexJobResult(BaseModel):
    """Result of running an offline index job."""

    job_id: str
    collection_id: str
    index_version: str
    status: JobStatus
    documents_indexed: int = Field(default=0, ge=0)
    chunks_indexed: int = Field(default=0, ge=0)
    backend_mode: str = "noop"
    error_message: Optional[str] = None


class IndexSwitchRequest(BaseModel):
    """Request to activate or rollback an index version."""

    collection_id: str
    index_version: Optional[str] = None


class IndexSwitchResult(BaseModel):
    """Result of activating or rolling back an index version."""

    collection_id: str
    active_index_version: str
    previous_index_version: Optional[str] = None
    target_index_version: Optional[str] = None
    status: str


# ── Cache Key ─────────────────────────────────────────────────────────


class CacheKeyComponents(BaseModel):
    """Components that MUST be included in every retrieval cache key."""

    tenant_id: str
    user_id: str = ""
    application_profile_id: str
    collection_scope: list[str]
    index_version: dict[str, str] = Field(
        description="Mapping of collection_id -> index_version"
    )
    permission_scope_hash: str
    policy_snapshot_version: str = "v1"
    normalized_query: str
    query_intent_version: str = "v1"
    retrieval_params: str = Field(
        description="Serialized retrieval params (max_results, etc.)"
    )
    token_budget: int
    budget_policy: BudgetPolicy = BudgetPolicy.BALANCED
    output_mode: str
    metadata_policy: str


class ChunkAsset(BaseModel):
    """Canonical chunk asset emitted by ingestion/indexing."""

    chunk_id: str
    doc_id: str
    collection_id: str
    chunk_index: int = Field(ge=0)
    canonical_source: str
    heading: str = ""
    content: str
    token_estimate: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpenSearchIndexRecord(BaseModel):
    """Serialized record ready for OpenSearch bulk indexing."""

    index_name: str
    document_id: str
    body: dict[str, Any] = Field(default_factory=dict)


class QdrantPointRecord(BaseModel):
    """Serialized point payload ready for Qdrant upsert."""

    collection_name: str
    point_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class IndexAssetBundle(BaseModel):
    """Bundle of per-document index assets emitted during ingestion/index preparation."""

    indexed_document_id: str = ""
    doc_id: str
    collection_id: str
    index_version: str = "v1"
    canonical_source: str
    document_metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[ChunkAsset] = Field(default_factory=list)
    opensearch_records: list[OpenSearchIndexRecord] = Field(default_factory=list)
    qdrant_points: list[QdrantPointRecord] = Field(default_factory=list)


# ── Orchestrator Contracts ─────────────────────────────────────────────


class IntakeJob(BaseModel):
    """Persistent intake job record. Owner: intake-orchestrator."""

    intake_job_id: str
    source_file_id: str
    object_id: str
    collection_id: str
    state: Any = Field(default="created", description="IntakeJobState value")
    state_version: int = Field(default=1, ge=1)
    current_stage: Optional[str] = Field(default=None, description="StageName value or null")
    preliminary_doc_id: Optional[str] = None
    review_id: Optional[str] = None
    ticket_id: Optional[str] = None
    final_doc_id: Optional[str] = None
    publish_id: Optional[str] = None
    attempt_count: int = Field(default=0, ge=0)
    trace_id: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    error_message: Optional[str] = None


class StageTask(BaseModel):
    """Persistent stage task record. Owner: intake-orchestrator."""

    stage_task_id: str
    intake_job_id: str
    stage_name: str = Field(description="StageName value")
    idempotency_key: str
    schema_version: str = "v1"
    input_hash: str
    state: str = Field(default="queued", description="StageTaskState value")
    locked_by: Optional[str] = None
    lock_expires_at: Optional[datetime] = None
    attempt_count: int = Field(default=0, ge=0)
    rerun_round: int = Field(default=0, ge=0)
    rerun_reason_code: Optional[str] = None
    next_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StageAttempt(BaseModel):
    """Persistent stage attempt record. Owner: intake-orchestrator."""

    stage_attempt_id: str
    stage_task_id: str
    intake_job_id: str
    stage_name: str = Field(description="StageName value")
    attempt_no: int = Field(default=1, ge=1)
    worker_id: Optional[str] = None
    state: str = Field(default="running", description="StageAttemptState value")
    error_code: Optional[str] = None
    error_summary_hash: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class StageResult(BaseModel):
    """Persistent stage result record (success only). Owner: intake-orchestrator."""

    stage_result_id: str
    stage_task_id: str = Field(description="FK, also unique")
    stage_attempt_id: str
    intake_job_id: str
    stage_name: str = Field(description="StageName value")
    idempotency_key: str
    result_hash: str
    result_ref: Optional[str] = None
    summary_json: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


# ── Approval Contracts ─────────────────────────────────────────────────


class ApprovalTicket(BaseModel):
    """Approval ticket record. Owner: approval-service."""

    ticket_id: str
    intake_job_id: str
    approval_round: int = Field(default=1, ge=1)
    preliminary_doc_id: str
    collection_id: str
    state: ApprovalTicketState = ApprovalTicketState.PENDING
    routing_recommendation: str = "auto_approve"
    decision: Optional[str] = None  # approve / reject / return
    decision_actor: Optional[str] = None  # user id or "system"
    decision_reason: Optional[str] = None
    final_doc_id: Optional[str] = None
    confirmed_tags: list[str] = Field(default_factory=list)
    return_target_stage: Optional[str] = None
    return_reason: Optional[str] = None
    version_decision: Optional[VersionDecision] = None
    supersedes_final_doc_id: Optional[str] = None
    created_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class ApprovalAuditLog(BaseModel):
    """Approval audit log — append only. Owner: approval-service."""

    audit_id: str
    ticket_id: str
    intake_job_id: str
    actor_id: str
    action: ApprovalAction
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    reason: Optional[str] = None
    payload_hash: str = ""
    created_at: Optional[datetime] = None


# ── Outbox Contracts ───────────────────────────────────────────────────


class OutboxEvent(BaseModel):
    """Outbox event record. Each owner schema has its own outbox table.

    Producer writes outbox_events in the same DB transaction as business state.
    Dispatcher polls pending events and delivers them asynchronously.
    """

    event_id: str
    event_type: str = Field(description="EventType value")
    aggregate_type: str = Field(description="Domain aggregate type, e.g. intake_job")
    aggregate_id: str = Field(description="Domain aggregate id, e.g. intake_job_id")
    schema_version: str = "2026-05-21.v1"
    payload_json: dict[str, Any] = Field(default_factory=dict)
    payload_hash: str = ""
    idempotency_key: Optional[str] = None
    trace_id: str = ""
    status: str = Field(default="pending", description="OutboxStatus value")
    attempt_count: int = Field(default=0, ge=0)
    next_attempt_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    @property
    def payload(self) -> dict[str, Any]:
        """Alias for payload_json — matches event schema terminology."""
        return self.payload_json


class ConsumerIdempotency(BaseModel):
    """Consumer-side idempotency record.

    Each consumer records processed (event_id, idempotency_key) pairs
    to guard against duplicate event delivery.
    """

    consumer_id: str = Field(description="Consumer component name, e.g. orchestrator")
    event_id: str
    idempotency_key: Optional[str] = None
    processed_at: Optional[datetime] = None


# ── Telemetry Contracts ─────────────────────────────────────────────────


class TelemetryEvent(BaseModel):
    """Structured telemetry event for observability and analytics.

    Does NOT store document bodies, PII raw values, full prompt text,
    or full LLM response text.
    """

    event_id: str
    event_name: str = Field(description="TelemetryEventName value")
    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = "2026-05-21.v1"
    trace_id: str
    intake_job_id: Optional[str] = None
    source_file_id: Optional[str] = None
    collection_id: Optional[str] = None
    visibility: Optional[str] = Field(default=None, description="INTERNAL / EXTERNAL / null")
    stage_name: Optional[str] = None
    stage_task_id: Optional[str] = None
    ticket_id: Optional[str] = None
    final_doc_id: Optional[str] = None
    component: str = Field(description="Component that emitted the event, e.g. conversion-worker")
    component_version: str = "0.1.0"
    status: str = Field(default="started", description="TelemetryStatus value")
    duration_ms: Optional[int] = None
    error_code: Optional[str] = None
    retry_count: int = 0
    attributes_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized attributes only: enums, counts, hashes, buckets, versions",
    )


class LLMCallLog(BaseModel):
    """Per-LLM-call metadata record.

    Stores hashes and metadata, NOT prompt/response plaintext.
    """

    llm_call_id: str
    trace_id: str
    intake_job_id: str
    stage_task_id: str
    review_id: Optional[str] = None
    provider: str
    model_name: str
    model_version: str
    prompt_version: str
    policy_version: str
    request_hash: str = Field(description="SHA-256 of the request payload")
    response_hash: Optional[str] = Field(default=None, description="SHA-256 of the response body")
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None
    total_token_count: Optional[int] = None
    latency_ms: Optional[int] = None
    timeout_ms: int
    status: str = Field(default="succeeded", description="LLMCallStatus value")
    error_code: Optional[str] = None
    retry_count: int = 0
    json_parse_success: bool = False
    schema_validation_success: bool = False
    redaction_before_send: bool = False
    external_model_used: bool = True
    created_at: Optional[datetime] = None


class ReviewQualityFeedback(BaseModel):
    """Links agent-review output to approval decision for quality analysis.

    Enables answering: which prompt_version has highest return rate,
    which PII type has most false positives, etc.
    """

    feedback_id: str
    review_id: str
    intake_job_id: str
    ticket_id: Optional[str] = None
    collection_id: str
    visibility: str = Field(description="INTERNAL / EXTERNAL")
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    routing_recommendation: str = Field(default="auto_approve", description="auto_approve / require_approval")
    review_status: str = Field(default="succeeded", description="succeeded / degraded / failed")
    pii_count_by_type: dict[str, int] = Field(default_factory=dict)
    pii_count_by_severity: dict[str, int] = Field(default_factory=dict)
    visibility_conflict: bool = False
    visibility_conflict_type: Optional[str] = None
    approval_decision: Optional[str] = Field(default=None, description="approve / reject / return / expire")
    auto_approved: bool = False
    manual_override: bool = False
    return_target_stage: Optional[str] = None
    return_reason_code: Optional[str] = None
    approver_changed_tags: Optional[bool] = None
    approved_after_review_failure: bool = False
    created_at: Optional[datetime] = None


class LLMCostDaily(BaseModel):
    """Daily aggregated LLM cost and stability metrics.

    Generated from llm_call_log; can be backfilled offline.
    """

    date: str = Field(description="ISO date string, e.g. 2026-05-21")
    provider: str
    model_name: str
    model_version: str
    prompt_version: str
    collection_id: str
    visibility: str = Field(description="INTERNAL / EXTERNAL")
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: Optional[float] = None
    avg_latency_ms: Optional[int] = None
    p95_latency_ms: Optional[int] = None


# ── Publishing & Indexing Contracts ─────────────────────────────────────


class PublishedDocument(BaseModel):
    """A published document record. Owner: publishing domain."""

    published_document_id: str
    final_doc_id: str = Field(description="Stable final document identity")
    logical_document_id: str
    tenant_id: str
    collection_id: str
    version: int = Field(default=1, ge=1)
    source_content_hash: str = Field(default="", description="For duplicate-upload lookup")
    canonical_hash: str = Field(default="", description="Hash of canonical content")
    state: PublishedDocumentState = PublishedDocumentState.PUBLISHED
    active_index_version: str = Field(default="", description="Currently active index version")
    previous_state: Optional[str] = None
    supersedes_final_doc_id: Optional[str] = None
    created_by_ticket_id: Optional[str] = None
    asset_paths: dict[str, str] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PublishedDocumentLifecycleAudit(BaseModel):
    """Audit log for published document state changes. Owner: publishing domain."""

    audit_id: str
    published_document_id: str
    final_doc_id: str
    actor_id: str = Field(description="User id or system component")
    action: str = Field(description="publish / archive / deprecate / retract / reindex / restore")
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    reason: Optional[str] = None
    payload_hash: str = ""
    created_at: Optional[datetime] = None


class PublishJob(BaseModel):
    """A publish job record. Owner: publishing-worker."""

    publish_id: str
    intake_job_id: str
    final_doc_id: str
    collection_id: str
    state: PublishJobState = PublishJobState.CREATED
    stage: str = Field(default="", description="Current stage within publish workflow")
    asset_paths: dict[str, str] = Field(default_factory=dict)
    index_build_job_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ReindexJob(BaseModel):
    """A reindex job record. Owner: publishing-worker."""

    reindex_job_id: str
    final_doc_id: str
    collection_id: str
    source_index_version: str
    target_index_version: str
    state: ReindexJobState = ReindexJobState.CREATED
    index_build_job_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class IndexBuildJob(BaseModel):
    """An index build job record. Owner: indexing-service."""

    index_build_job_id: str
    collection_id: str
    target_index_version: str
    publish_id: Optional[str] = None
    reindex_job_id: Optional[str] = None
    state: IndexBuildJobState = IndexBuildJobState.CREATED
    chunk_count: int = Field(default=0, ge=0)
    embedding_count: int = Field(default=0, ge=0)
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class IndexedDocument(BaseModel):
    """Per-document index record. Owner: indexing-service."""

    indexed_document_id: str
    final_doc_id: str
    collection_id: str
    index_version: str
    parser_id: str = ""
    source_suffix: str = ""
    chunk_count: int = Field(default=0, ge=0)
    embedding_count: int = Field(default=0, ge=0)
    visible_chunk_count: int = Field(default=0, ge=0)
    hidden_chunk_count: int = Field(default=0, ge=0)
    has_toc_chunk: bool = False
    has_parent_chunk: bool = False
    document_metadata: dict[str, Any] = Field(default_factory=dict)
    outline: list[dict[str, Any]] = Field(default_factory=list)
    state: IndexedDocumentState = IndexedDocumentState.CANDIDATE
    activated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ParsePreviewRequested(BaseModel):
    """Request for indexing to generate a parse preview and ParseSnapshot."""

    request_id: str
    tenant_id: str
    collection_id: str
    source_file_id: str
    source_binary_ref: str
    filename: str
    mime_type: str
    parser_profile_id: str
    trace_id: str


class ParseSnapshot(BaseModel):
    """Stable parse snapshot owned by indexing."""

    parse_snapshot_id: str
    source_file_id: str
    tenant_id: str
    collection_id: str
    parser_backend: str
    parser_profile_id: str
    input_hash: str
    preview_text_ref: str
    normalized_blocks_ref: str
    outline_ref: str
    chunk_preview_ref: str
    warnings: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class ParseSnapshotReady(BaseModel):
    """Event payload announcing a parse snapshot is ready for review/workbench use."""

    parse_snapshot_id: str
    source_file_id: str
    tenant_id: str
    collection_id: str
    parser_backend: str
    parser_profile_id: str
    preview_text_ref: str
    chunk_preview_ref: str
    warnings: list[str] = Field(default_factory=list)
    trace_id: str
