"""Event ingestion module for downstream service callbacks.

Downstream services (intake, approval, indexing) POST events here
to drive projection updates. Each service authenticates with its
own X-Service-Key.
"""

import secrets
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import config
from ..deps import get_db
from ..projections.projector import ProjectionProjector

# -- Models (define first to avoid circular imports in adapters) --

class ProjectionEvent(BaseModel):
    """Internal canonical event format for the projection projector."""

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


# -- Adapters (import after ProjectionEvent is defined) --

from .adapters import get_adapter

# -- Authentication --

SERVICE_KEYS: dict[str, str] = {
    "intake": config.workbench_event_key_intake,
    "approval": config.workbench_event_key_approval,
    "indexing": config.workbench_event_key_indexing,
}


def _verify_key(provided_key: str | None, expected_key: str) -> bool:
    if not provided_key or not expected_key:
        return False
    return secrets.compare_digest(provided_key.encode(), expected_key.encode())


async def verify_service_key(
    request: Request,
    x_service_key: str | None = Header(None, alias="X-Service-Key"),
) -> Literal["intake", "approval", "indexing"]:
    """Verify X-Service-Key and return the matched service name."""
    for service, expected in SERVICE_KEYS.items():
        if _verify_key(x_service_key, expected):
            path_service = request.path_params.get("service")
            if path_service and path_service != service:
                raise HTTPException(status_code=403, detail="Service key does not match URL path")
            return service  # type: ignore[return-value]
    raise HTTPException(status_code=401, detail="Invalid or missing service key")


# -- Routes --

router = APIRouter(prefix="/internal/events")


@router.post("/{service}")
async def ingest_events(
    service: Literal["intake", "approval", "indexing"],
    events: list[dict[str, Any]],
    verified_service: str = Depends(verify_service_key),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ingest a batch of events from a downstream service."""
    if service != verified_service:
        return {"error": "Service mismatch", "expected": service, "received": verified_service}

    adapter = get_adapter(service)
    projection_events = adapter.adapt_batch(events)

    projector = ProjectionProjector(db)
    results = []
    applied_count = 0
    skipped_count = 0
    error_count = 0

    for event in projection_events:
        try:
            result = projector.record_and_apply(event.model_dump())
            results.append({"event_id": event.event_id, **result})
            if result["applied"]:
                applied_count += 1
            else:
                skipped_count += 1
        except Exception as e:
            error_count += 1
            results.append({"event_id": event.event_id, "error": str(e)})

    return {
        "service": service,
        "received": len(events),
        "adapted": len(projection_events),
        "applied": applied_count,
        "skipped": skipped_count,
        "errors": error_count,
        "details": results,
    }
