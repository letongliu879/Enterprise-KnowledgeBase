"""Intake service event adapter.

Maps intake domain events into workbench projection events.
Intake is the owner of document lifecycle fields.
"""

from typing import Any

from .base import EventAdapter
from ..models import ProjectionEvent


class IntakeEventAdapter(EventAdapter):
    """Adapter for intake service events."""

    @property
    def service_name(self) -> str:
        return "intake"

    def adapt(self, native_event: dict[str, Any]) -> list[ProjectionEvent]:
        event_type = native_event.get("event_type")
        tenant_id = native_event.get("tenant_id", "")
        collection_id = native_event.get("collection_id")
        occurred_at = native_event.get("occurred_at")
        trace_id = native_event.get("trace_id")
        payload = native_event.get("payload", {})
        version = native_event.get("aggregate_version", 1)

        events: list[ProjectionEvent] = []

        if event_type in {"SourceFileRegistered", "FileReady"}:
            # Update task projection with source file info
            _tenant_id = tenant_id or "default"
            _upload_id = payload.get("upload_id", "")
            if not _upload_id:
                # Fallback: use source_file_id as aggregate_id for FileReady events
                _upload_id = payload.get("source_file_id", "")
            # Use fixed version numbers per event type to ensure they override
            # workbench local projection updates (version 1-2)
            _version = 10 if event_type == "SourceFileRegistered" else 20
            events.append(ProjectionEvent(
                event_id=native_event["event_id"],
                event_type=event_type,
                service=self.service_name,
                tenant_id=_tenant_id,
                collection_id=collection_id,
                aggregate_type="task",
                aggregate_id=_upload_id,
                aggregate_version=_version,
                occurred_at=occurred_at,
                payload={
                    "tenant_id": _tenant_id,
                    "collection_id": collection_id,
                    "upload_id": _upload_id,
                    "source_file_id": payload.get("source_file_id"),
                    "source_file_state": payload.get("state"),
                },
                trace_id=trace_id,
            ))

        elif event_type == "IntakeJobStateChanged":
            # Update task projection with job state
            job_payload = {
                "tenant_id": tenant_id or "default",
                "collection_id": collection_id,
                "upload_id": payload.get("upload_id", ""),
                "intake_job_id": payload.get("intake_job_id"),
                "intake_job_state": payload.get("state"),
            }
            if payload.get("parse_snapshot_id"):
                job_payload["parse_snapshot_id"] = payload["parse_snapshot_id"]
            if payload.get("ticket_id"):
                job_payload["ticket_id"] = payload["ticket_id"]
            if payload.get("final_doc_id"):
                job_payload["doc_id"] = payload["final_doc_id"]
            if payload.get("published_document_id"):
                job_payload["published_doc_id"] = payload["published_document_id"]

            events.append(ProjectionEvent(
                event_id=native_event["event_id"],
                event_type=event_type,
                service=self.service_name,
                tenant_id=tenant_id,
                collection_id=collection_id,
                aggregate_type="task",
                aggregate_id=payload.get("upload_id", ""),
                aggregate_version=30,
                occurred_at=occurred_at,
                payload=job_payload,
                trace_id=trace_id,
            ))

            # Also update document projection if we have a doc_id
            if payload.get("final_doc_id"):
                doc_payload = {
                    "doc_id": payload["final_doc_id"],
                    "tenant_id": tenant_id,
                    "collection_id": collection_id,
                    "source_file_id": payload.get("source_file_id"),
                    "parse_snapshot_id": payload.get("parse_snapshot_id"),
                    "upload_id": payload.get("upload_id"),
                    "document_state": payload.get("state"),
                }
                events.append(ProjectionEvent(
                    event_id=f"{native_event['event_id']}:doc",
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="document",
                    aggregate_id=payload["final_doc_id"],
                    aggregate_version=30,
                    occurred_at=occurred_at,
                    payload=doc_payload,
                    trace_id=trace_id,
                ))

        elif event_type == "StageCompleted":
            upload_id = payload.get("upload_id")
            if upload_id:
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="task",
                    aggregate_id=upload_id,
                    aggregate_version=30,
                    occurred_at=occurred_at,
                    payload={
                        "tenant_id": tenant_id or "default",
                        "collection_id": collection_id,
                        "upload_id": upload_id,
                        "intake_job_state": "processing",
                    },
                    trace_id=trace_id,
                ))

        elif event_type in {"PublishedDocumentStateChanged", "PublishCompleted"}:
            doc_id = payload.get("doc_id") or payload.get("final_doc_id")
            if doc_id:
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="document",
                    aggregate_id=doc_id,
                    aggregate_version=40,
                    occurred_at=occurred_at,
                    payload={
                        "doc_id": doc_id,
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "publish_state": payload.get("state", "published"),
                    },
                    trace_id=trace_id,
                ))

            # Also update task projection
            upload_id = payload.get("upload_id")
            if upload_id:
                events.append(ProjectionEvent(
                    event_id=f"{native_event['event_id']}:task",
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="task",
                    aggregate_id=upload_id,
                    aggregate_version=40,
                    occurred_at=occurred_at,
                    payload={
                        "tenant_id": tenant_id or "default",
                        "collection_id": collection_id,
                        "upload_id": upload_id,
                        "published_document_state": payload.get("state", "published"),
                        "intake_job_state": "published",
                        "active_index_version": payload.get("index_version"),
                        "overall_status": "published",
                    },
                    trace_id=trace_id,
                ))

        return events
