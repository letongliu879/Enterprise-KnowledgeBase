"""Pydantic DTOs for workspace aggregation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkspaceTicketView(BaseModel):
    ticket_id: str
    collection_id: str
    status: str
    tenant_id: str
    doc_id: str | None = None
    source_file_id: str | None = None
    parse_snapshot_id: str | None = None
    upload_id: str | None = None
    title: str | None = None
    filename: str | None = None
    priority: str | None = None
    assignee_user_id: str | None = None
    decision: str | None = None
    decision_reason: str | None = None
    decided_by: str | None = None
    agent_decision: str | None = None
    agent_risk_level: str | None = None
    agent_finding_count: int = 0
    agent_blocking_finding_count: int = 0
    failure_code: str | None = None
    failure_stage: str | None = None
    next_action: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    projection_updated_at: str | None = None
    is_stale: bool = False
    source: Literal["approval", "projection", "merged"] = "merged"


class WorkspaceDocumentView(BaseModel):
    doc_id: str | None = None
    tenant_id: str | None = None
    collection_id: str | None = None
    source_file_id: str | None = None
    parse_snapshot_id: str | None = None
    published_doc_id: str | None = None
    upload_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    document_state: str | None = None
    publish_state: str | None = None
    active_index_version: str | None = None
    chunk_count: int = 0
    page_count: int = 0
    parser_profile_id: str | None = None
    parser_profile_name: str | None = None
    projection_updated_at: str | None = None
    is_stale: bool = False
    degraded_reason: str | None = None
    linkage_source: Literal[
        "document_projection",
        "ticket_projection",
        "task_projection",
        "missing",
    ] = "missing"


class WorkspaceTaskView(BaseModel):
    upload_id: str
    collection_id: str
    status: str
    filename: str | None = None
    source_file_id: str | None = None
    intake_job_id: str | None = None
    parse_snapshot_id: str | None = None
    ticket_id: str | None = None
    published_doc_id: str | None = None
    doc_id: str | None = None
    progress_pct: int = 0
    source_file_state: str | None = None
    intake_job_state: str | None = None
    parse_snapshot_state: str | None = None
    ticket_state: str | None = None
    published_document_state: str | None = None
    index_build_state: str | None = None
    active_index_version: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    projection_updated_at: str | None = None
    is_stale: bool = False


class WorkspaceSourceFileView(BaseModel):
    source_file_id: str
    upload_id: str | None = None
    tenant_id: str | None = None
    collection_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    state: str | None = None
    intake_job_id: str | None = None
    scan_verdict: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class WorkspaceParseSnapshotView(BaseModel):
    parse_snapshot_id: str
    source_file_id: str | None = None
    tenant_id: str | None = None
    collection_id: str | None = None
    source_filename: str | None = None
    source_suffix: str | None = None
    parser_id: str | None = None
    parser_backend: str | None = None
    parser_profile_id: str | None = None
    effective_policy: str | None = None
    decision_reason: str | None = None
    preview_text: str | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: str | None = None


class WorkspaceChunkView(BaseModel):
    evidence_id: str
    doc_id: str
    content: str
    vector_text: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_spans: list[dict[str, Any]] = Field(default_factory=list)
    chunk_type: str | None = None
    metadata: dict[str, Any] | None = None


class WorkspaceChunkListView(BaseModel):
    items: list[WorkspaceChunkView] = Field(default_factory=list)
    total: int = 0


class WorkspaceChunkEditView(BaseModel):
    chunk_edit_id: str
    tenant_id: str
    collection_id: str
    source_file_id: str | None = None
    parse_snapshot_id: str | None = None
    base_evidence_id: str
    edit_scope: str
    operation: str
    content: str | None = None
    vector_text: str | None = None
    section_path: list[str] | None = None
    metadata_patch: dict[str, Any] | None = None
    citation_payload: dict[str, Any] | None = None
    source_block_ids: list[str] | None = None
    edit_reason: str | None = None
    edited_by: str
    status: str
    downstream_revision_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class WorkspaceChunkEditListView(BaseModel):
    items: list[WorkspaceChunkEditView] = Field(default_factory=list)
    total: int = 0


class WorkspaceAgentReviewFindingView(BaseModel):
    finding_id: str
    severity: str
    category: str
    problem_summary: str
    source_quote: str | None = None
    evidence_id: str | None = None
    doc_id: str | None = None
    source_file_id: str | None = None
    parse_snapshot_id: str | None = None
    page_from: int | None = None
    page_to: int | None = None
    state: str = "open"
    confidence: float | None = None
    chunk_quote: str | None = None
    why_wrong: str | None = None
    suggested_fix: str | None = None
    suggested_operation: str | None = None


class WorkspaceAgentReviewView(BaseModel):
    ticket_id: str
    decision: str | None = None
    source_file_id: str | None = None
    parse_snapshot_id: str | None = None
    findings: list[WorkspaceAgentReviewFindingView] = Field(default_factory=list)
    matched_count: int = 0
    unmatched_count: int = 0
    source: Literal["projection", "approval", "missing"] = "missing"


class WorkspaceCapabilitiesView(BaseModel):
    can_view_source: bool = False
    can_view_parsed_text: bool = False
    can_search_in_document: bool = False
    can_edit_drafts: bool = False
    can_jump_to_chunk: bool = False
    can_decide_ticket: bool = False
    can_approve: bool = False
    can_reject: bool = False
    can_upload: bool = False
    can_archive: bool = False
    can_retract: bool = False
    can_reindex: bool = False


class WorkspaceProjectionFreshnessView(BaseModel):
    ticket_projection_updated_at: str | None = None
    ticket_is_stale: bool = True
    document_projection_updated_at: str | None = None
    document_is_stale: bool = True


class WorkspaceDetailView(BaseModel):
    ticket_id: str
    ticket: WorkspaceTicketView | None = None
    document: WorkspaceDocumentView
    task: WorkspaceTaskView | None = None
    source_file: WorkspaceSourceFileView | None = None
    parse_snapshot: WorkspaceParseSnapshotView | None = None
    chunks: WorkspaceChunkListView = Field(default_factory=WorkspaceChunkListView)
    chunk_edits: WorkspaceChunkEditListView = Field(default_factory=WorkspaceChunkEditListView)
    agent_review: WorkspaceAgentReviewView
    capabilities: WorkspaceCapabilitiesView
    projection_freshness: WorkspaceProjectionFreshnessView
    degraded_parts: list[str] = Field(default_factory=list)
    trace_id: str
