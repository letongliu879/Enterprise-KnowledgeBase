"""Approval service event adapter.

Maps approval domain events into workbench projection events.
Approval callbacks drive ticket projection updates asynchronously.
"""

from typing import Any

from .base import EventAdapter
from ..models import ProjectionEvent


class ApprovalEventAdapter(EventAdapter):
    """Adapter for approval service events."""

    @property
    def service_name(self) -> str:
        return "approval"

    def adapt(self, native_event: dict[str, Any]) -> list[ProjectionEvent]:
        event_type = native_event.get("event_type")
        tenant_id = native_event.get("tenant_id", "")
        collection_id = native_event.get("collection_id")
        occurred_at = native_event.get("occurred_at")
        trace_id = native_event.get("trace_id")
        payload = native_event.get("payload", {})
        version = native_event.get("aggregate_version", 1)

        events: list[ProjectionEvent] = []

        if event_type in ("TicketCreated", "TicketUpdated"):
            ticket_id = payload.get("ticket_id")
            if ticket_id:
                ticket_payload = {
                    "ticket_id": ticket_id,
                    "tenant_id": tenant_id,
                    "collection_id": collection_id,
                    "upload_id": payload.get("upload_id"),
                    "source_file_id": payload.get("source_file_id"),
                    "parse_snapshot_id": payload.get("parse_snapshot_id"),
                    "doc_id": payload.get("doc_id"),
                    "title": payload.get("title"),
                    "filename": payload.get("filename"),
                    "state": payload.get("state", "pending"),
                    "priority": payload.get("priority"),
                    "routing_recommendation": payload.get("routing_recommendation"),
                    "assignee_user_id": payload.get("assignee_user_id"),
                    "agent_decision": payload.get("agent_decision"),
                    "agent_risk_level": payload.get("agent_risk_level"),
                    "agent_finding_count": payload.get("agent_finding_count", 0),
                    "agent_blocking_finding_count": payload.get("agent_blocking_finding_count", 0),
                }
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="ticket",
                    aggregate_id=ticket_id,
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload=ticket_payload,
                    trace_id=trace_id,
                ))

                # Also update task projection with ticket reference
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
                            "ticket_id": ticket_id,
                            "ticket_state": payload.get("state", "pending"),
                        },
                        trace_id=trace_id,
                    ))

        elif event_type == "TicketDecided":
            ticket_id = payload.get("ticket_id")
            if ticket_id:
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="ticket",
                    aggregate_id=ticket_id,
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "ticket_id": ticket_id,
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "state": payload.get("decision", "decided"),
                    },
                    trace_id=trace_id,
                ))

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
                            "ticket_state": payload.get("decision", "decided"),
                        },
                        trace_id=trace_id,
                    ))

        elif event_type == "AgentReviewCompleted":
            # Update ticket with agent review summary
            ticket_id = payload.get("ticket_id")
            if ticket_id:
                events.append(ProjectionEvent(
                    event_id=native_event["event_id"],
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="ticket",
                    aggregate_id=ticket_id,
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "ticket_id": ticket_id,
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "agent_decision": payload.get("agent_decision"),
                        "agent_risk_level": payload.get("agent_risk_level"),
                        "agent_finding_count": payload.get("finding_count", 0),
                        "agent_blocking_finding_count": payload.get("blocking_finding_count", 0),
                    },
                    trace_id=trace_id,
                ))

            # Create agent_review projection entries for each finding
            findings = payload.get("findings", [])
            for idx, finding in enumerate(findings):
                events.append(ProjectionEvent(
                    event_id=f"{native_event['event_id']}:finding:{idx}",
                    event_type=event_type,
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="agent_review",
                    aggregate_id=finding["finding_id"],
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "finding_id": finding["finding_id"],
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "ticket_id": ticket_id,
                        "doc_id": finding.get("doc_id"),
                        "source_file_id": finding.get("source_file_id"),
                        "parse_snapshot_id": finding.get("parse_snapshot_id"),
                        "evidence_id": finding.get("evidence_id"),
                        "severity": finding.get("severity"),
                        "category": finding.get("category"),
                        "problem_summary": finding.get("problem_summary"),
                        "problem_detail": finding.get("problem_detail"),
                        "source_quote": finding.get("source_quote"),
                        "chunk_quote": finding.get("chunk_quote"),
                        "page_from": finding.get("page_from"),
                        "page_to": finding.get("page_to"),
                        "source_anchor_json": finding.get("source_anchor_json"),
                        "why_wrong": finding.get("why_wrong"),
                        "suggested_fix": finding.get("suggested_fix"),
                        "suggested_operation": finding.get("suggested_operation"),
                        "confidence": finding.get("confidence"),
                        "state": finding.get("state", "open"),
                    },
                    trace_id=trace_id,
                ))

        return events
