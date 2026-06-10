"""Ticket routes.

List endpoints read from SQL projection (no downstream fan-out).
Detail endpoints read projection first, with optional approval fallback.
"""

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, require_role, CurrentUser
from ..downstream_clients import ApprovalClient
from ..errors import not_found
from ..projections.projector import ProjectionProjector
from ..projections.repository import TicketProjectionRepository
from .models import TicketDecisionRequest
from .service import TicketService

router = APIRouter(prefix="/workbench/tickets")


def _get_service() -> TicketService:
    return TicketService(ApprovalClient())


def _normalize_projection_finding(finding) -> dict:
    return {
        "finding_id": finding.finding_id,
        "severity": finding.severity or "medium",
        "category": finding.category or "",
        "problem_summary": finding.problem_summary or "",
        "source_quote": finding.source_quote,
        "evidence_id": finding.evidence_id,
        "doc_id": finding.doc_id,
        "source_file_id": finding.source_file_id,
        "parse_snapshot_id": finding.parse_snapshot_id,
        "page_from": finding.page_from,
        "page_to": finding.page_to,
        "state": finding.state,
        "confidence": finding.confidence,
    }


def _normalize_approval_agent_review(result: dict) -> dict:
    findings_payload = result.get("findings", [])
    findings = []
    for finding in findings_payload if isinstance(findings_payload, list) else []:
        if not isinstance(finding, dict):
            continue
        findings.append({
            "finding_id": finding.get("finding_id"),
            "severity": finding.get("severity", "medium"),
            "category": finding.get("category", ""),
            "problem_summary": finding.get("problem_summary", ""),
            "source_quote": finding.get("source_quote"),
            "evidence_id": finding.get("evidence_id"),
            "doc_id": finding.get("doc_id"),
            "source_file_id": finding.get("source_file_id", result.get("source_file_id")),
            "parse_snapshot_id": finding.get("parse_snapshot_id", result.get("parse_snapshot_id")),
            "page_from": finding.get("page_from"),
            "page_to": finding.get("page_to"),
            "state": finding.get("state", "open"),
            "confidence": finding.get("confidence"),
        })
    matched_count = result.get("matched_count")
    if not isinstance(matched_count, int):
        matched_count = sum(1 for finding in findings if finding.get("evidence_id"))
    unmatched_count = result.get("unmatched_count")
    if not isinstance(unmatched_count, int):
        unmatched_count = max(0, len(findings) - matched_count)
    return {
        "ticket_id": result.get("ticket_id", ""),
        "decision": result.get("decision"),
        "source_file_id": result.get("source_file_id"),
        "parse_snapshot_id": result.get("parse_snapshot_id"),
        "findings": findings,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
    }


