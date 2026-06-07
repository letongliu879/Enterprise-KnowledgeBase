"""Projection reconciler — scans stale projections and re-fetches from owner services.

Reconciliation is a backfill/repair mechanism, not the primary update path.
It runs periodically and repairs projections that missed events or fell stale.

Uses database row-level locks (FOR UPDATE SKIP LOCKED) for safe multi-instance
concurrency, and cursor-based pagination to avoid full table scans.
"""

from __future__ import annotations

import difflib
import re
import uuid
from datetime import datetime, timezone
from mimetypes import guess_type
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from reality_rag_persistence.models import (
    ChunkRegistryModel,
    DocumentModel,
    IndexedDocumentModel,
    IntakeJobModel,
    ParseSnapshotModel,
    PublishedDocumentModel,
    SourceFileModel,
    WorkbenchDocumentProjectionModel,
)

from ..downstream_clients import ApprovalClient, IndexingClient, IntakeClient
from ..downstream_clients.errors import DownstreamError
from .projector import ProjectionProjector
from .repository import (
    AgentReviewProjectionRepository,
    ReconcileRunRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectionReconciler:
    """Reconciles stale projection rows by querying owner services."""

    def __init__(
        self,
        session: Session,
        intake_client: IntakeClient,
        approval_client: ApprovalClient,
        indexing_client: IndexingClient,
    ):
        self._session = session
        self._intake_client = intake_client
        self._approval_client = approval_client
        self._indexing_client = indexing_client
        self._task_repo = TaskProjectionRepository(session)
        self._ticket_repo = TicketProjectionRepository(session)
        self._agent_review_repo = AgentReviewProjectionRepository(session)
        self._reconcile_repo = ReconcileRunRepository(session)
        self._projector = ProjectionProjector(session)

    async def reconcile_tasks(self, tenant_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Scan stale task projections with row-level locks and recompute from owner states."""
        run_id = f"rec_{uuid.uuid4().hex[:16]}"
        self._reconcile_repo.create({
            "run_id": run_id,
            "tenant_id": tenant_id,
            "aggregate_type": "task",
            "started_at": _utcnow(),
            "status": "running",
            "trace_id": run_id,
        })

        # Build SQL safely — only string literals are concatenated, never user input
        dialect = self._session.bind.dialect.name if self._session.bind else ""
        parts = [
            "SELECT projection_id, tenant_id, collection_id, upload_id, version",
            "FROM workbench_task_projection",
            "WHERE is_stale = true",
        ]
        if tenant_id:
            parts.append("AND tenant_id = :tenant_id")
        parts.extend([
            "ORDER BY stale_after ASC NULLS LAST, projection_updated_at ASC",
            "LIMIT :limit",
        ])
        if dialect != "sqlite":
            parts.append("FOR UPDATE SKIP LOCKED")
        sql = text(" ".join(parts))

        params = {"limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id

        scanned = 0
        updated = 0
        failed = 0
        degraded = 0

        rows = self._session.execute(sql, params).mappings().all()
        for row in rows:
            scanned += 1
            try:
                # Re-fetch the full row inside the transaction (it's locked)
                from reality_rag_persistence.models import WorkbenchTaskProjectionModel
                full_row = self._session.query(WorkbenchTaskProjectionModel).filter_by(
                    projection_id=row["projection_id"]
                ).first()
                if not full_row:
                    continue

                event_payload = await self._rebuild_task_payload(full_row)
                event = {
                    "event_id": f"rec_ev_{uuid.uuid4().hex[:16]}",
                    "event_type": "RECONCILE_TASK",
                    "tenant_id": full_row.tenant_id,
                    "collection_id": full_row.collection_id,
                    "aggregate_type": "task",
                    "aggregate_id": full_row.upload_id,
                    "aggregate_version": full_row.version + 1,
                    "occurred_at": _utcnow(),
                    "payload": event_payload,
                    "trace_id": run_id,
                }
                result = self._projector.record_and_apply(event)
                if result["applied"]:
                    updated += 1
                else:
                    degraded += 1
            except Exception:
                failed += 1

        self._reconcile_repo.update(run_id, {
            "completed_at": _utcnow(),
            "scanned_count": scanned,
            "updated_count": updated,
            "failed_count": failed,
            "degraded_count": degraded,
            "status": "completed",
        })

        return {
            "run_id": run_id,
            "scanned": scanned,
            "updated": updated,
            "failed": failed,
            "degraded": degraded,
        }

    async def reconcile_tickets(self, tenant_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Scan stale ticket projections with row-level locks and recompute from approval."""
        run_id = f"rec_{uuid.uuid4().hex[:16]}"
        self._reconcile_repo.create({
            "run_id": run_id,
            "tenant_id": tenant_id,
            "aggregate_type": "ticket",
            "started_at": _utcnow(),
            "status": "running",
            "trace_id": run_id,
        })
        dialect = self._session.bind.dialect.name if self._session.bind else ""

        parts = [
            "SELECT ticket_id, tenant_id, collection_id, version",
            "FROM workbench_ticket_projection",
            "WHERE is_stale = true",
        ]
        if tenant_id:
            parts.append("AND tenant_id = :tenant_id")
        parts.extend([
            "ORDER BY projection_updated_at ASC",
            "LIMIT :limit",
        ])
        if dialect != "sqlite":
            parts.append("FOR UPDATE SKIP LOCKED")
        sql = text(" ".join(parts))

        params = {"limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id

        scanned = 0
        updated = 0
        failed = 0
        degraded = 0

        rows = self._session.execute(sql, params).mappings().all()
        for row in rows:
            scanned += 1
            try:
                ticket_raw = await self._approval_client.get_ticket(row["ticket_id"])
                event = {
                    "event_id": f"rec_ev_{uuid.uuid4().hex[:16]}",
                    "event_type": "RECONCILE_TICKET",
                    "tenant_id": row["tenant_id"],
                    "collection_id": row["collection_id"],
                    "aggregate_type": "ticket",
                    "aggregate_id": row["ticket_id"],
                    "aggregate_version": row["version"] + 1,
                    "occurred_at": _utcnow(),
                    "payload": self._ticket_raw_to_payload(ticket_raw),
                    "trace_id": run_id,
                }
                result = self._projector.record_and_apply(event)
                if result["applied"]:
                    updated += 1
                else:
                    degraded += 1
            except DownstreamError:
                failed += 1
            except Exception:
                failed += 1

        self._reconcile_repo.update(run_id, {
            "completed_at": _utcnow(),
            "scanned_count": scanned,
            "updated_count": updated,
            "failed_count": failed,
            "degraded_count": degraded,
            "status": "completed",
        })

        return {
            "run_id": run_id,
            "scanned": scanned,
            "updated": updated,
            "failed": failed,
            "degraded": degraded,
        }

    async def reconcile_documents(self, tenant_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Rebuild incomplete document projections from local owner tables."""
        run_id = f"rec_{uuid.uuid4().hex[:16]}"
        self._reconcile_repo.create({
            "run_id": run_id,
            "tenant_id": tenant_id,
            "aggregate_type": "document",
            "started_at": _utcnow(),
            "status": "running",
            "trace_id": run_id,
        })
        dialect = self._session.bind.dialect.name if self._session.bind else ""

        query = self._session.query(WorkbenchDocumentProjectionModel).filter(
            or_(
                WorkbenchDocumentProjectionModel.is_stale.is_(True),
                WorkbenchDocumentProjectionModel.source_file_id.is_(None),
                WorkbenchDocumentProjectionModel.parse_snapshot_id.is_(None),
                WorkbenchDocumentProjectionModel.filename.is_(None),
                WorkbenchDocumentProjectionModel.active_index_version.is_(None),
                WorkbenchDocumentProjectionModel.chunk_count == 0,
                WorkbenchDocumentProjectionModel.page_count == 0,
            )
        )
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        query = query.order_by(WorkbenchDocumentProjectionModel.projection_updated_at.asc()).limit(limit)
        if dialect != "sqlite":
            query = query.with_for_update(skip_locked=True)

        scanned = 0
        updated = 0
        failed = 0
        degraded = 0

        for row in query.all():
            scanned += 1
            try:
                event = {
                    "event_id": f"rec_ev_{uuid.uuid4().hex[:16]}",
                    "event_type": "RECONCILE_DOCUMENT",
                    "tenant_id": row.tenant_id,
                    "collection_id": row.collection_id,
                    "aggregate_type": "document",
                    "aggregate_id": row.doc_id,
                    "aggregate_version": row.version + 1,
                    "occurred_at": _utcnow(),
                    "payload": self._rebuild_document_payload(row),
                    "trace_id": run_id,
                }
                result = self._projector.record_and_apply(event)
                if result["applied"]:
                    updated += 1
                else:
                    degraded += 1
            except Exception:
                failed += 1

        self._reconcile_repo.update(run_id, {
            "completed_at": _utcnow(),
            "scanned_count": scanned,
            "updated_count": updated,
            "failed_count": failed,
            "degraded_count": degraded,
            "status": "completed",
        })

        return {
            "run_id": run_id,
            "scanned": scanned,
            "updated": updated,
            "failed": failed,
            "degraded": degraded,
        }

    async def reconcile_chunks(self, tenant_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Scan stale chunk projections with row-level locks."""
        run_id = f"rec_{uuid.uuid4().hex[:16]}"
        self._reconcile_repo.create({
            "run_id": run_id,
            "tenant_id": tenant_id,
            "aggregate_type": "chunk",
            "started_at": _utcnow(),
            "status": "running",
            "trace_id": run_id,
        })
        dialect = self._session.bind.dialect.name if self._session.bind else ""

        parts = [
            "SELECT evidence_id, tenant_id, collection_id, version",
            "FROM workbench_chunk_projection",
            "WHERE is_stale = true",
        ]
        if tenant_id:
            parts.append("AND tenant_id = :tenant_id")
        parts.extend([
            "ORDER BY projection_updated_at ASC",
            "LIMIT :limit",
        ])
        if dialect != "sqlite":
            parts.append("FOR UPDATE SKIP LOCKED")
        sql = text(" ".join(parts))

        params = {"limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id

        scanned = len(self._session.execute(sql, params).mappings().all())
        self._reconcile_repo.update(run_id, {
            "completed_at": _utcnow(),
            "scanned_count": scanned,
            "updated_count": 0,
            "failed_count": 0,
            "degraded_count": 0,
            "status": "completed",
        })

        return {"run_id": run_id, "scanned": scanned, "updated": 0, "failed": 0, "degraded": 0}

    async def reconcile_agent_reviews(self, tenant_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        """Match unmatched agent-review findings back to parse-snapshot chunks."""
        run_id = f"rec_{uuid.uuid4().hex[:16]}"
        self._reconcile_repo.create({
            "run_id": run_id,
            "tenant_id": tenant_id,
            "aggregate_type": "agent_review",
            "started_at": _utcnow(),
            "status": "running",
            "trace_id": run_id,
        })

        scanned = 0
        updated = 0
        failed = 0
        degraded = 0

        if self._session.bind is not None and self._session.bind.dialect.name == "sqlite":
            rows = [
                {"finding_id": finding.finding_id}
                for finding in self._agent_review_repo.list_unmatched(limit=limit)
                if not tenant_id or finding.tenant_id == tenant_id
            ]
        else:
            parts = [
                "SELECT finding_id, tenant_id, version",
                "FROM workbench_agent_review_projection",
                "WHERE evidence_id IS NULL",
                "AND parse_snapshot_id IS NOT NULL",
                "AND source_quote IS NOT NULL",
            ]
            if tenant_id:
                parts.append("AND tenant_id = :tenant_id")
            parts.extend([
                "ORDER BY projection_updated_at ASC",
                "LIMIT :limit",
                "FOR UPDATE SKIP LOCKED",
            ])
            sql = text(" ".join(parts))
            params = {"limit": limit}
            if tenant_id:
                params["tenant_id"] = tenant_id
            rows = self._session.execute(sql, params).mappings().all()
        for row in rows:
            from reality_rag_persistence.models import WorkbenchAgentReviewProjectionModel

            finding = self._session.query(WorkbenchAgentReviewProjectionModel).filter_by(
                finding_id=row["finding_id"]
            ).first()
            if finding is None:
                continue
            scanned += 1
            try:
                chunks = await self._fetch_all_snapshot_chunks(str(finding.parse_snapshot_id or ""))
                match = _best_chunk_match(str(finding.source_quote or ""), chunks)
                if match is None:
                    degraded += 1
                    continue
                ok = self._agent_review_repo.update_match_with_version_check(
                    finding.finding_id,
                    expected_version=finding.version,
                    evidence_id=str(match["evidence_id"]),
                    page_from=match.get("page_from"),
                    page_to=match.get("page_to"),
                    chunk_quote=str(match.get("content", "") or ""),
                    source_anchor_json=_source_anchor_json(match),
                )
                if ok:
                    updated += 1
                else:
                    degraded += 1
            except DownstreamError:
                failed += 1
            except Exception:
                failed += 1

        self._reconcile_repo.update(run_id, {
            "completed_at": _utcnow(),
            "scanned_count": scanned,
            "updated_count": updated,
            "failed_count": failed,
            "degraded_count": degraded,
            "status": "completed",
        })
        return {
            "run_id": run_id,
            "scanned": scanned,
            "updated": updated,
            "failed": failed,
            "degraded": degraded,
        }

    async def _fetch_all_snapshot_chunks(self, parse_snapshot_id: str) -> list[dict[str, Any]]:
        if not parse_snapshot_id:
            return []
        page = 1
        page_size = 200
        items: list[dict[str, Any]] = []
        while True:
            result = await self._indexing_client.get_parse_snapshot_chunks(
                parse_snapshot_id,
                page=page,
                page_size=page_size,
            )
            if isinstance(result, list):
                batch = result
                total = len(batch)
            else:
                batch = list(result.get("items", []))
                total = int(result.get("total", len(batch)) or len(batch))
            items.extend(item for item in batch if isinstance(item, dict))
            if not batch or len(items) >= total:
                break
            page += 1
        return items

    async def _rebuild_task_payload(self, row: Any) -> dict[str, Any]:
        """Requery owner services and rebuild a task projection payload."""
        payload: dict[str, Any] = {
            "projection_id": row.upload_id,
            "tenant_id": row.tenant_id,
            "user_id": row.user_id,
            "collection_id": row.collection_id,
            "upload_id": row.upload_id,
            "filename": row.filename,
            "mime_type": row.mime_type,
            "size_bytes": row.size_bytes,
            "source_file_id": row.source_file_id,
            "intake_job_id": row.intake_job_id,
            "parse_snapshot_id": row.parse_snapshot_id,
            "ticket_id": row.ticket_id,
            "published_doc_id": row.published_doc_id,
            "doc_id": row.doc_id,
        }

        if row.source_file_id:
            try:
                sf = await self._intake_client.get_source_file(row.source_file_id)
                payload["source_file_state"] = sf.get("state")
                payload["intake_job_id"] = sf.get("intake_job_id") or row.intake_job_id
            except DownstreamError:
                payload["degraded_reason"] = "source_file_fetch_failed"
                return payload

        if payload.get("intake_job_id"):
            try:
                job = await self._intake_client.get_intake_job(payload["intake_job_id"])
                payload["intake_job_state"] = job.get("state")
                payload["parse_snapshot_id"] = job.get("parse_snapshot_id") or row.parse_snapshot_id
                payload["ticket_id"] = job.get("ticket_id") or row.ticket_id
                payload["doc_id"] = job.get("final_doc_id") or row.doc_id
                payload["published_doc_id"] = job.get("published_document_id") or row.published_doc_id

                if payload.get("parse_snapshot_id"):
                    payload["parse_snapshot_state"] = "PARSED"
                elif payload.get("intake_job_state") in ("CREATED", "PARSING"):
                    payload["parse_snapshot_state"] = "PARSING"
                elif payload.get("intake_job_state") == "FAILED":
                    payload["parse_snapshot_state"] = "FAILED"
                else:
                    payload["parse_snapshot_state"] = "CREATED"
            except DownstreamError:
                payload["degraded_reason"] = "intake_job_fetch_failed"
                return payload

        if payload.get("ticket_id"):
            try:
                ticket = await self._approval_client.get_ticket(payload["ticket_id"])
                payload["ticket_state"] = ticket.get("state")
            except DownstreamError:
                pass

        if payload.get("published_doc_id"):
            try:
                pd = await self._intake_client.get_published_document(payload["published_doc_id"])
                payload["published_document_state"] = pd.get("state")
            except DownstreamError:
                pass

        if payload.get("doc_id"):
            try:
                indexed_docs = await self._indexing_client.get_indexed_documents(
                    collection_id=row.collection_id,
                    final_doc_id=payload["doc_id"],
                )
                if indexed_docs:
                    active_doc = next((d for d in indexed_docs if d.get("state") == "ACTIVE"), None)
                    if active_doc:
                        payload["index_build_state"] = "ACTIVE"
                        payload["active_index_version"] = active_doc.get("index_version")
                    else:
                        candidate = next((d for d in indexed_docs if d.get("state") == "CANDIDATE"), None)
                        payload["index_build_state"] = "BUILDING" if candidate else indexed_docs[0].get("state")
            except DownstreamError:
                pass

        payload["overall_status"] = _derive_status(
            payload.get("source_file_state"),
            payload.get("intake_job_state"),
            payload.get("ticket_state"),
            payload.get("published_document_state"),
            payload.get("index_build_state"),
            payload.get("active_index_version"),
        )
        payload["progress_pct"] = _derive_progress(
            payload.get("source_file_state"),
            payload.get("intake_job_state"),
            payload.get("parse_snapshot_state"),
            payload.get("ticket_state"),
            payload.get("published_document_state"),
            payload.get("index_build_state"),
            payload.get("active_index_version"),
        )
        payload["is_stale"] = False
        payload["degraded_reason"] = None
        return payload

    def _rebuild_document_payload(self, row: WorkbenchDocumentProjectionModel) -> dict[str, Any]:
        published = self._session.query(PublishedDocumentModel).filter_by(final_doc_id=row.doc_id).first()
        document = self._session.query(DocumentModel).filter_by(doc_id=row.doc_id).first()
        intake_job = (
            self._session.query(IntakeJobModel)
            .filter_by(final_doc_id=row.doc_id)
            .order_by(IntakeJobModel.updated_at.desc())
            .first()
        )

        source_file = None
        parse_snapshot = None
        task_projection = None
        if intake_job is not None and intake_job.source_file_id:
            source_file = self._session.query(SourceFileModel).filter_by(
                source_file_id=intake_job.source_file_id
            ).first()
            parse_snapshot = (
                self._session.query(ParseSnapshotModel)
                .filter_by(source_file_id=intake_job.source_file_id)
                .order_by(ParseSnapshotModel.created_at.desc())
                .first()
            )

        if source_file is not None and source_file.upload_id:
            task_projection = self._task_repo.get_by_upload_id(source_file.upload_id)

        indexed_documents = (
            self._session.query(IndexedDocumentModel)
            .filter_by(final_doc_id=row.doc_id)
            .all()
        )
        indexed_document = _pick_indexed_document(indexed_documents, published)

        chunk_rows = (
            self._session.query(ChunkRegistryModel)
            .filter_by(final_doc_id=row.doc_id, available_int=1)
            .all()
        )

        filename = None
        if source_file is not None:
            filename = source_file.original_name or source_file.sanitized_name
        if not filename and parse_snapshot is not None:
            filename = parse_snapshot.source_filename
        if not filename and task_projection is not None:
            filename = task_projection.filename

        mime_type = None
        if task_projection is not None:
            mime_type = task_projection.mime_type
        if not mime_type and filename:
            mime_type = guess_type(filename)[0]

        parser_name = row.parser_profile_name
        if indexed_document is not None and indexed_document.parser_id:
            parser_name = indexed_document.parser_id
        elif parse_snapshot is not None and parse_snapshot.parser_id:
            parser_name = parse_snapshot.parser_id

        return {
            "doc_id": row.doc_id,
            "tenant_id": row.tenant_id,
            "collection_id": row.collection_id,
            "source_file_id": source_file.source_file_id if source_file is not None else row.source_file_id,
            "parse_snapshot_id": parse_snapshot.parse_snapshot_id if parse_snapshot is not None else row.parse_snapshot_id,
            "published_doc_id": published.published_document_id if published is not None else row.published_doc_id,
            "upload_id": source_file.upload_id if source_file is not None else row.upload_id,
            "filename": filename or row.filename,
            "mime_type": mime_type or row.mime_type,
            "document_state": _derive_document_state(published, intake_job, indexed_document, row.document_state),
            "publish_state": _derive_publish_state(published, document, row.publish_state),
            "active_index_version": (
                published.active_index_version
                if published is not None and published.active_index_version
                else indexed_document.index_version if indexed_document is not None else row.active_index_version
            ),
            "chunk_count": _derive_chunk_count(indexed_document, chunk_rows),
            "page_count": _derive_page_count(chunk_rows),
            "parser_profile_id": row.parser_profile_id,
            "parser_profile_name": parser_name,
            "is_stale": False,
            "degraded_reason": None,
        }

    @staticmethod
    def _ticket_raw_to_payload(raw: dict) -> dict[str, Any]:
        return {
            "ticket_id": raw.get("ticket_id", ""),
            "tenant_id": raw.get("tenant_id", ""),
            "collection_id": raw.get("collection_id", ""),
            "upload_id": raw.get("upload_id"),
            "source_file_id": raw.get("source_file_id"),
            "parse_snapshot_id": raw.get("parse_snapshot_id"),
            "doc_id": raw.get("doc_id"),
            "title": raw.get("title"),
            "filename": raw.get("filename"),
            "state": raw.get("state", "pending"),
            "priority": raw.get("priority"),
            "routing_recommendation": raw.get("routing_recommendation"),
            "assignee_user_id": raw.get("assignee_user_id"),
            "agent_decision": raw.get("agent_decision"),
            "agent_risk_level": raw.get("agent_risk_level"),
            "agent_finding_count": raw.get("agent_finding_count", 0),
            "agent_blocking_finding_count": raw.get("agent_blocking_finding_count", 0),
            "is_stale": False,
            "degraded_reason": None,
        }


def _derive_status(
    source_file_state: str | None,
    intake_job_state: str | None,
    ticket_state: str | None,
    published_document_state: str | None,
    index_build_state: str | None,
    active_index_version: str | None,
) -> str:
    if published_document_state == "archived":
        return "archived"
    if published_document_state == "retracted":
        return "retracted"
    if active_index_version:
        return "published"
    if index_build_state == "building":
        return "indexing"
    if published_document_state == "publish_succeeded":
        return "published"
    if ticket_state == "approved":
        return "approved"
    if ticket_state == "rejected":
        return "rejected"
    if ticket_state == "pending":
        return "reviewing"
    if intake_job_state == "failed":
        return "failed"
    if intake_job_state in ("created", "conversion_queued", "conversion_running", "parsing", "processing"):
        return "parsing"
    if intake_job_state in ("review_queued", "review_running", "review_succeeded", "approval_requested", "awaiting_approval"):
        return "reviewing"
    if intake_job_state in ("publish_queued", "publish_running"):
        return "publishing"
    if intake_job_state == "published":
        return "published"
    if source_file_state == "ready":
        return "ready"
    if source_file_state == "uploaded":
        return "uploaded"
    return "uploading"


def _derive_progress(
    source_file_state: str | None,
    intake_job_state: str | None,
    parse_snapshot_state: str | None,
    ticket_state: str | None,
    published_document_state: str | None,
    index_build_state: str | None,
    active_index_version: str | None,
) -> int:
    if active_index_version:
        return 100
    if index_build_state == "building":
        return 95
    if published_document_state == "publish_succeeded":
        return 100
    if ticket_state == "approved":
        return 90
    if ticket_state == "rejected":
        return 100
    if ticket_state == "pending":
        return 70
    if parse_snapshot_state == "parsed":
        return 50
    if parse_snapshot_state == "parsing":
        return 40
    if intake_job_state == "failed":
        return 100
    if source_file_state == "ready":
        return 20
    return 0


def _best_chunk_match(source_quote: str, chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
    quote = _normalize_match_text(source_quote)
    if not quote:
        return None
    best_chunk: dict[str, Any] | None = None
    best_score = 0.0
    for chunk in chunks:
        content = _normalize_match_text(str(chunk.get("content", "") or ""))
        if not content:
            continue
        score = _similarity_score(quote, content)
        if score > best_score:
            best_score = score
            best_chunk = chunk
    if best_chunk is None or best_score < 0.55:
        return None
    return best_chunk


def _similarity_score(quote: str, content: str) -> float:
    if quote == content:
        return 1.0
    if quote in content:
        return 0.99

    quote_tokens = set(token for token in re.split(r"\W+", quote) if token)
    content_tokens = set(token for token in re.split(r"\W+", content) if token)
    overlap = len(quote_tokens & content_tokens) / max(1, len(quote_tokens))
    sequence_ratio = difflib.SequenceMatcher(None, quote, content).ratio()
    longest = difflib.SequenceMatcher(None, quote, content).find_longest_match(0, len(quote), 0, len(content)).size
    coverage = longest / max(1, len(quote))
    return max(sequence_ratio, (0.45 * overlap) + (0.55 * coverage))


def _normalize_match_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _source_anchor_json(chunk: dict[str, Any]) -> dict[str, Any] | None:
    section_path = chunk.get("section_path")
    page_spans = chunk.get("page_spans")
    anchor = {
        "section_path": section_path if isinstance(section_path, list) else [],
        "page_spans": page_spans if isinstance(page_spans, list) else [],
    }
    if not anchor["section_path"] and not anchor["page_spans"]:
        return None
    return anchor


def _pick_indexed_document(
    indexed_documents: list[IndexedDocumentModel],
    published: PublishedDocumentModel | None,
) -> IndexedDocumentModel | None:
    if not indexed_documents:
        return None
    if published is not None and published.active_index_version:
        for item in indexed_documents:
            if item.index_version == published.active_index_version:
                return item
    for item in indexed_documents:
        if str(item.state or "").lower() == "active":
            return item
    return indexed_documents[0]


def _derive_page_count(chunk_rows: list[ChunkRegistryModel]) -> int:
    max_page = 0
    for row in chunk_rows:
        payload = row.payload_json or {}
        page_spans = payload.get("page_spans") or []
        if not isinstance(page_spans, list):
            continue
        for span in page_spans:
            if not isinstance(span, dict):
                continue
            try:
                page_to = int(span.get("page_to") or span.get("page_from") or 0)
            except (TypeError, ValueError):
                continue
            max_page = max(max_page, page_to)
    return max_page


def _derive_chunk_count(
    indexed_document: IndexedDocumentModel | None,
    chunk_rows: list[ChunkRegistryModel],
) -> int:
    if indexed_document is not None:
        return indexed_document.visible_chunk_count or indexed_document.chunk_count or len(chunk_rows)
    return len(chunk_rows)


def _derive_document_state(
    published: PublishedDocumentModel | None,
    intake_job: IntakeJobModel | None,
    indexed_document: IndexedDocumentModel | None,
    fallback: str | None,
) -> str | None:
    if published is not None:
        state = str(published.state or "").upper()
        if state in {"ARCHIVED", "RETRACTED", "DEPRECATED"}:
            return "ARCHIVED"
        if published.active_index_version or (
            indexed_document is not None and str(indexed_document.state or "").lower() == "active"
        ):
            return "ACTIVE"
        return state or fallback
    if intake_job is not None and str(intake_job.state or "").lower() != "published":
        return "PENDING"
    return fallback


def _derive_publish_state(
    published: PublishedDocumentModel | None,
    document: DocumentModel | None,
    fallback: str | None,
) -> str | None:
    if published is not None and published.state:
        return str(published.state).lower()
    if document is not None and document.publish_status:
        return str(document.publish_status).lower()
    return fallback
