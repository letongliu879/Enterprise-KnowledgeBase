"""Pydantic DTOs for chunks."""

from pydantic import BaseModel
from typing import Any


class ChunkDetail(BaseModel):
    evidence_id: str
    doc_id: str
    content: str
    vector_text: str | None = None
    section_path: list[str] | None = None
    page_spans: list[dict[str, Any]] | None = None
    chunk_type: str | None = None
    metadata: dict[str, Any] | None = None
