"""Pydantic DTOs for parse snapshot."""

from pydantic import BaseModel
from typing import Any


class ChunkItem(BaseModel):
    evidence_id: str
    doc_id: str
    content: str
    section_path: list[str] | None = None
    page_spans: list[dict[str, Any]] | None = None
    chunk_type: str | None = None
