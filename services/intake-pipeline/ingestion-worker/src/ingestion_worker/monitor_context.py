"""MonitorContext for event emission within a lane.

Upgraded to also emit telemetry_events via TelemetryStore.
SSE monitor events remain the primary real-time observation path;
telemetry_events provide the durable, queryable audit trail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from reality_rag_contracts import TelemetryEvent, TelemetryStatus
from reality_rag_persistence.ingestion_monitor import IngestionMonitorStore
from reality_rag_persistence.telemetry import TelemetryStore

# Map SSE event_type strings to TelemetryEventName values.
_EVENT_NAME_MAP: dict[str, str] = {
    "review.started": "review_started",
    "review.completed": "review_completed",
    "review.failed": "review_failed",
    "conversion.started": "conversion_started",
    "conversion.completed": "conversion_completed",
    "conversion.failed": "conversion_failed",
    "upload.started": "upload_started",
    "upload.completed": "upload_completed",
    "upload.failed": "upload_failed",
    "publish.started": "publish_started",
    "publish.completed": "publish_completed",
    "publish.failed": "publish_failed",
    "job.completed": "intake_job_completed",
    "job.failed": "intake_job_failed",
    "job.cancelled": "intake_job_cancelled",
}

# Map SSE level to TelemetryStatus.
_LEVEL_STATUS_MAP: dict[str, str] = {
    "info": "succeeded",
    "warning": "degraded",
    "error": "failed",
}


def _derive_status(event_type: str, level: str) -> str:
    if event_type.endswith(".started"):
        return TelemetryStatus.STARTED.value
    if event_type.endswith(".failed"):
        return TelemetryStatus.FAILED.value
    return _LEVEL_STATUS_MAP.get(level, TelemetryStatus.SUCCEEDED.value)


@dataclass(frozen=True)
class MonitorContext:
    """Immutable context for a single lane in a monitored ingestion run."""

    run_id: str
    lane_id: int
    source_file_path: str
    store: IngestionMonitorStore
    telemetry_store: TelemetryStore | None = None
    trace_id: str = ""
    intake_job_id: str = ""
    collection_id: str = ""
    component: str = "ingestion-worker"
    component_version: str = "0.1.0"

    def emit(
        self,
        *,
        event_type: str,
        phase: str,
        message: str,
        level: str = "info",
        doc_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an event to the monitor store and return it.

        Also emits a telemetry_event when ``telemetry_store`` is configured.
        Telemetry failures are silently swallowed to avoid blocking the pipeline.
        """
        event = self.store.append_event(
            self.run_id,
            lane_id=self.lane_id,
            event_type=event_type,
            phase=phase,
            message=message,
            level=level,
            source_file_path=self.source_file_path,
            doc_id=doc_id,
            payload=payload,
        )

        if self.telemetry_store is not None:
            self._emit_telemetry(event_type, level, doc_id, payload)

        return event

    def _emit_telemetry(
        self,
        event_type: str,
        level: str,
        doc_id: str | None,
        payload: dict[str, Any] | None,
    ) -> None:
        try:
            telemetry_name = _EVENT_NAME_MAP.get(event_type, event_type)
            status = _derive_status(event_type, level)
            duration_ms = None
            if payload:
                duration_ms = payload.get("duration_ms") or payload.get("latency_ms")
                if isinstance(duration_ms, (int, float)):
                    duration_ms = int(duration_ms)

            attrs: dict[str, Any] = {}
            if payload:
                # Copy only safe, telemetry-relevant fields from payload
                for key in ("model", "converter_name", "converter_version",
                            "file_type", "quality_grade", "review_status",
                            "routing_recommendation", "decision", "chunk_count",
                            "index_version", "embedding_model_version"):
                    if key in payload:
                        attrs[key] = payload[key]

            tel_event = TelemetryEvent(
                event_id=f"tel_{uuid.uuid4().hex[:20]}",
                event_name=telemetry_name,
                trace_id=self.trace_id or self.run_id,
                intake_job_id=self.intake_job_id or None,
                collection_id=self.collection_id or None,
                component=self.component,
                component_version=self.component_version,
                status=status,
                duration_ms=duration_ms,
                attributes_json=attrs,
            )
            self.telemetry_store.emit_event(tel_event)
        except Exception:
            # Telemetry must never block the main pipeline
            pass
