"""Pydantic request/response DTOs for upload sessions."""

from pydantic import BaseModel, Field
from typing import Any


class UploadCreateRequest(BaseModel):
    collection_id: str
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    selected_parser_profile_id: str | None = None
    parser_override_json: dict[str, Any] | None = None
    access_scope_json: dict[str, Any] | None = None


class UploadListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
