from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from indexing_service._compat import StrEnum, utc_now


class IndexBuildStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    READY = "READY"
    FAILED = "FAILED"


class IndexVersionStatus(StrEnum):
    BUILDING = "BUILDING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    FAILED = "FAILED"
    DISCARDED = "DISCARDED"
    ROLLED_BACK = "ROLLED_BACK"


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
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class IndexVersionRecord(BaseModel):
    index_version_id: str
    tenant_id: str
    collection_id: str
    status: IndexVersionStatus
    schema_version: str
    index_profile_id: str
    chunk_profile_id: str
    embedding_model: str
    opensearch_index: str
    qdrant_collection: str
    chunk_count: int = 0
    previous_active_index_version_id: str | None = None
    replaced_by_index_version_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    activated_at: datetime | None = None
    rolled_back_at: datetime | None = None
    cleaned_up_at: datetime | None = None


class IndexVersionActionReceipt(BaseModel):
    index_version_id: str
    action: str
    accepted: bool = True
    reactivated_index_version_id: str | None = None
    deactivated_index_version_id: str | None = None
    removed_chunk_count: int = 0


class ChunkRecordRecord(BaseModel):
    chunk_id: str
    record_id: str = ""
    kb_id: str = ""
    tenant_id: str
    collection_id: str
    final_doc_id: str
    index_version_id: str
    document_index_revision_id: str
    chunk_type: str
    doc_type_kwd: str = ""
    available_int: int = 1
    display_text: str
    content_with_weight: str = ""
    content_ltks: str = ""
    content_sm_ltks: str = ""
    vector_text: str
    title_text: str = ""
    embedding_text: str = ""
    embedding_title_weight: float = 0.1
    docnm_kwd: str = ""
    title_tks: str = ""
    title_sm_tks: str = ""
    authors_tks: str = ""
    authors_sm_tks: str = ""
    important_kwd: list[str] = Field(default_factory=list)
    important_tks: str = ""
    question_kwd: list[str] = Field(default_factory=list)
    question_tks: str = ""
    tag_kwd: list[str] = Field(default_factory=list)
    tag_feas: dict[str, float] = Field(default_factory=dict)
    pagerank_fea: int | None = None
    removed_kwd: str = "N"
    source_id: list[str] = Field(default_factory=list)
    chunk_data: dict[str, object] | None = None
    img_id: str = ""
    mom_id: str = ""
    create_time: str = ""
    create_timestamp_flt: float = 0.0
    position_int: list[tuple[int, int, int, int, int]] = Field(default_factory=list)
    page_num_int: list[int] = Field(default_factory=list)
    top_int: list[int] = Field(default_factory=list)
    section_path: list[str]
    page_spans: list[dict[str, int]]
    source_block_ids: list[str]
    keyword_terms: list[str]
    confirmed_tags: list[str]
    visibility: str
    published_document_state: str
    access_control: dict[str, list[str]]
    citation_payload: dict[str, object]
    lexical_payload: dict[str, object]
    vector_payload: dict[str, object]
    metadata: dict[str, object] = Field(default_factory=dict)
    chunk_hash: str


class ParseSnapshotRecord(BaseModel):
    parse_snapshot_id: str
    request_id: str
    tenant_id: str
    collection_id: str
    source_file_id: str
    source_binary_ref: str
    source_filename: str
    source_suffix: str
    parser_id: str
    parser_backend: str
    collection_parser_config: dict[str, object] = Field(default_factory=dict)
    parser_config: dict[str, object] = Field(default_factory=dict)
    input_hash: str
    preview_text: str
    upstream_chunks: list[dict[str, object]] = Field(default_factory=list)
    outline: list[str]
    document_metadata: dict[str, object] = Field(default_factory=dict)
    chunk_preview: list[dict[str, object]]
    warnings: list[str]
    decision_reason: str
    created_at: datetime = Field(default_factory=utc_now)
