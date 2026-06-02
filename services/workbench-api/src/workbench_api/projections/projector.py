"""Idempotent projection projector.

record_event -> event log (idempotent by event_id)
apply_event -> projection table update (version ordered)
record_and_apply -> both in one SQL transaction
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .repository import (
    AgentReviewProjectionRepository,
    ChunkProjectionRepository,
    DocumentProjectionRepository,
    ProjectionEventRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectionProjector:
    """Projector that records events and applies them to projection tables.

    - Duplicate event_id is ignored entirely.
    - Older aggregate_version must not overwrite newer projection state.
    - Event recording and projection update happen in one SQL transaction.
    """

    def __init__(self, session: Session):
        self._session = session
        self._event_repo = ProjectionEventRepository(session)
        self._task_repo = TaskProjectionRepository(session)
        self._ticket_repo = TicketProjectionRepository(session)
        self._document_repo = DocumentProjectionRepository(session)
        self._agent_review_repo = AgentReviewProjectionRepository(session)
        self._chunk_repo = ChunkProjectionRepository(session)

    def record_and_apply(self, event: dict[str, Any]) -> dict:
        """Record event and apply to projection in one transaction.

        Returns {"applied": bool, "event_recorded": bool, "reason": str}
        """
        event_recorded = self._event_repo.insert(event)
        if not event_recorded:
            return {"applied": False, "event_recorded": False, "reason": "duplicate_event_id"}

        applied = self.apply_event(event)
        return {
            "applied": applied,
            "event_recorded": True,
            "reason": "ok" if applied else "version_skipped_or_noop",
        }

    def apply_event(self, event: dict[str, Any]) -> bool:
        """Apply a single event to its target projection table.

        Returns True if projection was updated.
        """
        aggregate_type = event.get("aggregate_type")
        event_type = event.get("event_type")
        payload = event.get("payload", {})
        version = event.get("aggregate_version", 1)

        if aggregate_type == "task":
            return self._apply_task_event(event_type, payload, version)
        if aggregate_type == "ticket":
            return self._apply_ticket_event(event_type, payload, version)
        if aggregate_type == "document":
            return self._apply_document_event(event_type, payload, version)
        if aggregate_type == "agent_review":
            return self._apply_agent_review_event(event_type, payload, version)
        if aggregate_type == "chunk":
            return self._apply_chunk_event(event_type, payload, version)
        return False

    def _apply_task_event(self, event_type: str, payload: dict, version: int) -> bool:
        row = self._build_task_row(payload, version)
        return self._task_repo.upsert_with_version_check(row)

    def _apply_ticket_event(self, event_type: str, payload: dict, version: int) -> bool:
        row = self._build_ticket_row(payload, version)
        return self._ticket_repo.upsert_with_version_check(row)

    def _apply_document_event(self, event_type: str, payload: dict, version: int) -> bool:
        row = self._build_document_row(payload, version)
        return self._document_repo.upsert_with_version_check(row)

    def _apply_agent_review_event(self, event_type: str, payload: dict, version: int) -> bool:
        row = self._build_agent_review_row(payload, version)
        return self._agent_review_repo.upsert_with_version_check(row)

    def _apply_chunk_event(self, event_type: str, payload: dict, version: int) -> bool:
        row = self._build_chunk_row(payload, version)
        return self._chunk_repo.upsert_with_version_check(row)

    @staticmethod
    def _build_task_row(payload: dict, version: int) -> dict:
        now = _utcnow()
        return {
            "projection_id": payload.get("projection_id", payload.get("upload_id", "")),
            "tenant_id": payload["tenant_id"],
            "user_id": payload.get("user_id", ""),
            "collection_id": payload["collection_id"],
            "upload_id": payload.get("upload_id", ""),
            "filename": payload.get("filename", ""),
            "mime_type": payload.get("mime_type", ""),
            "size_bytes": payload.get("size_bytes", 0),
            "source_file_id": payload.get("source_file_id"),
            "intake_job_id": payload.get("intake_job_id"),
            "parse_snapshot_id": payload.get("parse_snapshot_id"),
            "ticket_id": payload.get("ticket_id"),
            "published_doc_id": payload.get("published_doc_id"),
            "doc_id": payload.get("doc_id"),
            "source_file_state": payload.get("source_file_state"),
            "intake_job_state": payload.get("intake_job_state"),
            "parse_snapshot_state": payload.get("parse_snapshot_state"),
            "ticket_state": payload.get("ticket_state"),
            "agent_review_state": payload.get("agent_review_state"),
            "published_document_state": payload.get("published_document_state"),
            "index_build_state": payload.get("index_build_state"),
            "active_index_version": payload.get("active_index_version"),
            "overall_status": payload.get("overall_status", "uploading"),
            "progress_pct": payload.get("progress_pct", 0),
            "blocking_reason": payload.get("blocking_reason"),
            "error_code": payload.get("error_code"),
            "error_message": payload.get("error_message"),
            "last_event_at": now,
            "projection_updated_at": now,
            "is_stale": payload.get("is_stale", False),
            "degraded_reason": payload.get("degraded_reason"),
            "version": version,
        }

    @staticmethod
    def _build_ticket_row(payload: dict, version: int) -> dict:
        now = _utcnow()
        return {
            "ticket_id": payload["ticket_id"],
            "tenant_id": payload["tenant_id"],
            "collection_id": payload["collection_id"],
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
            "updated_at": now,
            "last_event_at": now,
            "projection_updated_at": now,
            "is_stale": payload.get("is_stale", False),
            "degraded_reason": payload.get("degraded_reason"),
            "version": version,
        }

    @staticmethod
    def _build_document_row(payload: dict, version: int) -> dict:
        now = _utcnow()
        return {
            "doc_id": payload["doc_id"],
            "tenant_id": payload["tenant_id"],
            "collection_id": payload["collection_id"],
            "source_file_id": payload.get("source_file_id"),
            "parse_snapshot_id": payload.get("parse_snapshot_id"),
            "published_doc_id": payload.get("published_doc_id"),
            "upload_id": payload.get("upload_id"),
            "filename": payload.get("filename"),
            "mime_type": payload.get("mime_type"),
            "document_state": payload.get("document_state"),
            "publish_state": payload.get("publish_state"),
            "active_index_version": payload.get("active_index_version"),
            "chunk_count": payload.get("chunk_count", 0),
            "page_count": payload.get("page_count", 0),
            "parser_profile_id": payload.get("parser_profile_id"),
            "parser_profile_name": payload.get("parser_profile_name"),
            "updated_at": now,
            "projection_updated_at": now,
            "is_stale": payload.get("is_stale", False),
            "degraded_reason": payload.get("degraded_reason"),
            "version": version,
        }

    @staticmethod
    def _build_agent_review_row(payload: dict, version: int) -> dict:
        now = _utcnow()
        return {
            "finding_id": payload["finding_id"],
            "tenant_id": payload["tenant_id"],
            "collection_id": payload["collection_id"],
            "ticket_id": payload["ticket_id"],
            "doc_id": payload.get("doc_id"),
            "source_file_id": payload.get("source_file_id"),
            "parse_snapshot_id": payload.get("parse_snapshot_id"),
            "evidence_id": payload.get("evidence_id"),
            "severity": payload.get("severity"),
            "category": payload.get("category"),
            "problem_summary": payload.get("problem_summary"),
            "problem_detail": payload.get("problem_detail"),
            "source_quote": payload.get("source_quote"),
            "chunk_quote": payload.get("chunk_quote"),
            "page_from": payload.get("page_from"),
            "page_to": payload.get("page_to"),
            "source_anchor_json": payload.get("source_anchor_json"),
            "why_wrong": payload.get("why_wrong"),
            "suggested_fix": payload.get("suggested_fix"),
            "suggested_operation": payload.get("suggested_operation"),
            "confidence": payload.get("confidence"),
            "state": payload.get("state", "open"),
            "projection_updated_at": now,
            "version": version,
        }

    @staticmethod
    def _build_chunk_row(payload: dict, version: int) -> dict:
        now = _utcnow()
        return {
            "evidence_id": payload["evidence_id"],
            "tenant_id": payload["tenant_id"],
            "collection_id": payload["collection_id"],
            "doc_id": payload["doc_id"],
            "source_file_id": payload.get("source_file_id"),
            "parse_snapshot_id": payload.get("parse_snapshot_id"),
            "chunk_ordinal": payload.get("chunk_ordinal", 0),
            "content_preview": payload.get("content_preview"),
            "section_path_json": payload.get("section_path_json"),
            "page_from": payload.get("page_from"),
            "page_to": payload.get("page_to"),
            "source_anchor_json": payload.get("source_anchor_json"),
            "state": payload.get("state", "active"),
            "active_revision_id": payload.get("active_revision_id"),
            "projection_updated_at": now,
            "version": version,
        }
