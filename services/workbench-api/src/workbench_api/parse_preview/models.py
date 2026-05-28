"""Pydantic DTOs for parse preview."""

from pydantic import BaseModel
from typing import Any


class ParsePreviewCreateRequest(BaseModel):
    upload_id: str
    source_file_id: str
    collection_id: str
    tenant_id: str
    parser_profile_id: str
    parser_override_json: dict[str, Any] | None = None
    actor: str


class ParsePreviewResponse(BaseModel):
    request_id: str
    trace_id: str
    status: str
    parse_snapshot_id: str | None = None
    error_message: str | None = None
