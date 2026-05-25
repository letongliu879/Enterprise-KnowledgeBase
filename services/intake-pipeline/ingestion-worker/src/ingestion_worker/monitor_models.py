"""Data models for monitored ingestion."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MonitorRunRequest(BaseModel):
    collection_id: str
    source_files: list[str] = Field(default_factory=list)
    concurrency: int = Field(default=4, ge=1, le=16)
    index_version: str | None = None


class MonitorRunSummary(BaseModel):
    run_id: str
    collection_id: str
    index_version: str
    status: str
    concurrency: int
    total_files: int
    processed_files: int
    approved_files: int
    rejected_files: int
    quarantined_files: int
    pending_review_files: int
    failed_files: int
    created_at: str
    updated_at: str


class MonitorRunDetail(MonitorRunSummary):
    source_files: list[str] = Field(default_factory=list)
    last_seq: int = 0
    events: list[dict[str, Any]] = Field(default_factory=list)
