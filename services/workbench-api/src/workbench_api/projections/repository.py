"""Repositories for workbench SQL projection store."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from reality_rag_persistence.models import (
    WorkbenchAgentReviewProjectionModel,
    WorkbenchChunkProjectionModel,
    WorkbenchDocumentProjectionModel,
    WorkbenchProjectionEventModel,
    WorkbenchProjectionReconcileRunModel,
    WorkbenchQueryRunModel,
    WorkbenchTaskProjectionModel,
    WorkbenchTicketProjectionModel,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectionEventRepository:
    """Append-only projection event log with idempotency by event_id."""

    def __init__(self, session: Session):
        self._session = session

    def insert(self, event: dict[str, Any]) -> bool:
        """Insert event if event_id does not exist. Returns True if inserted."""
        existing = (
            self._session.query(WorkbenchProjectionEventModel)
            .filter_by(event_id=event["event_id"])
            .first()
        )
        if existing:
            return False
        model = WorkbenchProjectionEventModel(
            event_id=event["event_id"],
            event_type=event["event_type"],
            tenant_id=event["tenant_id"],
            collection_id=event["collection_id"],
            aggregate_type=event["aggregate_type"],
            aggregate_id=event["aggregate_id"],
            aggregate_version=event.get("aggregate_version", 1),
            occurred_at=event.get("occurred_at", _utcnow()),
            payload=event.get("payload", {}),
            trace_id=event.get("trace_id", ""),
        )
        self._session.add(model)
        return True

    def get_by_aggregate(self, aggregate_type: str, aggregate_id: str) -> list[WorkbenchProjectionEventModel]:
        return (
            self._session.query(WorkbenchProjectionEventModel)
            .filter_by(aggregate_type=aggregate_type, aggregate_id=aggregate_id)
            .order_by(WorkbenchProjectionEventModel.aggregate_version.asc())
            .all()
        )


class TaskProjectionRepository:
    """Repository for workbench_task_projection."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, projection_id: str) -> WorkbenchTaskProjectionModel | None:
        return self._session.query(WorkbenchTaskProjectionModel).filter_by(projection_id=projection_id).first()

    def get_by_upload_id(self, upload_id: str) -> WorkbenchTaskProjectionModel | None:
        return self._session.query(WorkbenchTaskProjectionModel).filter_by(upload_id=upload_id).first()

    def list(
        self,
        tenant_id: str,
        user_id: str | None = None,
        collection_id: str | None = None,
        status: str | None = None,
        is_stale: bool | None = None,
        offset: int = 0,
        limit: int = 50,
        order_by: str = "projection_updated_at",
        order_dir: str = "desc",
    ) -> tuple[list[WorkbenchTaskProjectionModel], int]:
        query = self._session.query(WorkbenchTaskProjectionModel).filter_by(tenant_id=tenant_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if collection_id:
            query = query.filter_by(collection_id=collection_id)
        if status:
            query = query.filter_by(overall_status=status)
        if is_stale is not None:
            query = query.filter_by(is_stale=is_stale)

        total = query.count()
        order_col = getattr(WorkbenchTaskProjectionModel, order_by, WorkbenchTaskProjectionModel.projection_updated_at)
        order = desc(order_col) if order_dir == "desc" else asc(order_col)
        items = query.order_by(order).offset(offset).limit(limit).all()
        return items, total

    def upsert_with_version_check(self, row: dict[str, Any]) -> bool:
        """Upsert task projection, but only if new version > existing version.

        Skips None and empty-string values so event-driven partial updates
        don't wipe fields set by earlier events (e.g. user_id, source_file_state).
        """
        projection_id = row.get("projection_id")
        existing = self.get(projection_id) if projection_id else None
        if existing is None:
            model = WorkbenchTaskProjectionModel(**row)
            self._session.add(model)
            return True
        new_version = row.get("version", 1)
        if new_version <= existing.version:
            return False
        for key, value in row.items():
            if hasattr(existing, key):
                if value in (None, "") and getattr(existing, key) not in (None, ""):
                    continue
                setattr(existing, key, value)
        existing.projection_updated_at = _utcnow()
        return True

    def mark_stale(self, projection_id: str, reason: str) -> None:
        model = self.get(projection_id)
        if model:
            model.is_stale = True
            model.degraded_reason = reason
            model.projection_updated_at = _utcnow()


class TicketProjectionRepository:
    """Repository for workbench_ticket_projection."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, ticket_id: str) -> WorkbenchTicketProjectionModel | None:
        return self._session.query(WorkbenchTicketProjectionModel).filter_by(ticket_id=ticket_id).first()

    def list(
        self,
        tenant_id: str,
        collection_ids: list[str] | None = None,
        state: str | None = None,
        offset: int = 0,
        limit: int = 50,
        order_by: str = "projection_updated_at",
        order_dir: str = "desc",
    ) -> tuple[list[WorkbenchTicketProjectionModel], int]:
        query = self._session.query(WorkbenchTicketProjectionModel).filter_by(tenant_id=tenant_id)
        if collection_ids:
            query = query.filter(WorkbenchTicketProjectionModel.collection_id.in_(collection_ids))
        if state:
            query = query.filter_by(state=state)
        total = query.count()
        order_col = getattr(WorkbenchTicketProjectionModel, order_by, WorkbenchTicketProjectionModel.projection_updated_at)
        order = desc(order_col) if order_dir == "desc" else asc(order_col)
        items = query.order_by(order).offset(offset).limit(limit).all()
        return items, total

    def upsert_with_version_check(self, row: dict[str, Any]) -> bool:
        ticket_id = row.get("ticket_id")
        existing = self.get(ticket_id) if ticket_id else None
        if existing is None:
            model = WorkbenchTicketProjectionModel(**row)
            self._session.add(model)
            return True
        new_version = row.get("version", 1)
        if new_version <= existing.version:
            return False
        for key, value in row.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.projection_updated_at = _utcnow()
        return True

    def mark_stale(self, ticket_id: str, reason: str) -> None:
        model = self.get(ticket_id)
        if model:
            model.is_stale = True
            model.degraded_reason = reason
            model.projection_updated_at = _utcnow()


class DocumentProjectionRepository:
    """Repository for workbench_document_projection."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, doc_id: str) -> WorkbenchDocumentProjectionModel | None:
        return self._session.query(WorkbenchDocumentProjectionModel).filter_by(doc_id=doc_id).first()

    def list(
        self,
        tenant_id: str,
        collection_ids: list[str] | None = None,
        document_state: str | None = None,
        offset: int = 0,
        limit: int = 50,
        order_by: str = "projection_updated_at",
        order_dir: str = "desc",
    ) -> tuple[list[WorkbenchDocumentProjectionModel], int]:
        query = self._session.query(WorkbenchDocumentProjectionModel).filter_by(tenant_id=tenant_id)
        if collection_ids:
            query = query.filter(WorkbenchDocumentProjectionModel.collection_id.in_(collection_ids))
        if document_state:
            query = query.filter_by(document_state=document_state)
        total = query.count()
        order_col = getattr(WorkbenchDocumentProjectionModel, order_by, WorkbenchDocumentProjectionModel.projection_updated_at)
        order = desc(order_col) if order_dir == "desc" else asc(order_col)
        items = query.order_by(order).offset(offset).limit(limit).all()
        return items, total

    def upsert_with_version_check(self, row: dict[str, Any]) -> bool:
        doc_id = row.get("doc_id")
        existing = self.get(doc_id) if doc_id else None
        if existing is None:
            model = WorkbenchDocumentProjectionModel(**row)
            self._session.add(model)
            return True
        new_version = row.get("version", 1)
        if new_version <= existing.version:
            return False
        for key, value in row.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.projection_updated_at = _utcnow()
        return True

    def mark_stale(self, doc_id: str, reason: str) -> None:
        model = self.get(doc_id)
        if model:
            model.is_stale = True
            model.degraded_reason = reason
            model.projection_updated_at = _utcnow()


class AgentReviewProjectionRepository:
    """Repository for workbench_agent_review_projection."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, finding_id: str) -> WorkbenchAgentReviewProjectionModel | None:
        return self._session.query(WorkbenchAgentReviewProjectionModel).filter_by(finding_id=finding_id).first()

    def list_by_ticket(self, ticket_id: str, tenant_id: str) -> list[WorkbenchAgentReviewProjectionModel]:
        return (
            self._session.query(WorkbenchAgentReviewProjectionModel)
            .filter_by(ticket_id=ticket_id, tenant_id=tenant_id)
            .order_by(
                WorkbenchAgentReviewProjectionModel.severity.asc(),
                WorkbenchAgentReviewProjectionModel.confidence.desc(),
            )
            .all()
        )

    def list_unmatched(self, limit: int = 100) -> list[WorkbenchAgentReviewProjectionModel]:
        return (
            self._session.query(WorkbenchAgentReviewProjectionModel)
            .filter(WorkbenchAgentReviewProjectionModel.evidence_id.is_(None))
            .filter(WorkbenchAgentReviewProjectionModel.parse_snapshot_id.is_not(None))
            .filter(WorkbenchAgentReviewProjectionModel.source_quote.is_not(None))
            .order_by(WorkbenchAgentReviewProjectionModel.projection_updated_at.asc())
            .limit(limit)
            .all()
        )

    def upsert_with_version_check(self, row: dict[str, Any]) -> bool:
        finding_id = row.get("finding_id")
        existing = self.get(finding_id) if finding_id else None
        if existing is None:
            model = WorkbenchAgentReviewProjectionModel(**row)
            self._session.add(model)
            return True
        new_version = row.get("version", 1)
        if new_version <= existing.version:
            return False
        for key, value in row.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.projection_updated_at = _utcnow()
        return True

    def update_match_with_version_check(
        self,
        finding_id: str,
        *,
        expected_version: int,
        evidence_id: str,
        page_from: int | None,
        page_to: int | None,
        chunk_quote: str | None,
        source_anchor_json: dict[str, Any] | None,
    ) -> bool:
        existing = self.get(finding_id)
        if existing is None or existing.version != expected_version:
            return False
        existing.evidence_id = evidence_id
        existing.page_from = page_from
        existing.page_to = page_to
        existing.chunk_quote = chunk_quote
        existing.source_anchor_json = source_anchor_json
        existing.version = expected_version + 1
        existing.projection_updated_at = _utcnow()
        return True


class ChunkProjectionRepository:
    """Repository for workbench_chunk_projection."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, evidence_id: str) -> WorkbenchChunkProjectionModel | None:
        return self._session.query(WorkbenchChunkProjectionModel).filter_by(evidence_id=evidence_id).first()

    def list_by_doc(
        self,
        doc_id: str,
        tenant_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[WorkbenchChunkProjectionModel], int]:
        query = self._session.query(WorkbenchChunkProjectionModel).filter_by(doc_id=doc_id, tenant_id=tenant_id)
        total = query.count()
        items = query.order_by(WorkbenchChunkProjectionModel.chunk_ordinal.asc()).offset(offset).limit(limit).all()
        return items, total

    def upsert_with_version_check(self, row: dict[str, Any]) -> bool:
        evidence_id = row.get("evidence_id")
        existing = self.get(evidence_id) if evidence_id else None
        if existing is None:
            model = WorkbenchChunkProjectionModel(**row)
            self._session.add(model)
            return True
        new_version = row.get("version", 1)
        if new_version <= existing.version:
            return False
        for key, value in row.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.projection_updated_at = _utcnow()
        return True

    def mark_stale(self, evidence_id: str, reason: str) -> None:
        model = self.get(evidence_id)
        if model:
            model.is_stale = True
            model.degraded_reason = reason
            model.projection_updated_at = _utcnow()


class QueryRunRepository:
    """Repository for workbench_query_runs."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, row: dict[str, Any]) -> WorkbenchQueryRunModel:
        model = WorkbenchQueryRunModel(**row)
        self._session.add(model)
        return model

    def update(self, query_run_id: str, updates: dict[str, Any]) -> None:
        model = self.get(query_run_id)
        if model:
            for key, value in updates.items():
                if hasattr(model, key):
                    setattr(model, key, value)

    def get(self, query_run_id: str) -> WorkbenchQueryRunModel | None:
        return self._session.query(WorkbenchQueryRunModel).filter_by(query_run_id=query_run_id).first()

    def list(
        self,
        tenant_id: str,
        user_id: str | None = None,
        collection_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[WorkbenchQueryRunModel], int]:
        query = self._session.query(WorkbenchQueryRunModel).filter_by(tenant_id=tenant_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if collection_id:
            query = query.filter_by(collection_id=collection_id)
        total = query.count()
        items = (
            query.order_by(desc(WorkbenchQueryRunModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total


class ReconcileRunRepository:
    """Repository for workbench_projection_reconcile_runs."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, row: dict[str, Any]) -> WorkbenchProjectionReconcileRunModel:
        model = WorkbenchProjectionReconcileRunModel(**row)
        self._session.add(model)
        return model

    def get(self, run_id: str) -> WorkbenchProjectionReconcileRunModel | None:
        return self._session.query(WorkbenchProjectionReconcileRunModel).filter_by(run_id=run_id).first()

    def update(self, run_id: str, updates: dict[str, Any]) -> None:
        model = self.get(run_id)
        if model:
            for key, value in updates.items():
                if hasattr(model, key):
                    setattr(model, key, value)
