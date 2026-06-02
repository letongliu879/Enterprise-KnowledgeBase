"""Event ingestion routes for downstream service callbacks.

Downstream services (intake, approval, indexing) POST events here
to drive projection updates. Each service authenticates with its
own X-Service-Key.
"""

from typing import Any, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ..projections.projector import ProjectionProjector
from .adapters import get_adapter
from .auth import verify_service_key
from .models import ProjectionEvent

router = APIRouter(prefix="/internal/events")


@router.post("/{service}")
async def ingest_events(
    service: Literal["intake", "approval", "indexing"],
    events: list[dict[str, Any]],
    verified_service: str = Depends(verify_service_key),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ingest a batch of events from a downstream service.

    Each event is adapted into the canonical ProjectionEvent format,
    then recorded and applied by the projector. Events are processed
    independently: one failure does not block the batch.
    """
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