def _ticket_raw_to_payload(raw: dict) -> dict:
    return {
        "ticket_id": raw.get("ticket_id", ""),
        "tenant_id": raw.get("tenant_id", ""),
        "collection_id": raw.get("collection_id", ""),
        "upload_id": raw.get("upload_id"),
        "source_file_id": raw.get("source_file_id"),
        "parse_snapshot_id": raw.get("parse_snapshot_id"),
        "doc_id": raw.get("doc_id") or raw.get("final_doc_id") or raw.get("preliminary_doc_id"),
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


def _projection_needs_enrichment(item) -> bool:
    return not str(item.filename or "").strip() and not str(item.title or "").strip()


async def _backfill_ticket_projection(
    *,
    repo: TicketProjectionRepository,
    db: Session,
    user: CurrentUser,
    collection_id: str | None,
    state: str | None,
) -> bool:
    approval_items = await ApprovalClient().list_tickets(
        tenant_id=user.tenant_id,
        collection_id=collection_id,
        status=state,
    )
    if not approval_items:
        return False

    projector = ProjectionProjector(db)
    applied_any = False
    now = datetime.now(timezone.utc)
    for raw in approval_items:
        raw_collection_id = str(raw.get("collection_id") or "")
        if raw_collection_id and not user.can_access_collection(raw_collection_id):
            continue
        ticket_id = str(raw.get("ticket_id") or "")
        if not ticket_id:
            continue
        existing = repo.get(ticket_id)
        version = (existing.version + 1) if existing is not None else 1
        result = projector.record_and_apply({
            "event_id": f"backfill_ticket_{ticket_id}_{uuid.uuid4().hex[:8]}",
            "event_type": "BACKFILL_TICKET",
            "tenant_id": str(raw.get("tenant_id") or user.tenant_id),
            "collection_id": raw_collection_id,
            "aggregate_type": "ticket",
            "aggregate_id": ticket_id,
            "aggregate_version": version,
            "occurred_at": now,
            "payload": _ticket_raw_to_payload(raw),
            "trace_id": f"backfill:{ticket_id}",
        })
        applied_any = applied_any or bool(result.get("applied"))

    if applied_any:
        db.commit()
    return applied_any


@router.get("")
async def list_tickets(
    collection_id: str | None = None,
    state: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """List tickets from SQL projection only. No downstream fan-out."""
    repo = TicketProjectionRepository(db)
    offset = (page - 1) * page_size

    collection_ids = None
    if collection_id:
        if not user.can_access_collection(collection_id):
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        collection_ids = [collection_id]
    else:
        collection_ids = None if "*" in user.allowed_collections else (user.allowed_collections or None)

    items, total = repo.list(
        tenant_id=user.tenant_id,
        collection_ids=collection_ids,
        state=status or state,
        offset=offset,
        limit=page_size,
    )

    if total == 0 or any(_projection_needs_enrichment(item) for item in items):
        repaired = await _backfill_ticket_projection(
            repo=repo,
            db=db,
            user=user,
            collection_id=collection_id,
            state=status or state,
        )
        if repaired:
            items, total = repo.list(
                tenant_id=user.tenant_id,
                collection_ids=collection_ids,
                state=status or state,
                offset=offset,
                limit=page_size,
            )

    return {
        "items": [
            {
                "ticket_id": item.ticket_id,
                "collection_id": item.collection_id,
                "status": item.state,
                "priority": item.priority,
                "assignee_user_id": item.assignee_user_id,
                "title": item.title,
                "filename": item.filename,
                "agent_decision": item.agent_decision,
                "agent_risk_level": item.agent_risk_level,
                "agent_finding_count": item.agent_finding_count,
                "agent_blocking_finding_count": item.agent_blocking_finding_count,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                "projection_updated_at": item.projection_updated_at.isoformat() if item.projection_updated_at else None,
                "is_stale": item.is_stale,
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Get ticket details. Reads projection first; falls back to approval if stale/missing."""
    repo = TicketProjectionRepository(db)
    projection = repo.get(ticket_id)

    if projection and not projection.is_stale and not _projection_needs_enrichment(projection):
        # Validate access
        if not user.can_access_collection(projection.collection_id):
            raise not_found("Ticket not found")
        return {
            "ticket_id": projection.ticket_id,
            "collection_id": projection.collection_id,
            "status": projection.state,
            "priority": projection.priority,
            "assignee_user_id": projection.assignee_user_id,
            "title": projection.title,
            "filename": projection.filename,
            "upload_id": projection.upload_id,
            "source_file_id": projection.source_file_id,
            "parse_snapshot_id": projection.parse_snapshot_id,
            "doc_id": projection.doc_id,
            "agent_decision": projection.agent_decision,
            "agent_risk_level": projection.agent_risk_level,
            "agent_finding_count": projection.agent_finding_count,
            "agent_blocking_finding_count": projection.agent_blocking_finding_count,
            "tenant_id": projection.tenant_id,
            "created_at": projection.created_at.isoformat() if projection.created_at else None,
            "updated_at": projection.updated_at.isoformat() if projection.updated_at else None,
            "projection_updated_at": projection.projection_updated_at.isoformat() if projection.projection_updated_at else None,
            "is_stale": projection.is_stale,
            "source": "projection",
        }

    if projection and _projection_needs_enrichment(projection):
        await _backfill_ticket_projection(
            repo=repo,
            db=db,
            user=user,
            collection_id=projection.collection_id,
            state=projection.state,
        )
        projection = repo.get(ticket_id)
        if projection and not projection.is_stale and not _projection_needs_enrichment(projection):
            if not user.can_access_collection(projection.collection_id):
                raise not_found("Ticket not found")
            return {
                "ticket_id": projection.ticket_id,
                "collection_id": projection.collection_id,
                "status": projection.state,
                "priority": projection.priority,
                "assignee_user_id": projection.assignee_user_id,
                "title": projection.title,
                "filename": projection.filename,
                "upload_id": projection.upload_id,
                "source_file_id": projection.source_file_id,
                "parse_snapshot_id": projection.parse_snapshot_id,
                "doc_id": projection.doc_id,
                "agent_decision": projection.agent_decision,
                "agent_risk_level": projection.agent_risk_level,
                "agent_finding_count": projection.agent_finding_count,
                "agent_blocking_finding_count": projection.agent_blocking_finding_count,
                "tenant_id": projection.tenant_id,
                "created_at": projection.created_at.isoformat() if projection.created_at else None,
                "updated_at": projection.updated_at.isoformat() if projection.updated_at else None,
                "projection_updated_at": projection.projection_updated_at.isoformat() if projection.projection_updated_at else None,
                "is_stale": projection.is_stale,
                "source": "projection",
            }

    # Fallback to approval service
    service = _get_service()
    detail = await service.get_ticket(ticket_id, user)
    return {**detail.model_dump(), "source": "approval"}


@router.post("/{ticket_id}/decide")
async def decide_ticket(
    ticket_id: str,
    req: TicketDecisionRequest,
    user: CurrentUser = Depends(require_role("reviewer")),
):
    """Submit ticket decision. Still calls approval service; projection updated via callback."""
    service = _get_service()
    result = await service.decide_ticket(ticket_id, req, user)
    return result


@router.get("/{ticket_id}/agent-review")
async def get_agent_review(
    ticket_id: str,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Get agent review findings. Reads from projection first."""
    from ..projections.repository import AgentReviewProjectionRepository

    repo = AgentReviewProjectionRepository(db)
    ticket_projection = TicketProjectionRepository(db).get(ticket_id)
    if ticket_projection and not user.can_access_collection(ticket_projection.collection_id):
        raise not_found("Ticket not found")
    findings = repo.list_by_ticket(ticket_id, user.tenant_id)

    if findings:
        matched_count = sum(1 for finding in findings if finding.evidence_id)
        return {
            "ticket_id": ticket_id,
            "decision": ticket_projection.agent_decision if ticket_projection else None,
            "source_file_id": ticket_projection.source_file_id if ticket_projection else findings[0].source_file_id,
            "parse_snapshot_id": ticket_projection.parse_snapshot_id if ticket_projection else findings[0].parse_snapshot_id,
            "findings": [_normalize_projection_finding(finding) for finding in findings],
            "matched_count": matched_count,
            "unmatched_count": max(0, len(findings) - matched_count),
            "source": "projection",
        }

    # Fallback to approval service
    service = _get_service()
    result = await service.get_agent_review(ticket_id, user)
    return {**_normalize_approval_agent_review(result), "source": "approval"}
