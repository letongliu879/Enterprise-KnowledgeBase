"""Pydantic DTOs for tickets."""

from pydantic import BaseModel
from typing import Any


class TicketDecisionRequest(BaseModel):
    decision_request_id: str
    action: str
    reason: str | None = None
    actor: str | None = None  # Deprecated: backend derives actor from authenticated user
    tenant_id: str
    collection_id: str


class TicketItem(BaseModel):
    ticket_id: str
    collection_id: str
    status: str
    doc_id: str | None = None
    source_file_id: str | None = None
    created_at: str
    updated_at: str | None = None


class TicketDetail(BaseModel):
    ticket_id: str
    collection_id: str
    status: str
    doc_id: str | None = None
    source_file_id: str | None = None
    parse_snapshot_id: str | None = None
    filename: str | None = None
    decision: str | None = None
    decision_reason: str | None = None
    decided_by: str | None = None
    tenant_id: str
    created_at: str
    updated_at: str | None = None
