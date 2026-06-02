"""Unified projection event models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectionEvent(BaseModel):
    """Internal canonical event format for the projection projector.

    All downstream service events are adapted into this format before
    being passed to the projector.
    """

    event_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    service: str = Field(..., pattern=r"^(intake|approval|indexing)$")
    tenant_id: str = Field(..., min_length=1)
    collection_id: str | None = None
    aggregate_type: str = Field(..., pattern=r"^(task|ticket|document|chunk|agent_review)$")
    aggregate_id: str = Field(..., min_length=1)
    aggregate_version: int = Field(..., ge=1)
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
