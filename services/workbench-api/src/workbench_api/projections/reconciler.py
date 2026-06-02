"""Projection reconciler — scans stale projections and re-fetches from owner services.

Reconciliation is a backfill/repair mechanism, not the primary update path.
It runs periodically and repairs projections that missed events or fell stale.

Uses database row-level locks (FOR UPDATE SKIP LOCKED) for safe multi-instance
concurrency, and cursor-based pagination to avoid full table scans.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..downstream_clients import ApprovalClient, IndexingClient, IntakeClient
from ..downstream_clients.errors import DownstreamError
from .projector import ProjectionProjector
from .repository import (
    ReconcileRunRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)


RECONCILE_INTERVAL_SECONDS = int(os.environ.get("WORKBENCH_RECONCILE_INTERVAL_SECONDS", "300"))
RECONCILE_BATCH_SIZE = int(os.environ.get("WORKBENCH_RECONCILE_BATCH_SIZE", "100"))
RECONCILE_ENABLED = os.environ.get("WORKBENCH_RECONCILE_ENABLED", "true").lower() == "true"


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

        # Use raw SQL with FOR UPDATE SKIP LOCKED for safe multi-instance concurrency
        sql = text("""
            SELECT projection_id, tenant_id, collection_id, upload_id, version
            FROM workbench_task_projection
            WHERE is_stale = true
            {tenant_filter}
            ORDER BY stale_after ASC NULLS LAST, projection_updated_at ASC
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        """.format(tenant_filter="AND tenant_id = :tenant_id" if tenant_id else ""))

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

        sql = text("""
            SELECT ticket_id, tenant_id, collection_id, version
            FROM workbench_ticket_projection
            WHERE is_stale = true
            {tenant_filter}
            ORDER BY projection_updated_at ASC
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        """.format(tenant_filter="AND tenant_id = :tenant_id" if tenant_id else ""))

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
        """Scan stale document projections with row-level locks."""
        run_id = f"rec_{uuid.uuid4().hex[:16]}"
        self._reconcile_repo.create({
            "run_id": run_id,
            "tenant_id": tenant_id,
            "aggregate_type": "document",
            "started_at": _utcnow(),
            "status": "running",
            "trace_id": run_id,
        })

        sql = text("""
            SELECT doc_id, tenant_id, collection_id, version
            FROM workbench_document_projection
            WHERE is_stale = true
            {tenant_filter}
            ORDER BY projection_updated_at ASC
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        """.format(tenant_filter="AND tenant_id = :tenant_id" if tenant_id else ""))

        params = {"limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id

        scanned = len(self._session.execute(sql, params).mappings().all())
        # Document reconciliation is primarily event-driven; reconcile just marks scanned
        self._reconcile_repo.update(run_id, {
            "completed_at": _utcnow(),
            "scanned_count": scanned,
            "updated_count": 0,
            "failed_count": 0,
            "degraded_count": 0,
            "status": "completed",
        })

        return {"run_id": run_id, "scanned": scanned, "updated": 0, "failed": 0, "degraded": 0}

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

        sql = text("""
            SELECT evidence_id, tenant_id, collection_id, version
            FROM workbench_chunk_projection
            WHERE is_stale = true
            {tenant_filter}
            ORDER BY projection_updated_at ASC
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        """.format(tenant_filter="AND tenant_id = :tenant_id" if tenant_id else ""))

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
    if published_document_state == "ARCHIVED":
        return "archived"
    if published_document_state == "RETRACTED":
        return "retracted"
    if active_index_version:
        return "published"
    if index_build_state == "BUILDING":
        return "indexing"
    if published_document_state == "PUBLISH_SUCCEEDED":
        return "published"
    if ticket_state == "approved":
        return "approved"
    if ticket_state == "rejected":
        return "rejected"
    if ticket_state == "pending":
        return "reviewing"
    if intake_job_state == "FAILED":
        return "failed"
    if intake_job_state in ("CREATED", "PARSING"):
        return "parsing"
    if source_file_state == "READY":
        return "uploading"
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
    if index_build_state == "BUILDING":
        return 95
    if published_document_state == "PUBLISH_SUCCEEDED":
        return 100
    if ticket_state == "approved":
        return 90
    if ticket_state == "rejected":
        return 100
    if ticket_state == "pending":
        return 70
    if parse_snapshot_state == "PARSED":
        return 50
    if parse_snapshot_state == "PARSING":
        return 40
    if intake_job_state == "FAILED":
        return 100
    if source_file_state == "READY":
        return 20
    return 0


async def reconciliation_loop() -> None:
    """Background reconciliation loop started by FastAPI lifespan.

    Runs every RECONCILE_INTERVAL_SECONDS, processing one batch of stale
    projections per aggregate type. Uses database row-level locks to avoid
    duplicate work across multiple instances.
    """
    if not RECONCILE_ENABLED:
        return

    while True:
        try:
            await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)

            # Lazy import to avoid circular dependency at module load time
            from reality_rag_persistence.database import get_session

            db = next(get_session())
            try:
                reconciler = ProjectionReconciler(
                    session=db,
                    intake_client=IntakeClient(),
                    approval_client=ApprovalClient(),
                    indexing_client=IndexingClient(),
                )

                for aggregate_type in ["task", "ticket", "document", "chunk"]:
                    try:
                        if aggregate_type == "task":
                            await reconciler.reconcile_tasks(limit=RECONCILE_BATCH_SIZE)
                        elif aggregate_type == "ticket":
                            await reconciler.reconcile_tickets(limit=RECONCILE_BATCH_SIZE)
                        elif aggregate_type == "document":
                            await reconciler.reconcile_documents(limit=RECONCILE_BATCH_SIZE)
                        elif aggregate_type == "chunk":
                            await reconciler.reconcile_chunks(limit=RECONCILE_BATCH_SIZE)
                    except Exception as e:
                        # Log and continue with next aggregate type
                        import logging
                        logging.getLogger(__name__).error(
                            f"Reconciliation failed for {aggregate_type}: {e}"
                        )
            finally:
                db.close()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Reconciliation loop crashed: {e}")
            await asyncio.sleep(60)  # Short retry on crash
