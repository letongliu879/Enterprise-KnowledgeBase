"""PipelineStage Protocol and StageContext."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from reality_rag_contracts import (
    AgentReview,
    CanonicalMetadata,
    Collection,
    ConversionResult,
    IndexAssetBundle,
    QualityReport,
    Tenant,
)

from ..agent_review_cache import AgentReviewCache

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reality_rag_persistence.repositories.documents import DocumentRepository
    from reality_rag_persistence.repositories.document_policies import DocumentPolicyRepository
    from ..monitor_context import MonitorContext


@dataclass
class StageContext:
    """Mutable context passed through each pipeline stage."""

    collection_id: str
    source_file_path: str
    collection: Collection | None = None
    tenant: Tenant | None = None
    result: ConversionResult | None = None
    quality_report: QualityReport | None = None
    agent_review: AgentReview | None = None
    publish_status: Any = None
    canonical_metadata: CanonicalMetadata | None = None
    asset_paths: dict[str, str] = field(default_factory=dict)
    asset_bundle: IndexAssetBundle | None = None
    doc_id: str = ""
    final_doc_id: str = ""
    logical_document_id: str = ""
    parse_snapshot_id: str = ""
    source_file_id: str = ""
    object_id: str = ""
    content_hash: str = ""
    source_hash: str = ""
    version: int = 1
    job_id: str = ""
    intake_job_id: str = ""
    ticket_id: str = ""
    index_version: str = "v1"
    monitor: MonitorContext | None = None
    session: Session | None = None
    document_repo: DocumentRepository | None = None
    policy_repo: DocumentPolicyRepository | None = None
    skipped: bool = False
    skip_reason: str = ""

    def emit(self, **kwargs: Any) -> dict[str, Any] | None:
        if self.monitor is None:
            return None
        return self.monitor.emit(**kwargs)


class PipelineStage(Protocol):
    """Single stage in the ingestion pipeline."""

    def run(self, ctx: StageContext) -> StageContext:
        """Execute the stage and return the (possibly mutated) context."""
        ...
