"""Stage input/output schemas for logical stages.

Maps the current 8 Python stages into 3 logical stage contracts:
  - conversion: ConversionStage + DedupStage + VersionStage + QualityStage
  - agent_review: ReviewStage
  - publishing: AssetStage + PersistStage

Field naming follows intake-pipeline.md target architecture:
  - preliminary_doc_id: candidate identity within ingestion pipeline
  - logical_document_id: stable across versions
  - version_conflict: conflict hint for approval domain (not auto-resolved)
  - final_doc_id: NOT present — only approval domain generates this

Legacy compatibility:
  - StageContext.doc_id maps to preliminary_doc_id in adapters
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from reality_rag_contracts import (
    AgentReview,
    CanonicalMetadata,
    ConversionResult,
    IndexAssetBundle,
    PublishStatus,
    QualityReport,
)


# ──────────────────────────────────────────────────────────────────────────────
#  conversion logical stage
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ConversionStageInput:
    """Input boundary for the conversion logical stage.

    Fields needed from orchestrator / upstream:
      - intake_job_id, collection_id, source_file_path
      - tenant context (tenant_id, collection_authority_level)
      - Optional lookup hints for dedup/version (DB-dependent in current code)
    """

    schema_version: str = "v1"
    intake_job_id: str = ""
    collection_id: str = ""
    source_file_path: str = ""
    tenant_id: str = "default"
    collection_authority_level: int = 0
    index_version: str = "v1"

    # Pre-computed source hash (avoids re-reading file in pure executor).
    source_hash: str = ""

    # [TRANSITIONAL] Dedup/version lookups currently hit the DB.
    # In target architecture these come from document-service queries.
    existing_published_doc_id_by_source_hash: str | None = None
    latest_version_by_logical_id: int | None = None


@dataclass
class VersionConflictInfo:
    """Version conflict detected during versioning.

    [TRANSITIONAL] Current code auto-archives the latest version.
    Target architecture: approval domain decides between:
      new_version, independent_document, business_duplicate.
    """

    logical_document_id: str
    existing_version: int
    proposed_version: int
    existing_doc_id: str = ""
    conflict_type: str = "new_version"


@dataclass
class ConversionStageOutput:
    """Output boundary for the conversion logical stage.

    Consumed by: agent_review stage, approval domain (for version_conflict).
    """

    schema_version: str = "v1"
    input_hash: str = ""
    result_hash: str = ""

    conversion_result: ConversionResult | None = None
    quality_report: QualityReport | None = None

    # Identity fields (target architecture)
    preliminary_doc_id: str = ""
    logical_document_id: str = ""
    version: int = 1
    source_hash: str = ""
    version_conflict: VersionConflictInfo | None = None

    # Control flags
    dedup_skipped: bool = False
    skip_reason: str | None = None



# ──────────────────────────────────────────────────────────────────────────────
#  agent_review logical stage
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ReviewStageInput:
    """Input boundary for the agent_review logical stage."""

    schema_version: str = "v1"
    intake_job_id: str = ""
    collection_id: str = ""
    preliminary_doc_id: str = ""
    logical_document_id: str = ""
    canonical_content: str = ""
    quality_report: QualityReport | None = None
    collection_authority_level: int = 0
    review_model: str = ""


@dataclass
class ReviewStageOutput:
    """Output boundary for the agent_review logical stage.

    Consumed by: approval domain (system decision / manual ticket).
    """

    schema_version: str = "v1"
    input_hash: str = ""
    result_hash: str = ""

    agent_review: AgentReview | None = None
    cache_hit: bool = False
    review_context: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
#  publishing logical stage
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class PublishingStageInput:
    """Input boundary for the publishing logical stage.

    Requires approval decision (publish_status) because publishing
    must NOT run until approval domain has decided.

    [TRANSITIONAL] Current MVP runs DecisionStage inside the worker;
    target architecture: publish_status comes from approval-service ticket.
    """

    schema_version: str = "v1"
    intake_job_id: str = ""
    collection_id: str = ""
    preliminary_doc_id: str = ""
    final_doc_id: str = ""
    logical_document_id: str = ""
    version: int = 1
    source_hash: str = ""
    tenant_id: str = "default"
    collection_authority_level: int = 0
    index_version: str = "v1"

    # Upstream stage outputs
    conversion_result: ConversionResult | None = None
    quality_report: QualityReport | None = None
    agent_review: AgentReview | None = None

    # Upstream stage outputs
    conversion_result: ConversionResult | None = None
    quality_report: QualityReport | None = None
    agent_review: AgentReview | None = None
    review_context: dict[str, Any] = field(default_factory=dict)

    # Approval decision
    publish_status: PublishStatus = PublishStatus.DRAFT


@dataclass
class PublishingStageOutput:
    """Output boundary for the publishing logical stage.

    Produced by: publishing-worker (asset write + document persist).
    Consumed by: indexing-service (IndexBuildRequested event).
    """

    schema_version: str = "v1"
    input_hash: str = ""
    result_hash: str = ""

    asset_paths: dict[str, str] = field(default_factory=dict)
    asset_bundle: IndexAssetBundle | None = None
    canonical_metadata: CanonicalMetadata | None = None
    document_persisted: bool = False
    policy_persisted: bool = False
