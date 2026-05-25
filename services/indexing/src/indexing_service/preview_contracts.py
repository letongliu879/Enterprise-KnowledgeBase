from __future__ import annotations

from pydantic import BaseModel, Field


class ParsePreviewRequestedCommand(BaseModel):
    request_id: str
    tenant_id: str
    collection_id: str
    source_file_id: str
    source_binary_ref: str
    filename: str
    mime_type: str
    parser_id: str | None = None
    collection_parser_id: str | None = None
    collection_parser_config: dict[str, object] = Field(default_factory=dict)
    parser_config: dict[str, object] = Field(default_factory=dict)
    content_class_hint: str | None = None
    source_system: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)
    trace_id: str


class ParsePreviewAccepted(BaseModel):
    request_id: str
    source_file_id: str
    parse_snapshot_id: str
    parser_id: str
    decision_reason: str
    preview_text_ref: str
    chunk_preview_ref: str
    warnings: list[str] = Field(default_factory=list)
    trace_id: str
