"""SQLAlchemy ORM models for Reality-RAG V2.

These map the contracts Pydantic models to PostgreSQL tables.
Nested or list-typed fields use JSON columns.

PostgreSQL vs Object Storage Boundary (B35):
  PostgreSQL stores: governance index, lifecycle state, status, paths, summaries.
  Object storage / sidecar stores: canonical.md, quality_report.json,
    agent_review.json, processing_record.json — full bodies.
  JSON columns (e.g. conversion_report) store transitional summaries only;
    full report bodies migrate to sidecar with *_asset_path references.

Batch 3.5 Persistence Shape Review (D35):

  Retained in PostgreSQL (permanent governance & lifecycle columns):
    - documents: doc_id, logical_document_id, tenant_id, collection_id,
      source_hash, version, publish_status, index_status, effective_date,
      authority_level, governance_level, access_policy, domain_tags,
      risk_tags, quality_summary (≤2KB), processing_summary (≤2KB),
      asset_paths (JSON path map), created_at, updated_at
    - ingestion_jobs: job_id, job_type, status, collection_id,
      source_files (JSON array), error_message, created_at, updated_at
    - jobs: job_id, job_type, status, collection_id, doc_id,
      error_message, created_at, updated_at
    - collections, tenants, application_profiles, index_registry: all columns

  Slated for migration to object storage / sidecar (future batch):
    - documents.asset_paths points to sidecar — no full bodies stored
    - ingestion_jobs.conversion_report (JSON) → sidecar
    - ingestion_jobs.report_asset_path → already present as pointer

  Transitional JSON columns (allowed during transition, bounded):
    - ingestion_jobs.conversion_report: JSON summary of ConversionReport.
      During transition the full report (including per-file canonical_md inside
      details[*]) may exist here.  Once sidecar write path is built, the column
      is reduced to a stub summary (< 2KB) and report_asset_path becomes the
      canonical source for the full report.
    - documents.asset_paths: JSON path map already points to sidecar.
      No full content is embedded.

  Confirmed non-violations:
    - No canonical.md body stored in PostgreSQL.
    - No quality_report.json / agent_review.json full JSON in PostgreSQL.
    - Repositories preserve sidecar-only columns (processing_summary,
      asset_paths, report_asset_path) across save() calls.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON, Float, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Tenant ──────────────────────────────────────────────────────────────

class TenantModel(Base):
    __tablename__ = "tenants"

    tenant_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)


# ── Collection ──────────────────────────────────────────────────────────

class CollectionModel(Base):
    __tablename__ = "collections"

    collection_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), default="")
    lifecycle_state = Column(String(32), default="active", nullable=False)
    authority_level = Column(Integer, default=0)
    access_policy = Column(JSON, default=dict)
    default_parser_profile_id = Column(String(64), nullable=False, default="")
    default_retrieval_profile_id = Column(String(64), nullable=False, default="")
    default_approval_policy_id = Column(String(64), nullable=False, default="")
    created_by = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_by = Column(String(128), nullable=False, default="")
    updated_at = Column(DateTime(timezone=True), default=_utcnow)


# ── Admin Users ─────────────────────────────────────────────────────────

class AdminUserModel(Base):
    __tablename__ = "admin_users"

    user_id = Column(String(128), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False, default="")
    roles = Column(JSON, default=list)
    clearance_level = Column(Integer, default=0)
    allowed_tenants = Column(JSON, default=list)
    allowed_collections = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)


class AdminSessionModel(Base):
    __tablename__ = "admin_sessions"

    session_id = Column(String(128), primary_key=True)
    user_id = Column(String(128), ForeignKey("admin_users.user_id"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(64), nullable=False, default="")
    user_agent = Column(String(512), nullable=False, default="")


# ── Collection Profile Bindings ─────────────────────────────────────────

class CollectionProfileBindingModel(Base):
    __tablename__ = "collection_profile_bindings"

    binding_id = Column(String(128), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id"), nullable=False)
    collection_id = Column(String(64), ForeignKey("collections.collection_id"), nullable=False)
    parser_profile_id = Column(String(128), nullable=False, default="")
    retrieval_profile_id = Column(String(128), nullable=False, default="")
    approval_policy_id = Column(String(128), nullable=False, default="")
    effective_from = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    binding_version = Column(Integer, nullable=False, default=1)
    config_hash = Column(String(128), nullable=False, default="")
    created_by = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_bindings_collection_version", "collection_id", "binding_version"),
    )


# ── Parser Profiles ─────────────────────────────────────────────────────

class ParserProfileModel(Base):
    __tablename__ = "parser_profiles"

    parser_profile_id = Column(String(128), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=False, default="")
    parser_id = Column(String(64), nullable=False, default="naive")
    parser_config = Column(JSON, default=dict)
    runtime_canonical_config = Column(JSON, nullable=True)
    profile_hash = Column(String(128), nullable=False, default="")
    validator_version = Column(String(64), nullable=False, default="")
    warnings = Column(JSON, default=list)
    version = Column(Integer, nullable=False, default=1)
    state = Column(String(32), nullable=False, default="draft")
    created_by = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_by = Column(String(128), nullable=False, default="")
    updated_at = Column(DateTime(timezone=True), default=_utcnow)


# ── Retrieval Profiles (Admin View) ─────────────────────────────────────

class RetrievalProfileAdminModel(Base):
    __tablename__ = "retrieval_profiles_admin"

    retrieval_profile_id = Column(String(128), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=False, default="")
    profile_config = Column(JSON, default=dict)
    runtime_canonical_config = Column(JSON, nullable=True)
    profile_hash = Column(String(128), nullable=False, default="")
    validator_version = Column(String(64), nullable=False, default="")
    warnings = Column(JSON, default=list)
    version = Column(Integer, nullable=False, default=1)
    state = Column(String(32), nullable=False, default="draft")
    created_by = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_by = Column(String(128), nullable=False, default="")
    updated_at = Column(DateTime(timezone=True), default=_utcnow)


# ── Document (CanonicalMetadata) ────────────────────────────────────────

class DocumentModel(Base):
    """PostgreSQL boundary: documents stores governance index, lifecycle state,
    quality/processing summaries, and sidecar asset_paths.
    Full content (canonical.md, quality_report.json, agent_review.json,
    processing_record.json) lives in object storage / sidecar.
    """

    __tablename__ = "documents"

    doc_id = Column(String(128), primary_key=True)
    logical_document_id = Column(String(128), nullable=False)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id"), nullable=False)
    collection_id = Column(String(64), ForeignKey("collections.collection_id"), nullable=False)
    source_hash = Column(String(128), nullable=False)
    source_content_hash = Column(String(128), nullable=False, default="")
    version = Column(Integer, default=1)
    archived = Column(Boolean, default=False, nullable=False)
    publish_status = Column(String(32), default="draft")
    index_status = Column(String(32), default="not_indexed")
    effective_date = Column(DateTime(timezone=True), nullable=True)
    authority_level = Column(Integer, default=0)
    governance_level = Column(String(32), default="standard")
    access_policy = Column(String(64), default="collection_default")
    domain_tags = Column(JSON, default=list)
    risk_tags = Column(JSON, default=list)
    quality_summary = Column(String(2048), default="")
    processing_summary = Column(String(2048), default="")
    asset_paths = Column(
        JSON,
        default=dict,
        doc="Sidecar path map: e.g. {'canonical_md': 's3://...', 'quality_report': 's3://...'}",
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_documents_collection_archived", "collection_id", "archived"),
    )


# ── Job ─────────────────────────────────────────────────────────────────

class JobModel(Base):
    """PostgreSQL boundary: jobs stores lifecycle state, status, and error messages.
    Full processing records live in object storage / sidecar.
    """

    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True)
    job_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    collection_id = Column(String(64), nullable=True)
    doc_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    error_message = Column(String(2048), nullable=True)


# ── Application Profile ─────────────────────────────────────────────────

class ApplicationProfileModel(Base):
    __tablename__ = "application_profiles"

    application_profile_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String(255), nullable=False)
    allowed_collections = Column(JSON, default=list)
    default_collections = Column(JSON, default=list)
    allow_cross_collection = Column(Boolean, default=False)
    default_token_budget = Column(Integer, default=4096)
    default_budget_policy = Column(String(32), default="balanced")
    metadata_policy = Column(String(32), default="minimal")
    debug_permission = Column(Boolean, default=False)
    rate_limit = Column(Integer, default=100)


class RetrievalProfileModel(Base):
    __tablename__ = "retrieval_profiles"

    profile_id = Column(String(64), primary_key=True)
    collection_id = Column(String(64), primary_key=True)
    profile_version = Column(Integer, default=1, nullable=False)
    profile_hash = Column(String(128), nullable=False, default="")
    bm25_weight = Column(Float, default=0.5, nullable=False)
    vector_weight = Column(Float, default=0.5, nullable=False)
    candidate_top_k = Column(Integer, default=20, nullable=False)
    similarity_threshold = Column(Float, default=0.0, nullable=False)
    rerank_enabled = Column(Boolean, default=True, nullable=False)
    rerank_model = Column(String(128), nullable=False, default="")
    fail_policy = Column(String(32), nullable=False, default="fail_closed")
    expansion_policy = Column(JSON, default=dict)
    pack_budget = Column(Integer, default=1200, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_by = Column(String(128), nullable=False, default="system")

    __table_args__ = (
        Index("ix_retrieval_profiles_enabled", "enabled"),
        Index("ix_retrieval_profiles_collection", "collection_id"),
    )


# ── Principal Profile ──────────────────────────────────────────────────

class ApiKeyRegistryModel(Base):
    __tablename__ = "api_key_registry"

    api_key_id = Column(String(128), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, default="")
    display_name = Column(String(255), nullable=False, default="")
    agent_type_id = Column(String(128), nullable=False, default="")
    key_hash = Column(String(255), nullable=False, default="")
    knowledge_scopes = Column(JSON, default=list)
    roles = Column(JSON, default=list)
    debug_permission = Column(Boolean, default=False, nullable=False)
    max_context_tokens = Column(Integer, default=4096, nullable=False)
    token_budget_limit = Column(Integer, default=4096, nullable=False)
    state = Column(String(32), nullable=False, default="active")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_by = Column(String(128), nullable=False, default="")
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    last_rotated_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_api_key_registry_state", "state"),
        Index("ix_api_key_registry_tenant", "tenant_id"),
    )


class PrincipalProfileModel(Base):
    __tablename__ = "principal_profiles"

    user_id = Column(String(128), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id"), nullable=False)
    role_ids = Column(JSON, default=list)
    group_ids = Column(JSON, default=list)
    department_ids = Column(JSON, default=list)
    clearance_level = Column(Integer, default=0)
    attributes = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)


# ── Document Policy ────────────────────────────────────────────────────

class DocumentPolicyModel(Base):
    __tablename__ = "document_policies"

    __table_args__ = (
        UniqueConstraint("doc_id", "collection_id", name="uix_doc_policy"),
    )

    policy_id = Column(String(128), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id"), nullable=False)
    collection_id = Column(String(64), ForeignKey("collections.collection_id"), nullable=False)
    doc_id = Column(String(128), ForeignKey("documents.doc_id"), nullable=False)
    effect = Column(String(16), nullable=False)
    subjects = Column(JSON, default=list)
    conditions = Column(JSON, default=list)
    priority = Column(Integer, default=100)
    policy_version = Column(String(64), default="v1")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)


# ── Upload Session ──────────────────────────────────────────────────────

class UploadSessionModel(Base):
    """Upload session record. Owner: document-service."""

    __tablename__ = "upload_sessions"

    upload_id = Column(String(64), primary_key=True)
    source = Column(String(32), nullable=False, default="web")
    user_id = Column(String(128), nullable=True)
    trace_id = Column(String(64), nullable=False, default="")
    status = Column(String(32), nullable=False, default="active")
    expected_size = Column(Integer, nullable=True)
    expected_sha256 = Column(String(128), nullable=True)
    received_size = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    last_chunk_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


# ── Object Blob ─────────────────────────────────────────────────────────

class ObjectBlobModel(Base):
    """Physical object blob record. Owner: document-service."""

    __tablename__ = "object_blobs"

    object_id = Column(String(128), primary_key=True)
    content_hash = Column(String(128), nullable=False, unique=True)
    storage_key = Column(String(1024), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    ref_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


# ── Malware Scan Results ────────────────────────────────────────────────

class MalwareScanResultModel(Base):
    """Malware scan result record. Owner: document-service."""

    __tablename__ = "malware_scan_results"

    scan_result_id = Column(String(64), primary_key=True)
    source_file_id = Column(String(64), ForeignKey("source_files.source_file_id"), nullable=False)
    engine = Column(String(64), nullable=False)
    engine_version = Column(String(64), nullable=False)
    verdict = Column(String(32), nullable=False, default="clean")
    signature = Column(String(256), nullable=True)
    scanned_at = Column(DateTime(timezone=True), default=_utcnow)
    raw_result_ref = Column(String(1024), nullable=True)


# ── Source File ─────────────────────────────────────────────────────────

class SourceFileModel(Base):
    """Source file lifecycle record per collection. Owner: document-service."""

    __tablename__ = "source_files"

    source_file_id = Column(String(64), primary_key=True)
    upload_id = Column(String(64), ForeignKey("upload_sessions.upload_id"), nullable=True)
    object_id = Column(String(128), ForeignKey("object_blobs.object_id"), nullable=False)
    collection_id = Column(String(64), ForeignKey("collections.collection_id"), nullable=False)
    visibility = Column(String(32), nullable=False, default="INTERNAL")
    original_name = Column(String(512), nullable=False, default="")
    sanitized_name = Column(String(512), nullable=False, default="")
    content_hash = Column(String(128), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    state = Column(String(32), nullable=False, default="ready")
    claimed_by_job_id = Column(String(64), nullable=True, unique=True)
    scan_result_id = Column(String(64), ForeignKey("malware_scan_results.scan_result_id", use_alter=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_source_files_content_hash_collection", "content_hash", "collection_id"),
        Index("ix_source_files_object_id", "object_id"),
        Index("ix_source_files_upload_id", "upload_id"),
        Index("ix_source_files_collection_state", "collection_id", "state"),
        # Partial unique: only one active source file per (content_hash, collection_id)
        Index(
            "ix_source_files_active_unique",
            "content_hash",
            "collection_id",
            unique=True,
            postgresql_where=Column("state").in_(
                ["uploading", "uploaded", "scanning", "ready", "claimed", "consumed"]
            ),
        ),
    )


# ── Ingestion Job ───────────────────────────────────────────────────────

class IngestionJobModel(Base):
    """PostgreSQL boundary: ingestion_jobs stores lifecycle state, source file list,
    conversion_report JSON summary (transitional — full reports migrating to sidecar),
    and report_asset_path pointing to the full report in object storage.
    """

    __tablename__ = "ingestion_jobs"

    job_id = Column(String(64), primary_key=True)
    job_type = Column(String(32), default="ingestion")
    status = Column(String(32), nullable=False, default="pending")
    collection_id = Column(String(64), nullable=False)
    source_files = Column(JSON, default=list)
    source_file_ids = Column(JSON, default=list)
    # Transitional: stores JSON summary of ConversionReport.
    # Full report body (including canonical_md in details[*]) will migrate to
    # sidecar; report_asset_path points to the canonical location.
    conversion_report = Column(JSON, nullable=True)
    report_asset_path = Column(
        String(1024),
        nullable=True,
        default=None,
        doc="Path to full ConversionReport in object storage / sidecar",
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    error_message = Column(String(2048), nullable=True)


# ── Index Registry ──────────────────────────────────────────────────────

class IndexRegistryModel(Base):
    """PostgreSQL boundary: index_registry stores index version and status metadata.
    Actual vector index data lives in the vector store (e.g. ChromaDB/Milvus).
    """

    __tablename__ = "index_registry"

    collection_id = Column(String(64), primary_key=True)
    index_version = Column(String(64), nullable=False)
    previous_index_version = Column(String(64), nullable=True)
    target_index_version = Column(String(64), nullable=True)
    status = Column(String(32), default="indexed")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)


# ── Orchestrator Tables ─────────────────────────────────────────────────

class IntakeJobModel(Base):
    """Persistent intake job record. Owner: intake-orchestrator."""

    __tablename__ = "intake_jobs"

    intake_job_id = Column(String(64), primary_key=True)
    source_file_id = Column(String(64), nullable=False, unique=True)
    object_id = Column(String(128), nullable=False)
    collection_id = Column(String(64), nullable=False)
    state = Column(String(32), nullable=False, default="created")
    state_version = Column(Integer, default=1, nullable=False)
    current_stage = Column(String(32), nullable=True)
    preliminary_doc_id = Column(String(128), nullable=True)
    review_id = Column(String(64), nullable=True)
    ticket_id = Column(String(64), nullable=True)
    final_doc_id = Column(String(128), nullable=True)
    publish_id = Column(String(64), nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    trace_id = Column(String(64), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String(2048), nullable=True)


class StageTaskModel(Base):
    """Persistent stage task record. Owner: intake-orchestrator."""

    __tablename__ = "stage_tasks"

    stage_task_id = Column(String(64), primary_key=True)
    intake_job_id = Column(String(64), ForeignKey("intake_jobs.intake_job_id"), nullable=False)
    stage_name = Column(String(32), nullable=False)
    idempotency_key = Column(String(256), nullable=False, unique=True)
    schema_version = Column(String(32), nullable=False, default="v1")
    input_hash = Column(String(128), nullable=False)
    state = Column(String(32), nullable=False, default="queued")
    locked_by = Column(String(64), nullable=True)
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    rerun_round = Column(Integer, default=0, nullable=False)
    rerun_reason_code = Column(String(64), nullable=True)
    next_run_at = Column(DateTime(timezone=True), default=_utcnow)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_stage_tasks_intake_job_id", "intake_job_id"),
    )


class StageAttemptModel(Base):
    """Persistent stage attempt record. Owner: intake-orchestrator."""

    __tablename__ = "stage_attempts"

    stage_attempt_id = Column(String(64), primary_key=True)
    stage_task_id = Column(String(64), ForeignKey("stage_tasks.stage_task_id"), nullable=False)
    intake_job_id = Column(String(64), ForeignKey("intake_jobs.intake_job_id"), nullable=False)
    stage_name = Column(String(32), nullable=False)
    attempt_no = Column(Integer, nullable=False)
    worker_id = Column(String(64), nullable=True)
    state = Column(String(32), nullable=False, default="running")
    error_code = Column(String(64), nullable=True)
    error_summary_hash = Column(String(128), nullable=True)
    started_at = Column(DateTime(timezone=True), default=_utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("stage_task_id", "attempt_no", name="uix_stage_attempt_task_no"),
    )


class StageResultModel(Base):
    """Persistent stage result record (success only). Owner: intake-orchestrator."""

    __tablename__ = "stage_results"

    stage_result_id = Column(String(64), primary_key=True)
    stage_task_id = Column(String(64), ForeignKey("stage_tasks.stage_task_id"), nullable=False, unique=True)
    stage_attempt_id = Column(String(64), ForeignKey("stage_attempts.stage_attempt_id"), nullable=False)
    intake_job_id = Column(String(64), ForeignKey("intake_jobs.intake_job_id"), nullable=False)
    stage_name = Column(String(32), nullable=False)
    idempotency_key = Column(String(256), nullable=False)
    result_hash = Column(String(128), nullable=False)
    result_ref = Column(String(1024), nullable=True)
    summary_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ── Approval Tables ─────────────────────────────────────────────────────

class ApprovalTicketModel(Base):
    """Approval ticket record. Owner: approval-service."""

    __tablename__ = "approval_tickets"

    ticket_id = Column(String(64), primary_key=True)
    intake_job_id = Column(String(64), nullable=False)
    tenant_id = Column(String(64), nullable=True)
    approval_round = Column(Integer, nullable=False, default=1)
    preliminary_doc_id = Column(String(128), nullable=False)
    collection_id = Column(String(64), nullable=False)
    state = Column(String(32), nullable=False, default="pending")
    routing_recommendation = Column(String(32), nullable=False, default="auto_approve")
    decision = Column(String(32), nullable=True)
    decision_actor = Column(String(128), nullable=True)
    decision_reason = Column(String(2048), nullable=True)
    final_doc_id = Column(String(128), nullable=True)
    confirmed_tags = Column(JSON, nullable=True, default=list)
    return_target_stage = Column(String(32), nullable=True)
    return_reason = Column(String(2048), nullable=True)
    version_decision = Column(String(32), nullable=True)
    supersedes_final_doc_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("intake_job_id", "approval_round", name="uix_approval_ticket_job_round"),
    )


class ApprovalAuditLogModel(Base):
    """Approval audit log — append only. Owner: approval-service."""

    __tablename__ = "approval_audit_log"

    audit_id = Column(String(64), primary_key=True)
    ticket_id = Column(String(64), ForeignKey("approval_tickets.ticket_id"), nullable=False)
    intake_job_id = Column(String(64), nullable=False)
    actor_id = Column(String(128), nullable=False)
    action = Column(String(32), nullable=False)
    before_state = Column(String(32), nullable=True)
    after_state = Column(String(32), nullable=True)
    reason = Column(String(2048), nullable=True)
    payload_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ── Outbox Events ───────────────────────────────────────────────────────

class OutboxEventModel(Base):
    """Outbox event record. Each owner schema has its own outbox table.

    Producer writes outbox_events in the same DB transaction as business state.
    Dispatcher polls pending events and delivers them asynchronously.
    """

    __tablename__ = "outbox_events"

    event_id = Column(String(64), primary_key=True)
    event_type = Column(String(64), nullable=False)
    aggregate_type = Column(String(64), nullable=False)
    aggregate_id = Column(String(128), nullable=False)
    schema_version = Column(String(32), nullable=False, default="2026-05-21.v1")
    payload_json = Column(JSON, nullable=False, default=dict)
    payload_hash = Column(String(128), nullable=False, default="")
    idempotency_key = Column(String(512), nullable=True)
    trace_id = Column(String(64), nullable=False, default="")
    status = Column(String(32), nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_outbox_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )


class ConsumerIdempotencyModel(Base):
    """Consumer-side idempotency record.

    Each consumer records processed (event_id, idempotency_key) pairs
    to guard against duplicate event delivery.
    """

    __tablename__ = "consumer_idempotency"

    record_id = Column(String(64), primary_key=True)
    consumer_id = Column(String(64), nullable=False)
    event_id = Column(String(64), nullable=False)
    idempotency_key = Column(String(512), nullable=True)
    processed_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        # Composite unique for consumer dedup
        Index(
            "ix_consumer_idempotency_pk",
            "consumer_id",
            "event_id",
            unique=True,
        ),
        Index("ix_consumer_idempotency_key", "consumer_id", "idempotency_key"),
    )


# ── Telemetry Tables ────────────────────────────────────────────────────


class TelemetryEventModel(Base):
    """Structured telemetry event. Does NOT store sensitive plaintext."""

    __tablename__ = "telemetry_events"

    event_id = Column(String(64), primary_key=True)
    event_name = Column(String(64), nullable=False)
    event_time = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    schema_version = Column(String(32), nullable=False, default="2026-05-21.v1")
    trace_id = Column(String(64), nullable=False, default="")
    intake_job_id = Column(String(64), nullable=True)
    source_file_id = Column(String(64), nullable=True)
    collection_id = Column(String(64), nullable=True)
    visibility = Column(String(16), nullable=True)
    stage_name = Column(String(32), nullable=True)
    stage_task_id = Column(String(64), nullable=True)
    ticket_id = Column(String(64), nullable=True)
    final_doc_id = Column(String(128), nullable=True)
    component = Column(String(64), nullable=False)
    component_version = Column(String(32), nullable=False, default="0.1.0")
    status = Column(String(32), nullable=False, default="started")
    duration_ms = Column(Integer, nullable=True)
    error_code = Column(String(64), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    attributes_json = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_telemetry_trace_id", "trace_id"),
        Index("ix_telemetry_intake_job", "intake_job_id"),
        Index("ix_telemetry_event_name", "event_name"),
        Index("ix_telemetry_event_time", "event_time"),
    )


class LLMCallLogModel(Base):
    """Per-LLM-call metadata. Stores hashes, NOT prompt/response plaintext."""

    __tablename__ = "llm_call_log"

    llm_call_id = Column(String(64), primary_key=True)
    trace_id = Column(String(64), nullable=False, default="")
    intake_job_id = Column(String(64), nullable=False)
    stage_task_id = Column(String(64), nullable=False)
    review_id = Column(String(64), nullable=True)
    provider = Column(String(64), nullable=False)
    model_name = Column(String(64), nullable=False)
    model_version = Column(String(64), nullable=False)
    prompt_version = Column(String(64), nullable=False)
    policy_version = Column(String(64), nullable=False)
    request_hash = Column(String(128), nullable=False)
    response_hash = Column(String(128), nullable=True)
    input_token_count = Column(Integer, nullable=True)
    output_token_count = Column(Integer, nullable=True)
    total_token_count = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    timeout_ms = Column(Integer, nullable=False, default=60000)
    status = Column(String(32), nullable=False, default="succeeded")
    error_code = Column(String(64), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    json_parse_success = Column(Boolean, nullable=False, default=False)
    schema_validation_success = Column(Boolean, nullable=False, default=False)
    redaction_before_send = Column(Boolean, nullable=False, default=False)
    external_model_used = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_llm_call_trace_id", "trace_id"),
        Index("ix_llm_call_intake_job", "intake_job_id"),
        Index("ix_llm_call_status", "status"),
        Index("ix_llm_call_created", "created_at"),
    )


class ReviewQualityFeedbackModel(Base):
    """Links agent-review output to approval decision for quality analysis."""

    __tablename__ = "review_quality_feedback"

    feedback_id = Column(String(64), primary_key=True)
    review_id = Column(String(64), nullable=False)
    intake_job_id = Column(String(64), nullable=False)
    ticket_id = Column(String(64), nullable=True)
    collection_id = Column(String(64), nullable=False)
    visibility = Column(String(16), nullable=False)
    model_name = Column(String(64), nullable=True)
    model_version = Column(String(64), nullable=True)
    prompt_version = Column(String(64), nullable=True)
    routing_recommendation = Column(String(32), nullable=False, default="auto_approve")
    review_status = Column(String(32), nullable=False, default="succeeded")
    pii_count_by_type = Column(JSON, default=dict)
    pii_count_by_severity = Column(JSON, default=dict)
    visibility_conflict = Column(Boolean, nullable=False, default=False)
    visibility_conflict_type = Column(String(64), nullable=True)
    approval_decision = Column(String(32), nullable=True)
    auto_approved = Column(Boolean, nullable=False, default=False)
    manual_override = Column(Boolean, nullable=False, default=False)
    return_target_stage = Column(String(32), nullable=True)
    return_reason_code = Column(String(64), nullable=True)
    approver_changed_tags = Column(Boolean, nullable=True)
    approved_after_review_failure = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_review_feedback_review_id", "review_id"),
        Index("ix_review_feedback_intake_job", "intake_job_id"),
    )


class LLMCostDailyModel(Base):
    """Daily aggregated LLM cost and stability metrics."""

    __tablename__ = "llm_cost_daily"

    date = Column(String(10), primary_key=True)
    provider = Column(String(64), primary_key=True)
    model_name = Column(String(64), primary_key=True)
    model_version = Column(String(64), primary_key=True)
    prompt_version = Column(String(64), primary_key=True)
    collection_id = Column(String(64), primary_key=True)
    visibility = Column(String(16), primary_key=True)
    call_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost = Column(Float, nullable=True)
    avg_latency_ms = Column(Integer, nullable=True)
    p95_latency_ms = Column(Integer, nullable=True)


# ── Publishing & Indexing Tables ────────────────────────────────────────


class PublishedDocumentModel(Base):
    """Published document record. Owner: publishing domain."""

    __tablename__ = "published_documents"

    published_document_id = Column(String(64), primary_key=True)
    final_doc_id = Column(String(128), nullable=False, unique=True)
    logical_document_id = Column(String(128), nullable=False)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id"), nullable=False)
    collection_id = Column(String(64), ForeignKey("collections.collection_id"), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    source_content_hash = Column(String(128), nullable=False, default="")
    canonical_hash = Column(String(128), nullable=False, default="")
    state = Column(String(32), nullable=False, default="published")
    active_index_version = Column(String(64), nullable=False, default="")
    previous_state = Column(String(32), nullable=True)
    supersedes_final_doc_id = Column(String(128), nullable=True)
    created_by_ticket_id = Column(String(64), nullable=True)
    asset_paths = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_published_docs_collection_id", "collection_id"),
        Index("ix_published_docs_logical_id", "logical_document_id"),
        Index("ix_published_docs_source_hash", "source_content_hash"),
    )


class PublishedDocumentLifecycleAuditModel(Base):
    """Audit log for published document state changes. Owner: publishing domain."""

    __tablename__ = "published_document_lifecycle_audit"

    audit_id = Column(String(64), primary_key=True)
    published_document_id = Column(String(64), ForeignKey("published_documents.published_document_id"), nullable=False)
    final_doc_id = Column(String(128), nullable=False)
    actor_id = Column(String(128), nullable=False)
    action = Column(String(32), nullable=False)
    before_state = Column(String(32), nullable=True)
    after_state = Column(String(32), nullable=True)
    reason = Column(String(2048), nullable=True)
    payload_hash = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_pub_doc_audit_doc_id", "published_document_id"),
    )


class PublishJobModel(Base):
    """Publish job record. Owner: publishing-worker."""

    __tablename__ = "publish_jobs"

    publish_id = Column(String(64), primary_key=True)
    intake_job_id = Column(String(64), ForeignKey("intake_jobs.intake_job_id"), nullable=False)
    final_doc_id = Column(String(128), nullable=False)
    collection_id = Column(String(64), nullable=False)
    state = Column(String(32), nullable=False, default="created")
    stage = Column(String(32), nullable=False, default="")
    asset_paths = Column(JSON, default=dict)
    index_build_job_id = Column(String(64), nullable=True)
    error_message = Column(String(2048), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ReindexJobModel(Base):
    """Reindex job record. Owner: publishing-worker."""

    __tablename__ = "reindex_jobs"

    reindex_job_id = Column(String(64), primary_key=True)
    final_doc_id = Column(String(128), nullable=False)
    collection_id = Column(String(64), nullable=False)
    source_index_version = Column(String(64), nullable=False)
    target_index_version = Column(String(64), nullable=False)
    state = Column(String(32), nullable=False, default="created")
    index_build_job_id = Column(String(64), nullable=True)
    error_message = Column(String(2048), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class IndexBuildJobModel(Base):
    """Index build job record. Owner: indexing-service."""

    __tablename__ = "index_build_jobs"

    index_build_job_id = Column(String(64), primary_key=True)
    collection_id = Column(String(64), nullable=False)
    target_index_version = Column(String(64), nullable=False)
    publish_id = Column(String(64), ForeignKey("publish_jobs.publish_id"), nullable=True)
    reindex_job_id = Column(String(64), ForeignKey("reindex_jobs.reindex_job_id"), nullable=True)
    state = Column(String(32), nullable=False, default="created")
    chunk_count = Column(Integer, default=0, nullable=False)
    embedding_count = Column(Integer, default=0, nullable=False)
    error_message = Column(String(2048), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_index_build_jobs_collection", "collection_id"),
    )


class IndexedDocumentModel(Base):
    """Per-document index record. Owner: indexing-service."""

    __tablename__ = "indexed_documents"

    indexed_document_id = Column(String(256), primary_key=True)
    final_doc_id = Column(String(128), nullable=False)
    collection_id = Column(String(64), nullable=False)
    index_version = Column(String(64), nullable=False)
    parser_id = Column(String(64), nullable=False, default="")
    source_suffix = Column(String(32), nullable=False, default="")
    chunk_count = Column(Integer, default=0, nullable=False)
    embedding_count = Column(Integer, default=0, nullable=False)
    visible_chunk_count = Column(Integer, default=0, nullable=False)
    hidden_chunk_count = Column(Integer, default=0, nullable=False)
    has_toc_chunk = Column(Boolean, default=False, nullable=False)
    has_parent_chunk = Column(Boolean, default=False, nullable=False)
    document_metadata = Column(JSON, default=dict)
    outline = Column(JSON, default=list)
    state = Column(String(32), nullable=False, default="candidate")
    activated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("final_doc_id", "index_version", name="uix_indexed_doc_version"),
        Index("ix_indexed_docs_collection_version", "collection_id", "index_version"),
    )


class IndexVersionModel(Base):
    """Persistent index version lifecycle record. Owner: indexing-service."""

    __tablename__ = "index_versions"

    index_version_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), nullable=False, default="")
    collection_id = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="building")
    schema_version = Column(String(32), nullable=False, default="")
    index_profile_id = Column(String(64), nullable=False, default="")
    chunk_profile_id = Column(String(64), nullable=False, default="")
    embedding_model = Column(String(128), nullable=False, default="")
    opensearch_index = Column(String(128), nullable=False, default="")
    qdrant_collection = Column(String(128), nullable=False, default="")
    chunk_count = Column(Integer, nullable=False, default=0)
    previous_active_index_version_id = Column(String(64), nullable=True)
    replaced_by_index_version_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)
    cleaned_up_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_index_versions_collection", "collection_id"),
        Index("ix_index_versions_status", "status"),
    )


class ParseSnapshotModel(Base):
    """Stable parse snapshot record. Owner: indexing-service."""

    __tablename__ = "parse_snapshots"

    parse_snapshot_id = Column(String(64), primary_key=True)
    request_id = Column(String(64), nullable=False)
    tenant_id = Column(String(64), nullable=False)
    collection_id = Column(String(64), nullable=False)
    source_file_id = Column(String(64), nullable=False)
    source_binary_ref = Column(String(2048), nullable=False, default="")
    source_filename = Column(String(512), nullable=False, default="")
    source_suffix = Column(String(32), nullable=False, default="")
    parser_id = Column(String(64), nullable=False, default="")
    parser_backend = Column(String(64), nullable=False, default="")
    collection_parser_config = Column(JSON, default=dict)
    parser_config = Column(JSON, default=dict)
    input_hash = Column(String(128), nullable=False, default="")
    preview_text = Column(Text, nullable=False, default="")
    upstream_chunks = Column(JSON, default=list)
    outline = Column(JSON, default=list)
    document_metadata = Column(JSON, default=dict)
    chunk_preview = Column(JSON, default=list)
    warnings = Column(JSON, default=list)
    decision_reason = Column(String(512), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_parse_snapshots_source_file", "source_file_id"),
        Index("ix_parse_snapshots_collection", "collection_id"),
    )


class ChunkRegistryModel(Base):
    """Persistent chunk registry row. Owner: indexing-service."""

    __tablename__ = "chunk_registry"

    chunk_id = Column(String(128), primary_key=True)
    tenant_id = Column(String(64), nullable=False)
    collection_id = Column(String(64), nullable=False)
    final_doc_id = Column(String(128), nullable=False)
    index_version_id = Column(String(64), nullable=False)
    available_int = Column(Integer, nullable=False, default=1)
    visibility = Column(String(32), nullable=False, default="internal")
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_chunk_registry_collection_version", "collection_id", "index_version_id"),
        Index("ix_chunk_registry_final_doc_version", "final_doc_id", "index_version_id"),
        Index("ix_chunk_registry_tenant_collection", "tenant_id", "collection_id"),
    )


class RunTraceModel(Base):
    """Persistent root trace record for intake/indexing main-chain truth."""

    __tablename__ = "run_traces"

    run_trace_id = Column(String(128), primary_key=True)
    trace_id = Column(String(64), nullable=False, default="")
    run_kind = Column(String(64), nullable=False, default="")
    tenant_id = Column(String(64), nullable=False, default="")
    collection_id = Column(String(64), nullable=False, default="")
    principal_id = Column(String(128), nullable=False, default="")
    query_id = Column(String(128), nullable=False, default="")
    index_version_id = Column(String(64), nullable=False, default="")
    profile_id = Column(String(64), nullable=False, default="")
    root_status = Column(String(32), nullable=False, default="")
    debug_ref = Column(String(1024), nullable=False, default="")
    result_count = Column(Integer, nullable=False, default=0)
    source_file_id = Column(String(64), nullable=True)
    intake_job_id = Column(String(64), nullable=True)
    final_doc_id = Column(String(128), nullable=True)
    approval_ticket_id = Column(String(64), nullable=True)
    extra_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_run_traces_trace_id", "trace_id"),
        Index("ix_run_traces_source_file", "source_file_id"),
        Index("ix_run_traces_intake_job", "intake_job_id"),
        Index("ix_run_traces_final_doc", "final_doc_id"),
    )


class RunStepModel(Base):
    """Persistent step log for a trace."""

    __tablename__ = "run_steps"

    run_step_id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), nullable=False, default="")
    step_name = Column(String(64), nullable=False, default="")
    status = Column(String(32), nullable=False, default="")
    summary = Column(String(4096), nullable=False, default="")
    details_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_run_steps_trace_id", "trace_id"),
        Index("ix_run_steps_created_at", "created_at"),
    )


class TraceArtifactModel(Base):
    """Persistent artifact log for a trace."""

    __tablename__ = "trace_artifacts"

    trace_artifact_id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), nullable=False, default="")
    artifact_ref = Column(String(2048), nullable=False, default="")
    artifact_kind = Column(String(64), nullable=False, default="")
    summary = Column(String(4096), nullable=False, default="")
    details_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_trace_artifacts_trace_id", "trace_id"),
        Index("ix_trace_artifacts_kind", "artifact_kind"),
        Index("ix_trace_artifacts_created_at", "created_at"),
    )


class OpsAuditLogModel(Base):
    """Operations audit log for admin actions (retry, cancel, replay, reindex, mark-cleanable).

    Append-only. All management operations must write here.
    """

    __tablename__ = "ops_audit_log"

    audit_id = Column(String(64), primary_key=True)
    command_id = Column(String(128), nullable=False, default="")
    trace_id = Column(String(64), nullable=False, default="")
    idempotency_key = Column(String(512), nullable=False, default="")
    actor_id = Column(String(128), nullable=False)
    tenant_id = Column(String(64), nullable=False, default="")
    collection_id = Column(String(64), nullable=True)
    action = Column(String(32), nullable=False)
    target_type = Column(String(32), nullable=False)
    target_id = Column(String(128), nullable=False)
    before_state = Column(String(256), nullable=True)
    after_state = Column(String(256), nullable=True)
    reason = Column(String(2048), nullable=True)
    payload_hash = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_ops_audit_target", "target_type", "target_id"),
        Index("ix_ops_audit_actor", "actor_id"),
        Index("ix_ops_audit_created", "created_at"),
        Index("ix_ops_audit_trace", "trace_id"),
        Index("ix_ops_audit_idempotency", "idempotency_key"),
    )


# ── Workbench Models ────────────────────────────────────────────────────

class WorkbenchUploadSessionModel(Base):
    """Workbench upload session projection. Owner: workbench-api.
    Status is UI aggregate, derived from downstream owner states.
    """

    __tablename__ = "workbench_upload_sessions"

    upload_id = Column(String(64), primary_key=True)
    user_id = Column(String(128), nullable=False)
    tenant_id = Column(String(64), nullable=False)
    collection_id = Column(String(64), nullable=False)
    source_file_id = Column(String(64), nullable=True)
    intake_job_id = Column(String(64), nullable=True)
    parse_snapshot_id = Column(String(64), nullable=True)
    ticket_id = Column(String(64), nullable=True)
    selected_parser_profile_id = Column(String(128), nullable=True)
    parser_override_json = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="uploading")
    progress_pct = Column(Integer, nullable=False, default=0)
    filename = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    error_message = Column(String(2048), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_wb_uploads_user", "user_id"),
        Index("ix_wb_uploads_tenant", "tenant_id"),
        Index("ix_wb_uploads_collection", "collection_id"),
        Index("ix_wb_uploads_status", "status"),
    )


class WorkbenchUserPreferenceModel(Base):
    """Workbench user preference. Owner: workbench-api."""

    __tablename__ = "workbench_user_preferences"

    preference_id = Column(String(64), primary_key=True)
    user_id = Column(String(128), nullable=False)
    preference_type = Column(String(64), nullable=False)
    preference_value = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_wb_prefs_user", "user_id"),
        Index("ix_wb_prefs_type", "user_id", "preference_type"),
    )


class WorkbenchChunkEditModel(Base):
    """Workbench chunk edit intent. Owner: workbench-api.
    Uses canonical wire fields: base_evidence_id, content.
    """

    __tablename__ = "workbench_chunk_edits"

    chunk_edit_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), nullable=False)
    collection_id = Column(String(64), nullable=False)
    source_file_id = Column(String(64), nullable=False)
    parse_snapshot_id = Column(String(64), nullable=True)
    base_evidence_id = Column(String(128), nullable=False)
    edit_scope = Column(String(32), nullable=False, default="pre_publish")
    operation = Column(String(32), nullable=False, default="update")
    content = Column(Text, nullable=True)
    vector_text = Column(Text, nullable=True)
    section_path = Column(JSON, nullable=True)
    metadata_patch = Column(JSON, nullable=True)
    citation_payload = Column(JSON, nullable=True)
    source_block_ids = Column(JSON, nullable=True)
    edit_reason = Column(String(2048), nullable=True)
    edited_by = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="draft")
    downstream_revision_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_wb_chunk_edits_snapshot", "parse_snapshot_id"),
        Index("ix_wb_chunk_edits_source", "source_file_id"),
        Index("ix_wb_chunk_edits_evidence", "base_evidence_id"),
        Index("ix_wb_chunk_edits_editor", "edited_by"),
    )
