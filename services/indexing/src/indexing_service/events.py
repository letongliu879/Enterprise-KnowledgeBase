"""Emit projection events to workbench-api from indexing-service.

Fail-open: if workbench is unreachable or mis-configured the indexing job
continues unaffected.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _workbench_events_url() -> str | None:
    base_url = str(
        os.environ.get("WORKBENCH_API_BASE_URL")
        or os.environ.get("WORKBENCH_BASE_URL")
        or ""
    ).rstrip("/")
    if not base_url:
        return None
    return f"{base_url}/internal/events/indexing"


def _workbench_service_key() -> str:
    return str(os.environ.get("WORKBENCH_EVENT_KEY_INDEXING", "")).strip()


def emit_indexing_events(events: list[dict[str, Any]]) -> bool:
    """Send a batch of indexing events to workbench-api."""
    url = _workbench_events_url()
    api_key = _workbench_service_key()
    if not url or not api_key:
        return True

    try:
        response = httpx.post(
            url,
            json=events,
            headers={"X-Service-Key": api_key},
            timeout=30.0,
        )
    except Exception:
        logger.exception("failed to emit indexing events to workbench")
        return False

    if response.status_code >= 400:
        logger.warning(
            "workbench rejected indexing events with status %s: %s",
            response.status_code,
            response.text,
        )
        return False

    try:
        body = response.json()
    except Exception:
        body = {}
    if int(body.get("errors", 0) or 0) > 0:
        logger.warning("workbench reported projection errors: %s", body)
        return False
    return True


def build_indexing_event(
    *,
    event_id: str,
    event_type: str,
    tenant_id: str,
    collection_id: str | None,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int,
    payload: dict[str, Any],
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Build a canonical workbench projection event."""
    return {
        "event_id": event_id,
        "event_type": event_type,
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "aggregate_version": aggregate_version,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "trace_id": trace_id or "",
    }
