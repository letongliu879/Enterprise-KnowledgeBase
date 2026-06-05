"""Indexing service event adapter.

Maps indexing domain events into workbench projection events.
Indexing only updates index-related fields; document lifecycle fields
are owned by intake.
"""

from typing import Any

from .base import EventAdapter
from .. import ProjectionEvent


class IndexingEventAdapter(EventAdapter):
    """Adapter for indexing service events."""

    @property
    def service_name(self) -> str:
        return "indexing"

    def adapt(self, native_event: dict[str, Any]) -> list["ProjectionEvent"]:
        event_type = native_event.get("event_type")
        tenant_id = native_event.get("tenant_id", "")
        collection_id = native_event.get("collection_id")
        occurred_at = native_event.get("occurred_at")
        trace_id = native_event.get("trace_id")
        payload = native_event.get("payload", {})
        version = native_event.get("aggregate_version", 1)

        events: list["ProjectionEvent"] = []

        if event_type == "ParseSnapshotCompleted":
            doc_id = payload.get("doc_id")
            if doc_id:
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="document",
                    aggregate_id=doc_id,
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "doc_id": doc_id,
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "parse_snapshot_id": payload.get("parse_snapshot_id"),
                        "document_state": "PARSED",
                        "page_count": payload.get("page_count", 0),
                        "parser_profile_id": payload.get("parser_profile_id"),
                        "parser_profile_name": payload.get("parser_profile_name"),
                    },
                    trace_id=trace_id,
                ))

        elif event_type == "ChunksMaterialized":
            doc_id = payload.get("doc_id")
            chunk_count = payload.get("chunk_count", 0)

            if doc_id:
                # Update document projection with chunk_count
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="document",
                    aggregate_id=doc_id,
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "doc_id": doc_id,
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "chunk_count": chunk_count,
                    },
                    trace_id=trace_id,
                ))

            # Project first N chunks as lightweight summary
            chunks = payload.get("chunks", [])
            preview_limit = payload.get("preview_limit", 100)
            for idx, chunk in enumerate(chunks[:preview_limit]):
                events.append(ProjectionEvent(
                    event_id=f"{native_event['event_id']}:chunk:{idx}",
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="chunk",
                    aggregate_id=chunk["evidence_id"],
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "evidence_id": chunk["evidence_id"],
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "doc_id": doc_id,
                        "source_file_id": payload.get("source_file_id"),
                        "parse_snapshot_id": payload.get("parse_snapshot_id"),
                        "chunk_ordinal": chunk.get("ordinal", idx),
                        "content_preview": chunk.get("preview"),
                        "section_path_json": chunk.get("section_path"),
                        "page_from": chunk.get("page_from"),
                        "page_to": chunk.get("page_to"),
                        "source_anchor_json": chunk.get("source_anchor"),
                        "state": "active",
                    },
                    trace_id=trace_id,
                ))

        elif event_type == "IndexBuildCompleted":
            doc_id = payload.get("doc_id")
            if doc_id:
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="document",
                    aggregate_id=doc_id,
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "doc_id": doc_id,
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "index_build_state": payload.get("state", "ACTIVE"),
                        "active_index_version": payload.get("index_version"),
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
                        aggregate_version=version,
                        occurred_at=occurred_at,
                        payload={
                            "index_build_state": payload.get("state", "ACTIVE"),
                            "active_index_version": payload.get("index_version"),
                        },
                        trace_id=trace_id,
                    ))

        elif event_type == "ChunkRevisionActivated":
            evidence_id = payload.get("evidence_id")
            if evidence_id:
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="chunk",
                    aggregate_id=evidence_id,
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "evidence_id": evidence_id,
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "doc_id": payload.get("doc_id"),
                        "active_revision_id": payload.get("revision_id"),
                        "state": "active",
                    },
                    trace_id=trace_id,
                ))

        return events
