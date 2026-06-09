"""Workspace detail aggregation service.

Ticket approval state and document linkage are aggregated into one review-facing
workspace response. Ticket facts stay ticket-owned; document linkage is resolved
from document projection first so review and document-library views stay aligned.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from reality_rag_persistence.models import WorkbenchTaskProjectionModel

from ..chunk_edits.repository import ChunkEditRepository
from ..deps import CurrentUser
from ..downstream_clients import ApprovalClient, IndexingClient, IntakeClient
from ..downstream_clients.errors import DownstreamError
from ..projections.repository import (
    AgentReviewProjectionRepository,
    DocumentProjectionRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)
from .models import (
    WorkspaceAgentReviewFindingView,
    WorkspaceAgentReviewView,
    WorkspaceCapabilitiesView,
    WorkspaceChunkEditListView,
    WorkspaceChunkEditView,
    WorkspaceChunkListView,
    WorkspaceChunkView,
    WorkspaceDetailView,
    WorkspaceDocumentView,
    WorkspaceParseSnapshotView,
    WorkspaceProjectionFreshnessView,
    WorkspaceSourceFileView,
    WorkspaceTaskView,
    WorkspaceTicketView,
)


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def _non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _normalize_status(value: Any) -> str:
    return str(value or "").strip().lower()


class WorkspaceService:
    _DOWNSTREAM_TIMEOUTS = {
        "ticket": 0.8,
        "agent_review": 0.5,
        "source_file": 0.5,
        "parse_snapshot": 0.8,
        "chunks": 0.8,
    }

    def __init__(
        self,
        task_repo: TaskProjectionRepository,
        ticket_repo: TicketProjectionRepository,
        document_repo: DocumentProjectionRepository,
        agent_review_repo: AgentReviewProjectionRepository,
        chunk_edit_repo: ChunkEditRepository | None,
        intake_client: IntakeClient,
        approval_client: ApprovalClient,
        indexing_client: IndexingClient,
    ):
        self._task_repo = task_repo
        self._ticket_repo = ticket_repo
        self._document_repo = document_repo
        self._agent_review_repo = agent_review_repo
        self._chunk_edit_repo = chunk_edit_repo
        self._intake_client = intake_client
        self._approval_client = approval_client
        self._indexing_client = indexing_client

    def _append_degraded(self, degraded_parts: list[str], part: str) -> None:
        if part not in degraded_parts:
            degraded_parts.append(part)

    def _get_task_projection(self, ticket_id: str, tenant_id: str) -> WorkbenchTaskProjectionModel | None:
        return (
            self._task_repo._session.query(WorkbenchTaskProjectionModel)
            .filter_by(tenant_id=tenant_id, ticket_id=ticket_id)
            .first()
        )

    def _derive_task_status(self, task_proj: WorkbenchTaskProjectionModel | None) -> str:
        if task_proj is None:
            return "unknown"

        published_state = _normalize_status(task_proj.published_document_state)
        index_state = _normalize_status(task_proj.index_build_state)
        ticket_state = _normalize_status(task_proj.ticket_state)
        intake_state = _normalize_status(task_proj.intake_job_state)
        source_state = _normalize_status(task_proj.source_file_state)

        if published_state == "archived":
            return "archived"
        if published_state == "retracted":
            return "retracted"
        if task_proj.active_index_version:
            return "published"
        if index_state == "building":
            return "indexing"
        if published_state == "publish_succeeded":
            return "published"
        if ticket_state == "approved":
            return "approved"
        if ticket_state == "rejected":
            return "rejected"
        if ticket_state == "pending":
            return "reviewing"
        if intake_state == "failed":
            return "failed"
        if intake_state in {"created", "conversion_queued", "conversion_running", "parsing", "processing"}:
            return "parsing"
        if intake_state in {"review_queued", "review_running", "review_succeeded", "approval_requested", "awaiting_approval"}:
            return "reviewing"
        if intake_state in {"publish_queued", "publish_running"}:
            return "publishing"
        if intake_state == "published":
            return "published"
        if source_state == "ready":
            return "ready"
        if source_state == "uploaded":
            return "uploaded"
        return str(task_proj.overall_status or "uploading")

    def _build_task_view(
        self,
        task_proj: WorkbenchTaskProjectionModel | None,
    ) -> WorkspaceTaskView | None:
        if task_proj is None:
            return None

        return WorkspaceTaskView(
            upload_id=task_proj.upload_id,
            collection_id=task_proj.collection_id,
            status=self._derive_task_status(task_proj),
            filename=task_proj.filename,
            source_file_id=task_proj.source_file_id,
            intake_job_id=task_proj.intake_job_id,
            parse_snapshot_id=task_proj.parse_snapshot_id,
            ticket_id=task_proj.ticket_id,
            published_doc_id=task_proj.published_doc_id,
            doc_id=task_proj.doc_id,
            progress_pct=int(task_proj.progress_pct or 0),
            source_file_state=task_proj.source_file_state,
            intake_job_state=task_proj.intake_job_state,
            parse_snapshot_state=task_proj.parse_snapshot_state,
            ticket_state=task_proj.ticket_state,
            published_document_state=task_proj.published_document_state,
            index_build_state=task_proj.index_build_state,
            active_index_version=task_proj.active_index_version,
            created_at=_iso(task_proj.created_at),
            updated_at=_iso(task_proj.last_event_at),
            projection_updated_at=_iso(task_proj.projection_updated_at),
            is_stale=bool(task_proj.is_stale),
        )

    def _build_ticket_view(
        self,
        *,
        ticket_id: str,
        ticket_proj,
        task_proj: WorkbenchTaskProjectionModel | None,
        ticket_detail: dict[str, Any] | None,
    ) -> WorkspaceTicketView | None:
        if ticket_proj is None and task_proj is None and ticket_detail is None:
            return None

        detail = ticket_detail or {}
        status = _non_empty(detail.get("status"), detail.get("state"), ticket_proj.state if ticket_proj else None, task_proj.ticket_state if task_proj else None, "unknown")
        ticket_source = "merged"
        if ticket_detail and ticket_proj:
            ticket_source = "merged"
        elif ticket_detail:
            ticket_source = "approval"
        else:
            ticket_source = "projection"

        return WorkspaceTicketView(
            ticket_id=ticket_id,
            collection_id=str(
                _non_empty(
                    detail.get("collection_id"),
                    ticket_proj.collection_id if ticket_proj else None,
                    task_proj.collection_id if task_proj else None,
                    "",
                )
            ),
            status=str(status),
            tenant_id=str(
                _non_empty(
                    detail.get("tenant_id"),
                    ticket_proj.tenant_id if ticket_proj else None,
                    task_proj.tenant_id if task_proj else None,
                    "",
                )
            ),
            doc_id=_non_empty(
                detail.get("doc_id"),
                detail.get("final_doc_id"),
                detail.get("preliminary_doc_id"),
                ticket_proj.doc_id if ticket_proj else None,
                task_proj.doc_id if task_proj else None,
            ),
            source_file_id=_non_empty(
                detail.get("source_file_id"),
                ticket_proj.source_file_id if ticket_proj else None,
                task_proj.source_file_id if task_proj else None,
            ),
            parse_snapshot_id=_non_empty(
                detail.get("parse_snapshot_id"),
                ticket_proj.parse_snapshot_id if ticket_proj else None,
                task_proj.parse_snapshot_id if task_proj else None,
            ),
            upload_id=_non_empty(
                detail.get("upload_id"),
                ticket_proj.upload_id if ticket_proj else None,
                task_proj.upload_id if task_proj else None,
            ),
            title=_non_empty(detail.get("title"), ticket_proj.title if ticket_proj else None),
            filename=_non_empty(detail.get("filename"), ticket_proj.filename if ticket_proj else None, task_proj.filename if task_proj else None),
            priority=_non_empty(detail.get("priority"), ticket_proj.priority if ticket_proj else None),
            assignee_user_id=_non_empty(detail.get("assignee_user_id"), ticket_proj.assignee_user_id if ticket_proj else None),
            decision=_non_empty(detail.get("decision")),
            decision_reason=_non_empty(detail.get("decision_reason")),
            decided_by=_non_empty(detail.get("decided_by")),
            agent_decision=_non_empty(ticket_proj.agent_decision if ticket_proj else None),
            agent_risk_level=_non_empty(ticket_proj.agent_risk_level if ticket_proj else None),
            agent_finding_count=int(ticket_proj.agent_finding_count if ticket_proj else 0),
            agent_blocking_finding_count=int(ticket_proj.agent_blocking_finding_count if ticket_proj else 0),
            failure_code=_non_empty(detail.get("failure_code")),
            failure_stage=_non_empty(detail.get("failure_stage")),
            next_action=_non_empty(detail.get("next_action")),
            created_at=_iso(_non_empty(detail.get("created_at"), ticket_proj.created_at if ticket_proj else None, task_proj.created_at if task_proj else None)),
            updated_at=_iso(_non_empty(detail.get("updated_at"), ticket_proj.updated_at if ticket_proj else None, task_proj.last_event_at if task_proj else None)),
            projection_updated_at=_iso(ticket_proj.projection_updated_at if ticket_proj else None),
            is_stale=bool(ticket_proj.is_stale) if ticket_proj else False,
            source=ticket_source,
        )

    def _build_document_view(
        self,
        *,
        document_proj,
        ticket_proj,
        task_proj: WorkbenchTaskProjectionModel | None,
        ticket_view: WorkspaceTicketView | None,
    ) -> WorkspaceDocumentView:
        if document_proj is not None:
            return WorkspaceDocumentView(
                doc_id=document_proj.doc_id,
                tenant_id=document_proj.tenant_id,
                collection_id=document_proj.collection_id,
                source_file_id=document_proj.source_file_id,
                parse_snapshot_id=document_proj.parse_snapshot_id,
                published_doc_id=document_proj.published_doc_id,
                upload_id=document_proj.upload_id,
                filename=document_proj.filename,
                mime_type=document_proj.mime_type,
                document_state=document_proj.document_state,
                publish_state=document_proj.publish_state,
                active_index_version=document_proj.active_index_version,
                chunk_count=int(document_proj.chunk_count or 0),
                page_count=int(document_proj.page_count or 0),
                parser_profile_id=document_proj.parser_profile_id,
                parser_profile_name=document_proj.parser_profile_name,
                projection_updated_at=_iso(document_proj.projection_updated_at),
                is_stale=bool(document_proj.is_stale),
                degraded_reason=document_proj.degraded_reason,
                linkage_source="document_projection",
            )

        if ticket_proj is not None:
            return WorkspaceDocumentView(
                doc_id=ticket_proj.doc_id,
                tenant_id=ticket_proj.tenant_id,
                collection_id=ticket_proj.collection_id,
                source_file_id=ticket_proj.source_file_id,
                parse_snapshot_id=ticket_proj.parse_snapshot_id,
                upload_id=ticket_proj.upload_id,
                filename=ticket_proj.filename,
                linkage_source="ticket_projection",
            )

        if task_proj is not None:
            return WorkspaceDocumentView(
                doc_id=task_proj.doc_id,
                tenant_id=task_proj.tenant_id,
                collection_id=task_proj.collection_id,
                source_file_id=task_proj.source_file_id,
                parse_snapshot_id=task_proj.parse_snapshot_id,
                upload_id=task_proj.upload_id,
                filename=task_proj.filename,
                linkage_source="task_projection",
            )

        return WorkspaceDocumentView(
            doc_id=ticket_view.doc_id if ticket_view else None,
            linkage_source="missing",
        )

    def _resolve_task_projection_for_document(
        self,
        *,
        tenant_id: str,
        document_proj,
    ) -> WorkbenchTaskProjectionModel | None:
        if document_proj is None:
            return None
        if document_proj.upload_id:
            task = self._task_repo.get_by_upload_id(document_proj.upload_id)
            if task is not None and task.tenant_id == tenant_id:
                return task
        if document_proj.source_file_id:
            task = self._task_repo.get_by_source_file_id(document_proj.source_file_id, tenant_id)
            if task is not None:
                return task
        return self._task_repo.get_by_doc_id(document_proj.doc_id, tenant_id)

    def _resolve_ticket_projection_for_document(
        self,
        *,
        tenant_id: str,
        document_proj,
        task_proj: WorkbenchTaskProjectionModel | None,
    ):
        source_file_id = _non_empty(
            document_proj.source_file_id if document_proj is not None else None,
            task_proj.source_file_id if task_proj is not None else None,
        )
        doc_id = _non_empty(
            document_proj.doc_id if document_proj is not None else None,
            task_proj.doc_id if task_proj is not None else None,
        )

        if doc_id:
            pending = self._ticket_repo.get_pending_by_doc_id(str(doc_id), tenant_id)
            if pending is not None:
                return pending
        if source_file_id:
            pending = self._ticket_repo.get_pending_by_source_file_id(str(source_file_id), tenant_id)
            if pending is not None:
                return pending
        if doc_id:
            latest = self._ticket_repo.get_latest_by_doc_id(str(doc_id), tenant_id)
            if latest is not None:
                return latest
        if source_file_id:
            return self._ticket_repo.get_latest_by_source_file_id(str(source_file_id), tenant_id)
        return None

    def _normalize_source_file(self, payload: dict[str, Any] | None) -> WorkspaceSourceFileView | None:
        if not payload:
            return None
        source_file_id = _non_empty(payload.get("source_file_id"), payload.get("id"))
        if not source_file_id:
            return None
        return WorkspaceSourceFileView(
            source_file_id=str(source_file_id),
            upload_id=_non_empty(payload.get("upload_id")),
            tenant_id=_non_empty(payload.get("tenant_id")),
            collection_id=_non_empty(payload.get("collection_id")),
            filename=_non_empty(payload.get("original_name"), payload.get("filename"), payload.get("sanitized_name")),
            mime_type=_non_empty(payload.get("mime_type")),
            size_bytes=payload.get("size_bytes"),
            state=_non_empty(payload.get("state")),
            intake_job_id=_non_empty(payload.get("intake_job_id"), payload.get("claimed_by_job_id")),
            scan_verdict=_non_empty(payload.get("scan_verdict")),
            created_at=_iso(payload.get("created_at")),
            updated_at=_iso(payload.get("updated_at")),
        )

    def _normalize_parse_snapshot(self, payload: dict[str, Any] | None) -> WorkspaceParseSnapshotView | None:
        if not payload:
            return None
        parse_snapshot_id = _non_empty(payload.get("parse_snapshot_id"))
        if not parse_snapshot_id:
            return None
        warnings = payload.get("warnings", [])
        return WorkspaceParseSnapshotView(
            parse_snapshot_id=str(parse_snapshot_id),
            source_file_id=_non_empty(payload.get("source_file_id")),
            tenant_id=_non_empty(payload.get("tenant_id")),
            collection_id=_non_empty(payload.get("collection_id")),
            source_filename=_non_empty(payload.get("source_filename")),
            source_suffix=_non_empty(payload.get("source_suffix")),
            parser_id=_non_empty(payload.get("parser_id")),
            parser_backend=_non_empty(payload.get("parser_backend")),
            parser_profile_id=_non_empty(payload.get("parser_profile_id")),
            effective_policy=_non_empty(payload.get("effective_policy")),
            decision_reason=_non_empty(payload.get("decision_reason")),
            preview_text=_non_empty(payload.get("preview_text")),
            warnings=[str(item) for item in warnings] if isinstance(warnings, list) else [],
            created_at=_iso(payload.get("created_at")),
        )

    def _normalize_chunks(self, payload: dict[str, Any] | None) -> WorkspaceChunkListView:
        items_payload = payload.get("items", []) if isinstance(payload, dict) else []
        items: list[WorkspaceChunkView] = []
        for raw in items_payload if isinstance(items_payload, list) else []:
            if not isinstance(raw, dict):
                continue
            evidence_id = raw.get("evidence_id")
            doc_id = raw.get("doc_id")
            content = raw.get("content")
            if not evidence_id or not doc_id or content is None:
                continue
            items.append(
                WorkspaceChunkView(
                    evidence_id=str(evidence_id),
                    doc_id=str(doc_id),
                    content=str(content),
                    vector_text=raw.get("vector_text"),
                    section_path=[str(item) for item in raw.get("section_path", [])] if isinstance(raw.get("section_path"), list) else [],
                    page_spans=raw.get("page_spans", []) if isinstance(raw.get("page_spans"), list) else [],
                    chunk_type=raw.get("chunk_type"),
                    metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else None,
                )
            )
        total = payload.get("total") if isinstance(payload, dict) else None
        return WorkspaceChunkListView(items=items, total=int(total if isinstance(total, int) else len(items)))

    def _normalize_chunk_edits(self, rows: list[Any] | None) -> WorkspaceChunkEditListView:
        items: list[WorkspaceChunkEditView] = []
        for row in rows or []:
            items.append(
                WorkspaceChunkEditView(
                    chunk_edit_id=row.chunk_edit_id,
                    tenant_id=row.tenant_id,
                    collection_id=row.collection_id,
                    source_file_id=row.source_file_id,
                    parse_snapshot_id=row.parse_snapshot_id,
                    base_evidence_id=row.base_evidence_id,
                    edit_scope=row.edit_scope,
                    operation=row.operation,
                    content=row.content,
                    vector_text=row.vector_text,
                    section_path=row.section_path,
                    metadata_patch=row.metadata_patch,
                    citation_payload=row.citation_payload,
                    source_block_ids=row.source_block_ids,
                    edit_reason=row.edit_reason,
                    edited_by=row.edited_by,
                    status=row.status,
                    downstream_revision_id=row.downstream_revision_id,
                    created_at=_iso(row.created_at),
                    updated_at=_iso(row.updated_at),
                )
            )
        return WorkspaceChunkEditListView(items=items, total=len(items))

    def _normalize_projection_agent_review(
        self,
        *,
        ticket_id: str,
        findings: list[Any],
        decision: str | None,
        source_file_id: str | None,
        parse_snapshot_id: str | None,
    ) -> WorkspaceAgentReviewView:
        normalized = [
            WorkspaceAgentReviewFindingView(
                finding_id=f.finding_id,
                severity=f.severity or "medium",
                category=f.category or "",
                problem_summary=f.problem_summary or "",
                source_quote=f.source_quote,
                evidence_id=f.evidence_id,
                doc_id=f.doc_id,
                source_file_id=f.source_file_id,
                parse_snapshot_id=f.parse_snapshot_id,
                page_from=f.page_from,
                page_to=f.page_to,
                state=f.state or "open",
                confidence=f.confidence,
                chunk_quote=f.chunk_quote,
                why_wrong=f.why_wrong,
                suggested_fix=f.suggested_fix,
                suggested_operation=f.suggested_operation,
            )
            for f in findings
        ]
        matched_count = sum(1 for finding in normalized if finding.evidence_id)
        return WorkspaceAgentReviewView(
            ticket_id=ticket_id,
            decision=decision,
            source_file_id=source_file_id,
            parse_snapshot_id=parse_snapshot_id,
            findings=normalized,
            matched_count=matched_count,
            unmatched_count=max(0, len(normalized) - matched_count),
            source="projection",
        )

    def _normalize_approval_agent_review(self, payload: dict[str, Any] | None) -> WorkspaceAgentReviewView:
        if not payload:
            return WorkspaceAgentReviewView(ticket_id="", source="missing")
        findings_payload = payload.get("findings", [])
        findings: list[WorkspaceAgentReviewFindingView] = []
        for raw in findings_payload if isinstance(findings_payload, list) else []:
            if not isinstance(raw, dict):
                continue
            findings.append(
                WorkspaceAgentReviewFindingView(
                    finding_id=str(raw.get("finding_id") or ""),
                    severity=str(raw.get("severity") or "medium"),
                    category=str(raw.get("category") or ""),
                    problem_summary=str(raw.get("problem_summary") or ""),
                    source_quote=raw.get("source_quote"),
                    evidence_id=raw.get("evidence_id"),
                    doc_id=raw.get("doc_id"),
                    source_file_id=raw.get("source_file_id"),
                    parse_snapshot_id=raw.get("parse_snapshot_id"),
                    page_from=raw.get("page_from"),
                    page_to=raw.get("page_to"),
                    state=str(raw.get("state") or "open"),
                    confidence=raw.get("confidence"),
                )
            )
        matched_count = payload.get("matched_count")
        if not isinstance(matched_count, int):
            matched_count = sum(1 for finding in findings if finding.evidence_id)
        unmatched_count = payload.get("unmatched_count")
        if not isinstance(unmatched_count, int):
            unmatched_count = max(0, len(findings) - matched_count)
        return WorkspaceAgentReviewView(
            ticket_id=str(payload.get("ticket_id") or ""),
            decision=payload.get("decision"),
            source_file_id=payload.get("source_file_id"),
            parse_snapshot_id=payload.get("parse_snapshot_id"),
            findings=findings,
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            source="approval",
        )

    def _can_manage_document_lifecycle(
        self,
        user: CurrentUser,
        *,
        document_view: WorkspaceDocumentView,
    ) -> tuple[bool, bool, bool]:
        is_admin = user.has_role("knowledge_admin") or user.has_role("platform_admin")
        if not is_admin:
            return False, False, False

        doc_state = _normalize_status(document_view.document_state)
        has_doc_id = bool(_non_empty(document_view.doc_id))
        has_snapshot = bool(_non_empty(document_view.parse_snapshot_id))
        is_published_managed = bool(
            has_doc_id
            and _non_empty(
                document_view.published_doc_id,
                document_view.active_index_version,
                document_view.publish_state if _normalize_status(document_view.publish_state) == "published" else None,
            )
        )
        is_live_document = doc_state not in {"archived", "retracted", "pending"}

        can_archive = is_published_managed and is_live_document
        can_retract = is_published_managed and is_live_document
        can_reindex = is_published_managed and is_live_document and has_snapshot
        return can_archive, can_retract, can_reindex

    def resolve_document_action_context(self, doc_id: str, user: CurrentUser) -> dict[str, Any]:
        document_proj = self._document_repo.get(doc_id)
        if document_proj is None:
            return {"error": "document_not_found"}
        if not user.can_access_collection(document_proj.collection_id):
            return {"error": "collection_access_denied"}

        task_proj = self._resolve_task_projection_for_document(
            tenant_id=user.tenant_id,
            document_proj=document_proj,
        )
        document_view = self._build_document_view(
            document_proj=document_proj,
            ticket_proj=None,
            task_proj=task_proj,
            ticket_view=None,
        )
        return {
            "document_projection": document_proj,
            "task_projection": task_proj,
            "document": document_view,
            "final_doc_id": _non_empty(document_view.doc_id, doc_id),
            "tenant_id": _non_empty(document_view.tenant_id, user.tenant_id),
            "collection_id": _non_empty(document_view.collection_id, document_proj.collection_id),
            "parse_snapshot_id": _non_empty(document_view.parse_snapshot_id),
            "published_doc_id": _non_empty(document_view.published_doc_id),
        }

    async def get_workspace(self, ticket_id: str, user: CurrentUser, trace_id: str) -> dict[str, Any]:
        degraded_parts: list[str] = []
        tenant_id = user.tenant_id

        ticket_proj = self._ticket_repo.get(ticket_id)
        task_proj = self._get_task_projection(ticket_id, tenant_id)
        if ticket_proj is None and task_proj is None:
            return {"ticket_id": ticket_id, "error": "ticket_not_found", "degraded_parts": ["ticket"]}

        collection_id = ticket_proj.collection_id if ticket_proj is not None else task_proj.collection_id
        if not user.can_access_collection(collection_id):
            return {"ticket_id": ticket_id, "error": "collection_access_denied", "degraded_parts": ["ticket"]}

        async def fetch_ticket_detail() -> dict[str, Any] | None:
            try:
                return await asyncio.wait_for(
                    self._approval_client.get_ticket(ticket_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["ticket"],
                )
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "ticket_detail")
                return None

        async def fetch_agent_review_fallback() -> dict[str, Any] | None:
            try:
                return await asyncio.wait_for(
                    self._approval_client.get_agent_review(ticket_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["agent_review"],
                )
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "agent_review")
                return None

        ticket_detail = await fetch_ticket_detail()
        ticket_view = self._build_ticket_view(
            ticket_id=ticket_id,
            ticket_proj=ticket_proj,
            task_proj=task_proj,
            ticket_detail=ticket_detail,
        )

        doc_id = ticket_view.doc_id if ticket_view else None
        document_proj = self._document_repo.get(doc_id) if doc_id else None
        if doc_id and document_proj is None:
            self._append_degraded(degraded_parts, "document_projection")

        document_view = self._build_document_view(
            document_proj=document_proj,
            ticket_proj=ticket_proj,
            task_proj=task_proj,
            ticket_view=ticket_view,
        )
        task_view = self._build_task_view(task_proj)

        effective_source_file_id = document_view.source_file_id
        effective_parse_snapshot_id = document_view.parse_snapshot_id
        effective_ticket_status = str(ticket_view.status if ticket_view else "").lower()

        projection_findings = self._agent_review_repo.list_by_ticket(ticket_id, tenant_id)

        async def fetch_source_file() -> WorkspaceSourceFileView | None:
            if not effective_source_file_id:
                return None
            try:
                result = await asyncio.wait_for(
                    self._intake_client.get_source_file(effective_source_file_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["source_file"],
                )
                return self._normalize_source_file(result)
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "source_file")
                return None

        async def fetch_parse_snapshot() -> WorkspaceParseSnapshotView | None:
            if not effective_parse_snapshot_id:
                return None
            try:
                result = await asyncio.wait_for(
                    self._indexing_client.get_parse_snapshot(effective_parse_snapshot_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["parse_snapshot"],
                )
                return self._normalize_parse_snapshot(result)
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "parse_snapshot")
                return None

        async def fetch_chunks() -> WorkspaceChunkListView:
            if not effective_parse_snapshot_id:
                return WorkspaceChunkListView()
            try:
                result = await asyncio.wait_for(
                    self._indexing_client.get_parse_snapshot_chunks(
                        effective_parse_snapshot_id,
                        page=1,
                        page_size=100,
                    ),
                    timeout=self._DOWNSTREAM_TIMEOUTS["chunks"],
                )
                return self._normalize_chunks(result)
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "chunks")
                return WorkspaceChunkListView()

        async def fetch_chunk_edits() -> WorkspaceChunkEditListView:
            if not effective_parse_snapshot_id or self._chunk_edit_repo is None:
                return WorkspaceChunkEditListView()
            try:
                return self._normalize_chunk_edits(
                    self._chunk_edit_repo.list_by_snapshot(effective_parse_snapshot_id)
                )
            except Exception:
                self._append_degraded(degraded_parts, "chunk_edits")
                return WorkspaceChunkEditListView()

        coros = {
            "source_file": asyncio.create_task(fetch_source_file()),
            "parse_snapshot": asyncio.create_task(fetch_parse_snapshot()),
            "chunks": asyncio.create_task(fetch_chunks()),
            "chunk_edits": asyncio.create_task(fetch_chunk_edits()),
        }

        results: dict[str, Any] = {}
        for key, task in coros.items():
            try:
                results[key] = await task
            except Exception:
                self._append_degraded(degraded_parts, key)
                if key == "chunks":
                    results[key] = WorkspaceChunkListView()
                elif key == "chunk_edits":
                    results[key] = WorkspaceChunkEditListView()
                else:
                    results[key] = None

        parse_snapshot = results["parse_snapshot"]
        if effective_parse_snapshot_id and parse_snapshot is None:
            self._append_degraded(degraded_parts, "parse_snapshot")
        if effective_source_file_id and results["source_file"] is None:
            self._append_degraded(degraded_parts, "source_file")

        if projection_findings:
            agent_review = self._normalize_projection_agent_review(
                ticket_id=ticket_id,
                findings=projection_findings,
                decision=_non_empty(ticket_view.decision if ticket_view else None, ticket_view.agent_decision if ticket_view else None),
                source_file_id=effective_source_file_id,
                parse_snapshot_id=effective_parse_snapshot_id,
            )
        else:
            approval_review = await fetch_agent_review_fallback()
            if approval_review is None:
                agent_review = WorkspaceAgentReviewView(
                    ticket_id=ticket_id,
                    decision=_non_empty(ticket_view.decision if ticket_view else None, ticket_view.agent_decision if ticket_view else None),
                    source_file_id=effective_source_file_id,
                    parse_snapshot_id=effective_parse_snapshot_id,
                    source="missing",
                )
            else:
                agent_review = self._normalize_approval_agent_review(approval_review)
                if not agent_review.ticket_id:
                    agent_review.ticket_id = ticket_id
                if not agent_review.source_file_id:
                    agent_review.source_file_id = effective_source_file_id
                if not agent_review.parse_snapshot_id:
                    agent_review.parse_snapshot_id = effective_parse_snapshot_id

        can_archive, can_retract, can_reindex = self._can_manage_document_lifecycle(
            user,
            document_view=document_view,
        )
        capabilities = WorkspaceCapabilitiesView(
            can_view_source=bool(effective_source_file_id),
            can_view_parsed_text=bool(parse_snapshot and (parse_snapshot.preview_text or "").strip()),
            can_search_in_document=bool(parse_snapshot and (parse_snapshot.preview_text or "").strip()),
            can_edit_drafts=bool(user.has_role("chunk_editor") and effective_parse_snapshot_id),
            can_jump_to_chunk=bool(effective_parse_snapshot_id),
            can_decide_ticket=bool(user.has_role("reviewer") and effective_ticket_status == "pending"),
            can_approve=bool(user.has_role("reviewer") and effective_ticket_status == "pending"),
            can_reject=bool(user.has_role("reviewer") and effective_ticket_status == "pending"),
            can_upload=bool(user.has_role("uploader")),
            can_archive=can_archive,
            can_retract=can_retract,
            can_reindex=can_reindex,
        )

        projection_freshness = WorkspaceProjectionFreshnessView(
            ticket_projection_updated_at=_iso(ticket_proj.projection_updated_at if ticket_proj else None),
            ticket_is_stale=bool(ticket_proj.is_stale) if ticket_proj else True,
            document_projection_updated_at=_iso(document_proj.projection_updated_at if document_proj else None),
            document_is_stale=bool(document_proj.is_stale) if document_proj else True,
        )

        return WorkspaceDetailView(
            ticket_id=ticket_id,
            ticket=ticket_view,
            document=document_view,
            task=task_view,
            source_file=results["source_file"],
            parse_snapshot=parse_snapshot,
            chunks=results["chunks"],
            chunk_edits=results["chunk_edits"],
            agent_review=agent_review,
            capabilities=capabilities,
            projection_freshness=projection_freshness,
            degraded_parts=degraded_parts,
            trace_id=trace_id,
        ).model_dump()

    async def get_document_workspace(self, doc_id: str, user: CurrentUser, trace_id: str) -> dict[str, Any]:
        degraded_parts: list[str] = []
        tenant_id = user.tenant_id

        document_proj = self._document_repo.get(doc_id)
        if document_proj is None:
            return {"doc_id": doc_id, "error": "document_not_found", "degraded_parts": ["document_projection"]}
        if not user.can_access_collection(document_proj.collection_id):
            return {"doc_id": doc_id, "error": "collection_access_denied", "degraded_parts": ["document_projection"]}

        task_proj = self._resolve_task_projection_for_document(
            tenant_id=tenant_id,
            document_proj=document_proj,
        )
        ticket_proj = self._resolve_ticket_projection_for_document(
            tenant_id=tenant_id,
            document_proj=document_proj,
            task_proj=task_proj,
        )
        task_view = self._build_task_view(task_proj)

        ticket_id = str(_non_empty(ticket_proj.ticket_id if ticket_proj is not None else None, f"doc:{doc_id}"))

        async def fetch_ticket_detail() -> dict[str, Any] | None:
            if ticket_proj is None:
                return None
            try:
                return await asyncio.wait_for(
                    self._approval_client.get_ticket(ticket_proj.ticket_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["ticket"],
                )
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "ticket_detail")
                return None

        async def fetch_agent_review_fallback() -> dict[str, Any] | None:
            if ticket_proj is None:
                return None
            try:
                return await asyncio.wait_for(
                    self._approval_client.get_agent_review(ticket_proj.ticket_id),
                    timeout=self._DOWNSTREAM_TIMEOUTS["agent_review"],
                )
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "agent_review")
                return None

        ticket_detail = await fetch_ticket_detail()
        ticket_view = self._build_ticket_view(
            ticket_id=ticket_proj.ticket_id if ticket_proj is not None else ticket_id,
            ticket_proj=ticket_proj,
            task_proj=task_proj,
            ticket_detail=ticket_detail,
        )

        document_view = self._build_document_view(
            document_proj=document_proj,
            ticket_proj=ticket_proj,
            task_proj=task_proj,
            ticket_view=ticket_view,
        )

        effective_source_file_id = _non_empty(
            document_view.source_file_id,
            ticket_view.source_file_id if ticket_view else None,
            task_view.source_file_id if task_view else None,
        )
        effective_parse_snapshot_id = _non_empty(
            document_view.parse_snapshot_id,
            ticket_view.parse_snapshot_id if ticket_view else None,
            task_view.parse_snapshot_id if task_view else None,
        )
        effective_ticket_status = str(ticket_view.status if ticket_view else "").lower()

        projection_findings = []
        if ticket_proj is not None:
            projection_findings = self._agent_review_repo.list_by_ticket(ticket_proj.ticket_id, tenant_id)

        async def fetch_source_file() -> WorkspaceSourceFileView | None:
            if not effective_source_file_id:
                return None
            try:
                result = await asyncio.wait_for(
                    self._intake_client.get_source_file(str(effective_source_file_id)),
                    timeout=self._DOWNSTREAM_TIMEOUTS["source_file"],
                )
                return self._normalize_source_file(result)
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "source_file")
                return None

        async def fetch_parse_snapshot() -> WorkspaceParseSnapshotView | None:
            if not effective_parse_snapshot_id:
                return None
            try:
                result = await asyncio.wait_for(
                    self._indexing_client.get_parse_snapshot(str(effective_parse_snapshot_id)),
                    timeout=self._DOWNSTREAM_TIMEOUTS["parse_snapshot"],
                )
                return self._normalize_parse_snapshot(result)
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "parse_snapshot")
                return None

        async def fetch_chunks() -> WorkspaceChunkListView:
            if not effective_parse_snapshot_id:
                return WorkspaceChunkListView()
            try:
                result = await asyncio.wait_for(
                    self._indexing_client.get_parse_snapshot_chunks(
                        str(effective_parse_snapshot_id),
                        page=1,
                        page_size=100,
                    ),
                    timeout=self._DOWNSTREAM_TIMEOUTS["chunks"],
                )
                return self._normalize_chunks(result)
            except (asyncio.TimeoutError, DownstreamError):
                self._append_degraded(degraded_parts, "chunks")
                return WorkspaceChunkListView()

        async def fetch_chunk_edits() -> WorkspaceChunkEditListView:
            if not effective_parse_snapshot_id or self._chunk_edit_repo is None:
                return WorkspaceChunkEditListView()
            try:
                return self._normalize_chunk_edits(
                    self._chunk_edit_repo.list_by_snapshot(str(effective_parse_snapshot_id))
                )
            except Exception:
                self._append_degraded(degraded_parts, "chunk_edits")
                return WorkspaceChunkEditListView()

        coroutines = {
            "source_file": asyncio.create_task(fetch_source_file()),
            "parse_snapshot": asyncio.create_task(fetch_parse_snapshot()),
            "chunks": asyncio.create_task(fetch_chunks()),
            "chunk_edits": asyncio.create_task(fetch_chunk_edits()),
        }

        results: dict[str, Any] = {}
        for key, task in coroutines.items():
            try:
                results[key] = await task
            except Exception:
                self._append_degraded(degraded_parts, key)
                if key == "chunks":
                    results[key] = WorkspaceChunkListView()
                elif key == "chunk_edits":
                    results[key] = WorkspaceChunkEditListView()
                else:
                    results[key] = None

        parse_snapshot = results["parse_snapshot"]

        if projection_findings:
            agent_review = self._normalize_projection_agent_review(
                ticket_id=ticket_proj.ticket_id if ticket_proj is not None else ticket_id,
                findings=projection_findings,
                decision=_non_empty(ticket_view.decision if ticket_view else None, ticket_view.agent_decision if ticket_view else None),
                source_file_id=str(effective_source_file_id) if effective_source_file_id else None,
                parse_snapshot_id=str(effective_parse_snapshot_id) if effective_parse_snapshot_id else None,
            )
        else:
            approval_review = await fetch_agent_review_fallback()
            if approval_review is None:
                agent_review = WorkspaceAgentReviewView(
                    ticket_id=ticket_proj.ticket_id if ticket_proj is not None else ticket_id,
                    decision=_non_empty(ticket_view.decision if ticket_view else None, ticket_view.agent_decision if ticket_view else None),
                    source_file_id=str(effective_source_file_id) if effective_source_file_id else None,
                    parse_snapshot_id=str(effective_parse_snapshot_id) if effective_parse_snapshot_id else None,
                    source="missing",
                )
            else:
                agent_review = self._normalize_approval_agent_review(approval_review)
                if not agent_review.ticket_id:
                    agent_review.ticket_id = ticket_proj.ticket_id if ticket_proj is not None else ticket_id
                if not agent_review.source_file_id:
                    agent_review.source_file_id = str(effective_source_file_id) if effective_source_file_id else None
                if not agent_review.parse_snapshot_id:
                    agent_review.parse_snapshot_id = str(effective_parse_snapshot_id) if effective_parse_snapshot_id else None

        can_archive, can_retract, can_reindex = self._can_manage_document_lifecycle(
            user,
            document_view=document_view,
        )
        capabilities = WorkspaceCapabilitiesView(
            can_view_source=bool(effective_source_file_id),
            can_view_parsed_text=bool(parse_snapshot and (parse_snapshot.preview_text or "").strip()),
            can_search_in_document=bool(parse_snapshot and (parse_snapshot.preview_text or "").strip()),
            can_edit_drafts=bool(user.has_role("chunk_editor") and effective_parse_snapshot_id),
            can_jump_to_chunk=bool(effective_parse_snapshot_id),
            can_decide_ticket=bool(user.has_role("reviewer") and effective_ticket_status == "pending"),
            can_approve=bool(user.has_role("reviewer") and effective_ticket_status == "pending"),
            can_reject=bool(user.has_role("reviewer") and effective_ticket_status == "pending"),
            can_upload=bool(user.has_role("uploader")),
            can_archive=can_archive,
            can_retract=can_retract,
            can_reindex=can_reindex,
        )

        projection_freshness = WorkspaceProjectionFreshnessView(
            ticket_projection_updated_at=_iso(ticket_proj.projection_updated_at if ticket_proj else None),
            ticket_is_stale=bool(ticket_proj.is_stale) if ticket_proj else True,
            document_projection_updated_at=_iso(document_proj.projection_updated_at if document_proj else None),
            document_is_stale=bool(document_proj.is_stale) if document_proj else True,
        )

        return WorkspaceDetailView(
            ticket_id=ticket_proj.ticket_id if ticket_proj is not None else ticket_id,
            ticket=ticket_view,
            document=document_view,
            task=task_view,
            source_file=results["source_file"],
            parse_snapshot=parse_snapshot,
            chunks=results["chunks"],
            chunk_edits=results["chunk_edits"],
            agent_review=agent_review,
            capabilities=capabilities,
            projection_freshness=projection_freshness,
            degraded_parts=degraded_parts,
            trace_id=trace_id,
        ).model_dump()
