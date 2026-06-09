"""Core Pydantic models for Reality-RAG V2 contracts.

All cross-service communication MUST use these models.
No service may invent its own field names or shapes for these concepts.
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AdminRole,
    ApiKeyState,
    ApprovalAction,
    ApprovalTicketState,
    BudgetPolicy,
    CollectionLifecycleState,
    ConversionStatus,
    DocumentSupportTier,
    GovernanceSource,
    IndexBuildJobState,
    IndexStatus,
    IndexedDocumentState,
    JobStatus,
    OutputMode,
    ProfileState,
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


class ApiKeyRegistryEntry(BaseModel):
    """Server-side API key registry entry used by access/MCP authentication."""

    api_key_id: str = Field(description="Opaque API key presented by the caller")
    display_name: str = Field(default="", description="Human-readable integration name")
    agent_type_id: str = Field(description="Stable agent/integration type identifier")
    knowledge_scopes: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    debug_permission: bool = False
    max_context_tokens: int = Field(default=4096, gt=0)
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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


class AnchoredFinding(BaseModel):
    finding_id: str = ""
    source_quote: str = ""
    problem_summary: str = ""
    severity: str = "medium"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


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
    anchored_findings: list[AnchoredFinding] = Field(default_factory=list)


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


class RetrievalProfile(BaseModel):
    """DB-backed retrieval execution profile consumed by retrieval-service."""

    profile_id: str
    collection_id: str
    profile_version: int = Field(default=1, ge=1)
    profile_hash: str = ""
    bm25_weight: float = 0.5
    vector_weight: float = 0.5
    candidate_top_k: int = Field(default=20, gt=0)
    similarity_threshold: float = 0.0
    rerank_enabled: bool = True
    rerank_model: str = ""
    fail_policy: str = "fail_closed"
    expansion_policy: dict[str, Any] = Field(default_factory=dict)
    pack_budget: int = Field(default=1200, gt=0)
    enabled: bool = True
    updated_at: Optional[datetime] = None
    updated_by: str = "system"


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
    tenant_id: Optional[str] = None
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


# ── Indexing Contracts ──────────────────────────────────────────────────


class IndexRequestType(StrEnum):
    PUBLISH = "publish"
    REINDEX = "reindex"
    LIFECYCLE_TOMBSTONE = "lifecycle_tombstone"


class IndexBuildRequestedCommand(BaseModel):
    """Canonical command sent to indexing-service to materialize an index.

    This model is the single source of truth for the wire format between
    publishing-worker (or ingestion-worker) and indexing-service.
    """

    model_config = ConfigDict(populate_by_name=True)

    build_request_id: str
    request_type: IndexRequestType
    tenant_id: str
    collection_id: str
    source_file_id: str
    final_doc_id: str = Field(alias="doc_id")
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
    chunk_edit_refs: list[str] = Field(default_factory=list)
    idempotency_key: str
    trace_id: str


# ── Profile Validate Contracts ─────────────────────────────────────────


class ParserProfileValidateRequest(BaseModel):
    """Request to indexing-service to validate and canonicalize a parser profile."""

    parser_profile_id: str
    parser_id: str
    parser_config: dict[str, Any]
    chunk_profile_id: Optional[str] = None
    tenant_id: str
    collection_id: Optional[str] = None
    version: str | int | None = None


class ParserProfileValidateResponse(BaseModel):
    """Response from indexing-service for parser profile validation."""

    valid: bool
    canonical_config: dict[str, Any] | None = None
    profile_hash: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
    runtime_owner: str = "indexing"
    validator_version: str


class RetrievalProfileValidateRequest(BaseModel):
    """Request to retrieval-service to validate and canonicalize a retrieval profile."""

    retrieval_profile_id: str
    profile_config: dict[str, Any]
    tenant_id: str
    collection_id: Optional[str] = None
    version: str | int | None = None


class RetrievalProfileValidateResponse(BaseModel):
    """Response from retrieval-service for retrieval profile validation."""

    valid: bool
    canonical_config: dict[str, Any] | None = None
    profile_hash: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
    runtime_owner: str = "retrieval"
    validator_version: str


# ── Admin API Contracts ────────────────────────────────────────────────


class AdminCollection(BaseModel):
    """Collection as seen by the admin control panel."""

    collection_id: str
    tenant_id: str
    name: str
    description: str = ""
    lifecycle_state: CollectionLifecycleState = CollectionLifecycleState.ACTIVE
    authority_level: int = Field(default=0, ge=0, le=10)
    access_policy: dict[str, Any] = Field(default_factory=dict)
    default_parser_profile_id: str = ""
    default_retrieval_profile_id: str = ""
    default_approval_policy_id: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ParserProfile(BaseModel):
    """Parser profile managed by admin control panel."""

    parser_profile_id: str
    name: str
    description: str = ""
    parser_id: str = "naive"
    parser_config: dict[str, Any] = Field(default_factory=dict)
    runtime_canonical_config: dict[str, Any] | None = None
    profile_hash: str = ""
    validator_version: str = ""
    warnings: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    state: ProfileState = ProfileState.DRAFT
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RetrievalProfileAdmin(BaseModel):
    """Retrieval profile managed by admin control panel (distinct from runtime profile)."""

    retrieval_profile_id: str
    name: str
    description: str = ""
    profile_config: dict[str, Any] = Field(default_factory=dict)
    runtime_canonical_config: dict[str, Any] | None = None
    profile_hash: str = ""
    validator_version: str = ""
    warnings: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    state: ProfileState = ProfileState.DRAFT
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApiKeyRegistryEntryAdmin(BaseModel):
    """API key registry entry managed by admin control panel.

    Uses token_budget_limit as canonical wire field.
    """

    api_key_id: str
    tenant_id: str
    key_hash: str = ""
    display_name: str = ""
    agent_type_id: str = ""
    knowledge_scopes: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    debug_permission: bool = False
    token_budget_limit: int = Field(default=4096, gt=0)
    state: ApiKeyState = ApiKeyState.ACTIVE
    expires_at: Optional[datetime] = None
    created_by: str = ""
    created_at: Optional[datetime] = None
    updated_by: str = ""
    updated_at: Optional[datetime] = None
    last_rotated_at: Optional[datetime] = None


class ApiKeyProjection(BaseModel):
    """Access runtime projection of an API key.

    Derived from admin control plane. Uses canonical wire fields.
    Does NOT include key_hash — access runtime never stores plaintext keys.
    """

    api_key_id: str
    tenant_id: str
    agent_type_id: str = ""
    knowledge_scopes: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    debug_permission: bool = False
    token_budget_limit: int = Field(default=4096, gt=0)
    state: ApiKeyState = ApiKeyState.ACTIVE
    expires_at: Optional[datetime] = None
    projection_version: int = Field(default=1, ge=1)
    last_updated_at: Optional[datetime] = None


class ApiKeyProjectionSync(BaseModel):
    """Command envelope for syncing an API key projection to access runtime.

    All mutation commands MUST carry stable idempotency_key.
    """

    command_id: str
    trace_id: str
    idempotency_key: str
    actor: str
    tenant_id: str
    target_type: str = Field(default="api_key_projection")
    target_id: str
    payload: ApiKeyProjection


class IndexProjectionPayload(BaseModel):
    """Payload for syncing an index projection to retrieval runtime."""

    collection_id: str
    index_version_id: str
    sync_mode: str = Field(description="full_replace | lifecycle_patch")
    doc_id: Optional[str] = Field(default=None, description="Required for lifecycle_patch")
    lifecycle_state: Optional[str] = Field(default=None, description="Required for lifecycle_patch")
    available_int: Optional[int] = Field(default=None, description="Optional override for lifecycle_patch")
    chunks: list[dict[str, Any]] = Field(default_factory=list, description="Required for full_replace")
    tenant_id: Optional[str] = Field(default=None, description="Tenant for index_versions/published_documents upsert")
    opensearch_index: Optional[str] = Field(default=None, description="OpenSearch index for index_versions upsert")
    qdrant_collection: Optional[str] = Field(default=None, description="Qdrant collection for index_versions upsert")
    embedding_model: Optional[str] = Field(default=None, description="Embedding model for index_versions upsert")
    chunk_profile_id: Optional[str] = Field(default=None, description="Chunk profile for index_versions upsert")
    index_profile_id: Optional[str] = Field(default=None, description="Index profile for index_versions upsert")
    schema_version: Optional[str] = Field(default="v1", description="Schema version for index_versions upsert")
    published_document_state: Optional[str] = Field(default="PUBLISHED", description="Published document state for published_documents upsert")


class IndexProjectionSync(BaseModel):
    """Command envelope for syncing an index projection to retrieval runtime.

    All mutation commands MUST carry stable idempotency_key.
    """

    command_id: str
    trace_id: str
    idempotency_key: str
    actor: str
    tenant_id: str
    target_type: str = Field(default="index_projection")
    target_id: str
    payload: IndexProjectionPayload


class RetrievalProfileProjection(BaseModel):
    """Runtime projection of a retrieval profile for retrieval-service DB."""

    profile_id: str
    collection_id: str
    profile_version: int = Field(default=1, ge=1)
    profile_hash: str = ""
    bm25_weight: float = 0.5
    vector_weight: float = 0.5
    candidate_top_k: int = Field(default=20, gt=0)
    similarity_threshold: float = 0.0
    rerank_enabled: bool = True
    rerank_model: str = ""
    fail_policy: str = "fail_closed"
    expansion_policy: dict[str, Any] = Field(default_factory=dict)
    pack_budget: int = Field(default=1200, gt=0)
    enabled: bool = True
    updated_at: Optional[datetime] = None
    updated_by: str = "system"


class RetrievalProfileProjectionSync(BaseModel):
    """Command envelope for syncing a retrieval profile projection to retrieval runtime."""

    command_id: str
    trace_id: str
    idempotency_key: str
    actor: str
    tenant_id: str
    target_type: str = Field(default="retrieval_profile_projection")
    target_id: str
    payload: RetrievalProfileProjection


class CollectionProfileBinding(BaseModel):
    """Versioned collection-to-profile binding managed by admin."""

    binding_id: str
    tenant_id: str
    collection_id: str
    parser_profile_id: str = ""
    retrieval_profile_id: str = ""
    approval_policy_id: str = ""
    effective_from: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    effective_to: Optional[datetime] = None
    binding_version: int = Field(default=1, ge=1)
    config_hash: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommandEnvelope(BaseModel):
    """Stable command envelope for all admin control actions."""

    command_id: str
    trace_id: str
    idempotency_key: str
    actor: str
    tenant_id: str
    collection_id: Optional[str] = None
    target_type: str
    target_id: str
    reason: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class OpsAuditLogEntry(BaseModel):
    """Operations audit log entry for admin actions."""

    audit_id: str
    command_id: str = ""
    trace_id: str = ""
    idempotency_key: str = ""
    actor_id: str
    tenant_id: str = ""
    collection_id: Optional[str] = None
    action: str
    target_type: str
    target_id: str
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    reason: Optional[str] = None
    payload_hash: str = ""
    created_at: Optional[datetime] = None


# ── Workbench Contracts ───────────────────────────────────────────────


class WorkbenchUploadSession(BaseModel):
    """Upload session projection maintained by workbench. Status is derived from owner states."""

    upload_id: str
    user_id: str
    tenant_id: str
    collection_id: str
    source_file_id: Optional[str] = None
    intake_job_id: Optional[str] = None
    parse_snapshot_id: Optional[str] = None
    ticket_id: Optional[str] = None
    selected_parser_profile_id: Optional[str] = None
    parser_override_json: Optional[dict[str, Any]] = None
    access_scope_json: Optional[dict[str, Any]] = None
    status: str = "uploading"
    progress_pct: int = Field(default=0, ge=0, le=100)
    filename: str
    mime_type: str
    size_bytes: int = Field(default=0, ge=0)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkbenchUserPreference(BaseModel):
    """User preference stored locally by workbench."""

    preference_id: str
    user_id: str
    preference_type: str = Field(default="default_collection", description="default_parser_profile | default_collection | view_mode")
    preference_value: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkbenchChunkEdit(BaseModel):
    """Chunk edit intent recorded by workbench. Uses canonical wire fields."""

    chunk_edit_id: str
    tenant_id: str
    collection_id: str
    source_file_id: str
    parse_snapshot_id: Optional[str] = None
    base_evidence_id: str
    edit_scope: str = Field(default="pre_publish", description="pre_publish | post_publish")
    operation: str = Field(default="update", description="update | split | merge | delete | create | hide")
    content: Optional[str] = None
    vector_text: Optional[str] = None
    section_path: Optional[list[str]] = None
    metadata_patch: Optional[dict[str, Any]] = None
    citation_payload: Optional[dict[str, Any]] = None
    source_block_ids: Optional[list[str]] = None
    edit_reason: Optional[str] = None
    edited_by: str
    status: str = Field(default="draft", description="draft | submitted | materialized | active | rejected | failed")
    downstream_revision_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkbenchTaskView(BaseModel):
    """Aggregated task view derived from multiple downstream owner states."""

    upload_id: str
    status: str = "uploading"
    progress_pct: int = Field(default=0, ge=0, le=100)
    source_file_state: Optional[str] = None
    intake_job_state: Optional[str] = None
    parse_snapshot_state: Optional[str] = None
    ticket_state: Optional[str] = None
    published_document_state: Optional[str] = None
    index_build_state: Optional[str] = None
    active_index_version: Optional[str] = None
    filename: str
    collection_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkbenchDocumentLifecycleActionRequest(BaseModel):
    """Workbench-facing lifecycle action request for a single document."""

    reason: str = ""
    index_profile_id: Optional[str] = None


class WorkbenchDocumentLifecycleActionResult(BaseModel):
    """Result of a single lifecycle action proxied through workbench."""

    success: bool = True
    final_doc_id: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    job_id: Optional[str] = None


class WorkbenchBatchDocumentActionRequest(BaseModel):
    """Batch lifecycle action request over document projections."""

    doc_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    index_profile_id: Optional[str] = None


class WorkbenchBatchDocumentActionItemResult(BaseModel):
    """Per-document result for batch lifecycle actions."""

    doc_id: str
    success: bool
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    job_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class WorkbenchBatchDocumentActionResult(BaseModel):
    """Aggregate result for a batch lifecycle action."""

    total: int = Field(default=0, ge=0)
    succeeded: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    items: list[WorkbenchBatchDocumentActionItemResult] = Field(default_factory=list)


class WorkbenchParsePreviewRequest(BaseModel):
    """Request to trigger a parse preview via indexing."""

    upload_id: str
    source_file_id: str
    collection_id: str
    tenant_id: str
    parser_profile_id: str
    parser_override_json: Optional[dict[str, Any]] = None
    actor: str


class WorkbenchTicketDecision(BaseModel):
    """Request to decide an approval ticket."""

    decision_request_id: str
    action: str = Field(description="APPROVE | REJECT | RETURN")
    reason: Optional[str] = None
    actor: str
    tenant_id: str
    collection_id: str


class AgentReviewFindingView(BaseModel):
    """Workbench-facing finding view enriched with optional evidence backfill."""

    finding_id: str
    severity: str = Field(default="medium", description="critical | high | medium | low | info")
    category: str = ""
    problem_summary: str
    source_quote: Optional[str] = None
    evidence_id: Optional[str] = None
    doc_id: Optional[str] = None
    source_file_id: Optional[str] = None
    parse_snapshot_id: Optional[str] = None
    page_from: Optional[int] = None
    page_to: Optional[int] = None
    state: str = Field(default="open", description="open | resolved")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AgentReviewView(BaseModel):
    """Read-only view of AgentReview findings for approval/workbench display."""

    ticket_id: str
    review_run_id: Optional[str] = None
    source_file_id: Optional[str] = None
    parse_snapshot_id: Optional[str] = None
    decision: str = Field(default="REVIEW", description="APPROVE | REJECT | QUARANTINE | REVIEW | REQUEST_CHANGES | DEGRADED")
    findings: list[AgentReviewFindingView] = Field(default_factory=list)
    matched_count: int = Field(default=0, ge=0)
    unmatched_count: int = Field(default=0, ge=0)
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    version: Optional[str] = None
    prompt_hash: Optional[str] = None
    artifact_schema_version: Optional[str] = None
    degraded_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChunkRevisionRequest(BaseModel):
    """Command envelope for chunk revision. Must include stable idempotency_key."""

    command_id: str
    trace_id: str
    idempotency_key: str
    actor: str
    tenant_id: str
    collection_id: str
    target_type: str = Field(description="chunk | parse_snapshot")
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ChunkRevisionView(BaseModel):
    """Read-only view of a chunk revision. Owner: indexing service."""

    revision_id: str
    base_evidence_id: str
    doc_id: str
    collection_id: str
    tenant_id: str
    operation: str = Field(default="update", description="update | split | merge | delete | create | hide")
    content: Optional[str] = None
    vector_text: Optional[str] = None
    section_path: Optional[list[str]] = None
    metadata_patch: Optional[dict[str, Any]] = None
    citation_payload: Optional[dict[str, Any]] = None
    status: str = Field(default="draft", description="draft | materializing | active | failed | superseded")
    superseded_evidence_id: Optional[str] = None
    superseded_by: Optional[str] = None
    idempotency_key: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChunkRevisionMaterializeRequest(BaseModel):
    """Command envelope to materialize a chunk revision."""

    command_id: str
    trace_id: str
    idempotency_key: str
    actor: str
    tenant_id: str
    collection_id: str
    target_type: str = Field(default="chunk_revision")
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RetrievalCachePurgeRequest(BaseModel):
    """Request to purge retrieval cache by scope."""

    scope: "RetrievalCachePurgeScope"


class RetrievalCachePurgeScope(BaseModel):
    """Scope for cache purge. At least tenant_id is required."""

    tenant_id: str
    collection_id: Optional[str] = None
    doc_id: Optional[str] = None
    evidence_id: Optional[str] = None


class RetrievalCachePurgeResponse(BaseModel):
    """Result of cache purge operation."""

    purged_count: int = 0
    scope: dict[str, Any] = Field(default_factory=dict)
