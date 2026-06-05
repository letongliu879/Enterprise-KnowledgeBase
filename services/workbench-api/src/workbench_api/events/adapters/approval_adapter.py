"""Approval service event adapter.

Maps approval owner events into workbench ticket and agent-review projections.
Approval outbox delivery uses the canonical cross-service EventType names.
"""

from __future__ import annotations

from typing import Any

from .base import EventAdapter
from .. import ProjectionEvent


class ApprovalEventAdapter(EventAdapter):
    """Adapter for approval service events."""

    @property
    def service_name(self) -> str:
        return "approval"

    def adapt(self, native_event: dict[str, Any]) -> list["ProjectionEvent"]:
        event_type = str(native_event.get("event_type") or "")
        payload = self._payload(native_event)
        tenant_id = str(native_event.get("tenant_id") or payload.get("tenant_id") or "")
        collection_id = native_event.get("collection_id") or payload.get("collection_id")
        occurred_at = native_event.get("occurred_at")
        trace_id = native_event.get("trace_id")
        version = self._version(native_event, payload)

        events: list["ProjectionEvent"] = []

        if event_type in {"TicketCreated", "TicketUpdated", "ApprovalPending", "ApprovalDecided"}:
            ticket_event = self._ticket_projection_event(
                native_event=native_event,
                event_type=event_type,
                payload=payload,
                tenant_id=tenant_id,
                collection_id=collection_id,
                occurred_at=occurred_at,
                trace_id=trace_id,
                version=version,
            )
            if ticket_event is not None:
                events.append(ticket_event)

            task_event = self._task_projection_event(
                native_event=native_event,
                event_type=event_type,
                payload=payload,
                tenant_id=tenant_id,
                collection_id=collection_id,
                occurred_at=occurred_at,
                trace_id=trace_id,
                version=version,
            )
            if task_event is not None:
                events.append(task_event)

        if event_type in {"AgentReviewCompleted", "ApprovalPending", "ApprovalDecided"}:
            events.extend(
                self._agent_review_events(
                    native_event=native_event,
                    payload=payload,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    occurred_at=occurred_at,
                    trace_id=trace_id,
                    version=version,
                )
            )

        return events

    @staticmethod
    def _payload(native_event: dict[str, Any]) -> dict[str, Any]:
        payload = native_event.get("payload")
        if isinstance(payload, dict):
            return payload
        payload_json = native_event.get("payload_json")
        if isinstance(payload_json, dict):
            return payload_json
        return {}

    @staticmethod
    def _version(native_event: dict[str, Any], payload: dict[str, Any]) -> int:
        raw = native_event.get("aggregate_version") or payload.get("ticket_event_version") or 1
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 1

    def _ticket_projection_event(
        self,
        *,
        native_event: dict[str, Any],
        event_type: str,
        payload: dict[str, Any],
        tenant_id: str,
        collection_id: str | None,
        occurred_at: Any,
        trace_id: str | None,
        version: int,
    ) -> ProjectionEvent | None:
        ticket_id = payload.get("ticket_id")
        if not ticket_id:
            return None

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
            "state": payload.get("state", self._default_state(event_type, payload)),
            "priority": payload.get("priority"),
            "routing_recommendation": payload.get("routing_recommendation"),
            "assignee_user_id": payload.get("assignee_user_id"),
            "agent_decision": payload.get("agent_decision"),
            "agent_risk_level": payload.get("agent_risk_level"),
            "agent_finding_count": payload.get("agent_finding_count", payload.get("finding_count", 0)),
            "agent_blocking_finding_count": payload.get(
                "agent_blocking_finding_count",
                payload.get("blocking_finding_count", 0),
            ),
        }
        return ProjectionEvent(
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
        )

    def _task_projection_event(
        self,
        *,
        native_event: dict[str, Any],
        event_type: str,
        payload: dict[str, Any],
        tenant_id: str,
        collection_id: str | None,
        occurred_at: Any,
        trace_id: str | None,
        version: int,
    ) -> ProjectionEvent | None:
        upload_id = payload.get("upload_id")
        ticket_id = payload.get("ticket_id")
        if not upload_id or not ticket_id:
            return None
        return ProjectionEvent(
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
                "tenant_id": tenant_id or "default",
                "collection_id": collection_id,
                "upload_id": upload_id,
                "ticket_id": ticket_id,
                "ticket_state": payload.get("state", self._default_state(event_type, payload)),
            },
            trace_id=trace_id,
        )

    def _agent_review_events(
        self,
        *,
        native_event: dict[str, Any],
        payload: dict[str, Any],
        tenant_id: str,
        collection_id: str | None,
        occurred_at: Any,
        trace_id: str | None,
        version: int,
    ) -> list["ProjectionEvent"]:
        ticket_id = payload.get("ticket_id")
        findings = payload.get("findings", [])
        if not ticket_id or not isinstance(findings, list):
            return []

        events: list["ProjectionEvent"] = []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            finding_id = str(finding.get("finding_id", "") or "")
            if not finding_id:
                continue
            events.append(
                ProjectionEvent(
                    event_id=f"{native_event['event_id']}:finding:{finding_id}",
                    event_type=native_event.get("event_type", "approval_event"),
                    service=self.service_name,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    aggregate_type="agent_review",
                    aggregate_id=finding_id,
                    aggregate_version=version,
                    occurred_at=occurred_at,
                    payload={
                        "finding_id": finding_id,
                        "tenant_id": tenant_id,
                        "collection_id": collection_id,
                        "ticket_id": ticket_id,
                        "doc_id": finding.get("doc_id"),
                        "source_file_id": finding.get("source_file_id", payload.get("source_file_id")),
                        "parse_snapshot_id": finding.get("parse_snapshot_id", payload.get("parse_snapshot_id")),
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
                )
            )
        return events

    @staticmethod
    def _default_state(event_type: str, payload: dict[str, Any]) -> str:
        if event_type == "ApprovalPending":
            return "pending"
        if event_type == "ApprovalDecided":
            decision = str(payload.get("decision", "") or "").lower()
            mapping = {
                "approve": "approved",
                "reject": "rejected",
                "return": "returned",
                "expire": "expired",
            }
            return mapping.get(decision, str(payload.get("state", "system_decided") or "system_decided"))
        return str(payload.get("state", "pending") or "pending")
