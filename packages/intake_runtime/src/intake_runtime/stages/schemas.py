"""Stage input/output schemas for logical stages."""

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


@dataclass
class ConversionStageInput:
    schema_version: str = "v1"
    intake_job_id: str = ""
    collection_id: str = ""
    source_file_path: str = ""
    tenant_id: str = "default"
    collection_authority_level: int = 0
    index_version: str = "v1"
    source_hash: str = ""
    source_file_id: str = ""
    trace_id: str = ""
    source_metadata: dict[str, str] = field(default_factory=dict)
    existing_published_doc_id_by_source_hash: str | None = None
    latest_version_by_logical_id: int | None = None


@dataclass
class VersionConflictInfo:
    logical_document_id: str
    existing_version: int
    proposed_version: int
    existing_doc_id: str = ""
    conflict_type: str = "new_version"


@dataclass
class ConversionStageOutput:
    schema_version: str = "v1"
    input_hash: str = ""
    result_hash: str = ""
    conversion_result: ConversionResult | None = None
    quality_report: QualityReport | None = None
    preliminary_doc_id: str = ""
    logical_document_id: str = ""
    version: int = 1
    source_hash: str = ""
    version_conflict: VersionConflictInfo | None = None
    parse_snapshot_id: str = ""
    dedup_skipped: bool = False
    skip_reason: str | None = None


@dataclass
class ReviewStageInput:
    schema_version: str = "v1"
    intake_job_id: str = ""
    collection_id: str = ""
    source_file_id: str = ""
    preliminary_doc_id: str = ""
    logical_document_id: str = ""
    parse_snapshot_id: str = ""
    canonical_content: str = ""
    quality_report: QualityReport | None = None
    collection_authority_level: int = 0
    review_model: str = ""


@dataclass
class ReviewStageOutput:
    schema_version: str = "v1"
    input_hash: str = ""
    result_hash: str = ""
    agent_review: AgentReview | None = None
    cache_hit: bool = False
    review_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishingStageInput:
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
    conversion_result: ConversionResult | None = None
    quality_report: QualityReport | None = None
    agent_review: AgentReview | None = None
    review_context: dict[str, Any] = field(default_factory=dict)
    publish_status: PublishStatus = PublishStatus.DRAFT


@dataclass
class PublishingStageOutput:
    schema_version: str = "v1"
    input_hash: str = ""
    result_hash: str = ""
    asset_paths: dict[str, str] = field(default_factory=dict)
    asset_bundle: IndexAssetBundle | None = None
    canonical_metadata: CanonicalMetadata | None = None
    document_persisted: bool = False
    policy_persisted: bool = False

