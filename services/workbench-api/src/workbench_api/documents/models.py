"""Pydantic DTOs for document workspace and lifecycle actions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentLifecycleActionRequest(BaseModel):
    reason: str = ""
    index_profile_id: str | None = None


class BatchDocumentActionRequest(BaseModel):
    doc_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    index_profile_id: str | None = None


class BatchDocumentActionItemResult(BaseModel):
    doc_id: str
    success: bool
    previous_state: str | None = None
    new_state: str | None = None
    job_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class BatchDocumentActionResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    items: list[BatchDocumentActionItemResult] = Field(default_factory=list)
