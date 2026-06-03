from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from indexing_service._compat import StrEnum, utc_now
from reality_rag_contracts.indexing_models import (
    ChunkRecord,
    IndexVersionRecord,
    IndexVersionStatus,
    ParseSnapshotRecord,
)


class IndexBuildStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    READY = "READY"
    FAILED = "FAILED"


class BuildJobRecord(BaseModel):
    build_job_id: str
    build_request_id: str
    status: IndexBuildStatus
    tenant_id: str
    collection_id: str
    final_doc_id: str
    index_version_id: str
    idempotency_key: str
    accepted_command: str = "IndexBuildRequested"
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class IndexVersionActionReceipt(BaseModel):
    index_version_id: str
    action: str
    accepted: bool = True
    reactivated_index_version_id: str | None = None
    deactivated_index_version_id: str | None = None
    removed_chunk_count: int = 0


class ChunkRevisionRecord(BaseModel):
    revision_id: str
    base_evidence_id: str
    doc_id: str
    collection_id: str
    tenant_id: str
    operation: str = "update"
    content: str | None = None
    vector_text: str | None = None
    section_path: list[str] | None = None
    metadata_patch: dict[str, object] | None = None
    citation_payload: dict[str, object] | None = None
    status: str = "draft"
    superseded_evidence_id: str | None = None
    superseded_by: str | None = None
    idempotency_key: str | None = None
    trace_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)



