"""Pydantic DTOs for chunk edits."""

from pydantic import BaseModel
from typing import Any


class ChunkEditCreateRequest(BaseModel):
    base_evidence_id: str
    operation: str
    content: str | None = None
    vector_text: str | None = None
    section_path: list[str] | None = None
    metadata_patch: dict[str, Any] | None = None
    citation_payload: dict[str, Any] | None = None
    source_block_ids: list[str] | None = None
    edit_reason: str | None = None


class ChunkEditUpdateRequest(BaseModel):
    content: str | None = None
    vector_text: str | None = None
    section_path: list[str] | None = None
    metadata_patch: dict[str, Any] | None = None
    citation_payload: dict[str, Any] | None = None
    source_block_ids: list[str] | None = None
    edit_reason: str | None = None
    operation: str | None = None
