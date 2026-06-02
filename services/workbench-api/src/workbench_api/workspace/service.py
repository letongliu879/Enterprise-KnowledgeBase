"""Workspace detail aggregation service.

Fetches single-ticket workspace detail by concurrently querying:
- ticket projection (SQL, fast)
- approval ticket detail
- source file metadata
- parse snapshot
- chunks
- chunk edits
- agent review findings

Each downstream call has its own timeout.
Partial failures are collected into degraded_parts, never fail the whole page.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from ..deps import CurrentUser
from ..downstream_clients import ApprovalClient, IndexingClient, IntakeClient
from ..downstream_clients.errors import DownstreamError
from ..chunk_edits.repository import ChunkEditRepository
from ..projections.repository import (
    AgentReviewProjectionRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)


class WorkspaceService:
    _DOWNSTREAM_TIMEOUTS = {
        "ticket": 0.8,
        "source_file": 0.5,
        "parse_snapshot": 0.8,
        "chunks": 0.8,
        "chunk_edits": 0.3,
        "agent_review": 0.3,
    }

    def __init__(
        self,
        task_repo: TaskProjectionRepository,
        ticket_repo: TicketProjectionRepository,
        agent_review_repo: AgentReviewProjectionRepository,
        chunk_edit_repo: ChunkEditRepository | None,
        intake_client: IntakeClient,
        approval_client: ApprovalClient,
        indexing_client: IndexingClient,
    ):
        self._task_repo = task_repo
        self._ticket_repo = ticket_repo
        self._agent_review_repo = agent_review_repo
        self._chunk_edit_repo = chunk_edit_repo
        self._intake_client = intake_client
        self._approval_client = approval_client
        self._indexing_client = indexing_client

    async def get_workspace(self, ticket_id: str, user: CurrentUser, trace_id: str) -> dict[str, Any]:
        degraded_parts: list[str] = []
        tenant_id = user.tenant_id

        # 1. Fast SQL lookup: ticket projection
        ticket_proj = self._ticket_repo.get(ticket_id)
        if ticket_proj is None:
            # Fallback: also check task projection by ticket_id
            from reality_rag_persistence.models import WorkbenchTaskProjectionModel
            task_proj = self._task_repo._session.query(WorkbenchTaskProjectionModel).filter_by(
                tenant_id=tenant_id, ticket_id=ticket_id
            ).first()
            if task_proj is None:
                return {"ticket_id": ticket_id, "error": "ticket_not_found", "degraded_parts": ["ticket"]}
            collection_id = task_proj.collection_id
        else:
            collection_id = ticket_proj.collection_id

        if not user.can_access_collection(collection_id):
            return {"ticket_id": ticket_id, "error": "collection_access_denied", "degraded_parts": ["ticket"]}

        # 2. Concurrent downstream calls with individual timeouts
        coros = {}

        async def fetch_ticket_detail():
            try:
                return await asyncio.wait_for(
                    self._approval_client.get_ticket(ticket_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["ticket"],
                )
            except (asyncio.TimeoutError, DownstreamError) as e:
                degraded_parts.append("ticket_detail")
                return None

        async def fetch_source_file():
            sf_id = ticket_proj.source_file_id if ticket_proj else None
            if not sf_id:
                return None
            try:
                return await asyncio.wait_for(
                    self._intake_client.get_source_file(sf_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["source_file"],
                )
            except (asyncio.TimeoutError, DownstreamError) as e:
                degraded_parts.append("source_file")
                return None

        async def fetch_parse_snapshot():
            ps_id = ticket_proj.parse_snapshot_id if ticket_proj else None
            if not ps_id:
                return None
            try:
                return await asyncio.wait_for(
                    self._indexing_client.get_parse_snapshot(ps_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["parse_snapshot"],
                )
            except (asyncio.TimeoutError, DownstreamError) as e:
                degraded_parts.append("parse_snapshot")
                return None

        async def fetch_chunks():
            ps_id = ticket_proj.parse_snapshot_id if ticket_proj else None
            if not ps_id:
                return None
            try:
                return await asyncio.wait_for(
                    self._indexing_client.get_parse_snapshot_chunks(ps_id, page=1, page_size=50),
                    timeout=self._DOWNSTREAM_TIMEOUTS["chunks"],
                )
            except (asyncio.TimeoutError, DownstreamError) as e:
                degraded_parts.append("chunks")
                return None

        async def fetch_chunk_edits():
            ps_id = ticket_proj.parse_snapshot_id if ticket_proj else None
            if not ps_id or self._chunk_edit_repo is None:
                return None
            try:
                # chunk edits are local SQL, no downstream
                return self._chunk_edit_repo.list_by_snapshot(ps_id)
            except Exception:
                degraded_parts.append("chunk_edits")
                return None

        async def fetch_agent_reviews():
            try:
                return self._agent_review_repo.list_by_ticket(ticket_id, tenant_id)
            except Exception:
                degraded_parts.append("agent_review_findings")
                return []

        coros = {
            "ticket": asyncio.create_task(fetch_ticket_detail()),
            "source_file": asyncio.create_task(fetch_source_file()),
            "parse_snapshot": asyncio.create_task(fetch_parse_snapshot()),
            "chunks": asyncio.create_task(fetch_chunks()),
            "chunk_edits": asyncio.create_task(fetch_chunk_edits()),
            "agent_reviews": asyncio.create_task(fetch_agent_reviews()),
        }

        results = {}
        for key, task in coros.items():
            try:
                results[key] = await task
            except Exception:
                degraded_parts.append(key)
                results[key] = None

        ticket_detail = results.get("ticket")
        source_file = results.get("source_file")
        parse_snapshot = results.get("parse_snapshot")
        chunks = results.get("chunks")
        chunk_edits = results.get("chunk_edits")
        agent_reviews = results.get("agent_reviews") or []

        # Build permissions
        permissions = {
            "can_approve": user.has_role("reviewer") and (ticket_detail or {}).get("state") == "pending",
            "can_reject": user.has_role("reviewer") and (ticket_detail or {}).get("state") == "pending",
            "can_edit_chunks": user.has_role("chunk_editor"),
            "can_upload": user.has_role("uploader"),
        }

        # Projection freshness
        projection_freshness = {
            "ticket_projection_updated_at": ticket_proj.projection_updated_at.isoformat() if ticket_proj and ticket_proj.projection_updated_at else None,
            "ticket_is_stale": ticket_proj.is_stale if ticket_proj else True,
        }

        return {
            "ticket_id": ticket_id,
            "ticket": ticket_detail,
            "document": {
                "doc_id": ticket_proj.doc_id if ticket_proj else None,
                "source_file_id": ticket_proj.source_file_id if ticket_proj else None,
                "parse_snapshot_id": ticket_proj.parse_snapshot_id if ticket_proj else None,
            },
            "source_file": source_file,
            "parse_snapshot": parse_snapshot,
            "chunks": chunks,
            "chunk_edits": chunk_edits,
            "agent_review_findings": [
                {
                    "finding_id": f.finding_id,
                    "severity": f.severity,
                    "category": f.category,
                    "problem_summary": f.problem_summary,
                    "evidence_id": f.evidence_id,
                    "doc_id": f.doc_id,
                    "source_file_id": f.source_file_id,
                    "parse_snapshot_id": f.parse_snapshot_id,
                    "page_from": f.page_from,
                    "page_to": f.page_to,
                    "source_quote": f.source_quote,
                    "chunk_quote": f.chunk_quote,
                    "why_wrong": f.why_wrong,
                    "suggested_fix": f.suggested_fix,
                    "suggested_operation": f.suggested_operation,
                    "confidence": f.confidence,
                    "state": f.state,
                }
                for f in agent_reviews
            ],
            "permissions": permissions,
            "projection_freshness": projection_freshness,
            "degraded_parts": degraded_parts,
            "trace_id": trace_id,
        }
