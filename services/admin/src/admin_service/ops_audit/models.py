"""Ops audit DTOs."""

from datetime import datetime

from pydantic import BaseModel

from reality_rag_contracts import OpsAuditLogEntry


class AuditLogQueryRequest(BaseModel):
    actor_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    tenant_id: str | None = None
    collection_id: str | None = None
    limit: int = 50
    offset: int = 0


class AuditLogListResponse(BaseModel):
    items: list[OpsAuditLogEntry]
    total: int
    limit: int
    offset: int
