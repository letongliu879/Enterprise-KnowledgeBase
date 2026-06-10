"""FastAPI application for the Approval Service.

This service owns:
  - approval_tickets
  - approval_audit_log
  - final_doc_id generation
  - system decision (auto approve / auto reject)
"""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from reality_rag_contracts import AgentReviewView, HealthResponse, PublishStatus, StageName
from reality_rag_persistence.database import get_session

from .approval_domain import ApprovalService, system_decide
from .review_artifacts import (
    build_ticket_event_payload,
    load_review_artifact_payload,
    normalize_agent_review_findings,
    resolve_ticket_tenant_id,
    utc_now_iso,
)

app = FastAPI(
    title="Approval Service",
    description="Approval ticket and audit management for Reality-RAG",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="approval-service",
        version="0.1.0",
    )


# ── System Decide ─────────────────────────────────────────────────────

class SystemDecideRequest(BaseModel):
    quality_report: dict | None = None
    agent_review: dict | None = None


@app.post("/internal/approval/system-decide")
async def decide(request: SystemDecideRequest) -> dict:
    """Pure function: decide publish_status from quality report and agent review."""
    from reality_rag_contracts import QualityReport, AgentReview

    qr = QualityReport.model_validate(request.quality_report) if request.quality_report else None
    ar = AgentReview.model_validate(request.agent_review) if request.agent_review else None
    result = system_decide(qr, ar)
    return {"publish_status": result.value}


# ── Auto Approve ──────────────────────────────────────────────────────

class AutoApproveRequest(BaseModel):
    intake_job_id: str
    preliminary_doc_id: str
    collection_id: str
    logical_document_id: str
    version: int
    confirmed_tags: list[str] | None = None


@app.post("/internal/approval/auto-approve")
async def auto_approve(request: AutoApproveRequest) -> dict:
    session = get_session()
    try:
        svc = ApprovalService(session)
        ticket = svc.submit_auto_approve(
            intake_job_id=request.intake_job_id,
            preliminary_doc_id=request.preliminary_doc_id,
            collection_id=request.collection_id,
            logical_document_id=request.logical_document_id,
            version=request.version,
            confirmed_tags=request.confirmed_tags,
        )
        session.commit()
        return ticket.model_dump(mode="json")
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


# ── Auto Reject ───────────────────────────────────────────────────────

class AutoRejectRequest(BaseModel):
    intake_job_id: str
    preliminary_doc_id: str
    collection_id: str
    rejection_reason: str


@app.post("/internal/approval/auto-reject")
async def auto_reject(request: AutoRejectRequest) -> dict:
    session = get_session()
    try:
        svc = ApprovalService(session)
        ticket = svc.submit_auto_reject(
            intake_job_id=request.intake_job_id,
            preliminary_doc_id=request.preliminary_doc_id,
            collection_id=request.collection_id,
            rejection_reason=request.rejection_reason,
        )
        session.commit()
        return ticket.model_dump(mode="json")
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


# ── Manual Lifecycle ──────────────────────────────────────────────────

class CreatePendingRequest(BaseModel):
    intake_job_id: str
    preliminary_doc_id: str
    collection_id: str
    routing_recommendation: str = "require_approval"


@app.post("/internal/approval/pending")
async def create_pending(request: CreatePendingRequest) -> dict:
    session = get_session()
    try:
        svc = ApprovalService(session)
        ticket = svc.create_pending(
            intake_job_id=request.intake_job_id,
            preliminary_doc_id=request.preliminary_doc_id,
            collection_id=request.collection_id,
            routing_recommendation=request.routing_recommendation,
        )
        session.commit()
        return ticket.model_dump(mode="json")
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class ApproveRequest(BaseModel):
    actor_id: str
    confirmed_tags: list[str] | None = None
    version_decision: str | None = None
    supersedes_final_doc_id: str | None = None


@app.post("/internal/approval/{ticket_id}/approve")
async def approve(ticket_id: str, request: ApproveRequest) -> dict:
    from reality_rag_contracts import VersionDecision

    session = get_session()
    try:
        svc = ApprovalService(session)
        vd = VersionDecision(request.version_decision) if request.version_decision else None
        ticket = svc.approve(
            ticket_id=ticket_id,
            actor_id=request.actor_id,
            confirmed_tags=request.confirmed_tags,
            version_decision=vd,
            supersedes_final_doc_id=request.supersedes_final_doc_id,
        )
        session.commit()
        return ticket.model_dump(mode="json")
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class RejectRequest(BaseModel):
    actor_id: str
    rejection_reason: str


@app.post("/internal/approval/{ticket_id}/reject")
async def reject(ticket_id: str, request: RejectRequest) -> dict:
    session = get_session()
    try:
        svc = ApprovalService(session)
        ticket = svc.reject(
            ticket_id=ticket_id,
            actor_id=request.actor_id,
            rejection_reason=request.rejection_reason,
        )
        session.commit()
        return ticket.model_dump(mode="json")
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


class ReturnRequest(BaseModel):
    actor_id: str
    return_target_stage: str
    return_reason: str


@app.post("/internal/approval/{ticket_id}/return")
async def return_to_stage(ticket_id: str, request: ReturnRequest) -> dict:
    session = get_session()
    try:
        svc = ApprovalService(session)
        returned, new_pending = svc.return_to_stage(
            ticket_id=ticket_id,
            actor_id=request.actor_id,
            return_target_stage=request.return_target_stage,
            return_reason=request.return_reason,
        )
        session.commit()
        return {
            "returned": returned.model_dump(mode="json"),
            "new_pending": new_pending.model_dump(mode="json"),
        }
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@app.post("/internal/approval/{ticket_id}/expire")
async def expire(ticket_id: str) -> dict:
    session = get_session()
    try:
        svc = ApprovalService(session)
        ticket = svc.expire(ticket_id=ticket_id)
        session.commit()
        return ticket.model_dump(mode="json")
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        session.close()


@app.get("/internal/approval/{intake_job_id}/history")
async def get_ticket_history(intake_job_id: str) -> list[dict]:
    session = get_session()
    try:
        svc = ApprovalService(session)
        tickets = svc.get_ticket_history(intake_job_id)
        return [t.model_dump(mode="json") for t in tickets]
    finally:
        session.close()


# -- New internal owner APIs for workbench consumption --------------------------------


class ApprovalTicketView(BaseModel):
    ticket_id: str
    intake_job_id: str
    collection_id: str
    tenant_id: str
    state: str
    title: str | None = None
    filename: str | None = None
    preliminary_doc_id: str
    final_doc_id: str | None = None
    source_file_id: str | None = None
    parse_snapshot_id: str | None = None
    agent_review_ref: str | None = None
    decision: str | None = None
    decision_reason: str | None = None
    decided_by: str | None = None
    confirmed_tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    decided_at: str | None = None


class DecideTicketRequest(BaseModel):
    command_id: str
    trace_id: str
    idempotency_key: str
    actor: str
    tenant_id: str
    collection_id: str
    target_type: str = "ticket"
    target_id: str
    payload: dict


# In-memory idempotency store for decisions
# Keyed by ticket_id to prevent cross-ticket replay with the same idempotency_key.
_decision_idempotency: dict[str, dict[str, dict]] = {}  # ticket_id -> idempotency_key -> decision result


def _ticket_to_view(ticket: ApprovalTicket, *, session=None) -> ApprovalTicketView:
    owns_session = session is None
    if session is None:
        session = get_session()
    try:
        payload = build_ticket_event_payload(session, ticket)
        tenant_id = resolve_ticket_tenant_id(session, ticket)
        return ApprovalTicketView(
            ticket_id=ticket.ticket_id,
            intake_job_id=ticket.intake_job_id,
            collection_id=ticket.collection_id,
            tenant_id=tenant_id,
            state=ticket.state.value,
            title=payload.get("title"),
            filename=payload.get("filename"),
            preliminary_doc_id=ticket.preliminary_doc_id,
            final_doc_id=ticket.final_doc_id,
            source_file_id=payload.get("source_file_id"),
            parse_snapshot_id=payload.get("parse_snapshot_id"),
            agent_review_ref=payload.get("agent_review_ref"),
            decision=ticket.decision,
            decision_reason=ticket.decision_reason,
            decided_by=ticket.decision_actor,
            confirmed_tags=ticket.confirmed_tags or [],
            created_at=ticket.created_at.isoformat() if ticket.created_at else _utc_now(),
            updated_at=ticket.created_at.isoformat() if ticket.created_at else _utc_now(),
            decided_at=ticket.decided_at.isoformat() if ticket.decided_at else None,
        )
    finally:
        if owns_session:
            session.close()


def _utc_now() -> str:
    return utc_now_iso()


_load_review_artifact_payload = load_review_artifact_payload


def _build_agent_review_artifact(ticket_id: str, ticket, payload: dict) -> AgentReviewView:
    agent_review = payload.get("agent_review", {}) if isinstance(payload.get("agent_review"), dict) else {}
    review_context = payload.get("review_context", {}) if isinstance(payload.get("review_context"), dict) else {}
    llm_records = review_context.get("llm_call_records", []) if isinstance(review_context.get("llm_call_records"), list) else []
    anchored_findings = agent_review.get("anchored_findings", []) if isinstance(agent_review.get("anchored_findings"), list) else []
    findings = normalize_agent_review_findings(
        anchored_findings,
        ticket_id=ticket_id,
        doc_id=ticket.final_doc_id or ticket.preliminary_doc_id,
        source_file_id=payload.get("source_file_id"),
        parse_snapshot_id=payload.get("parse_snapshot_id"),
    )
    matched_count = sum(1 for finding in findings if finding.get("evidence_id"))
    return AgentReviewView(
        ticket_id=ticket_id,
        review_run_id=payload.get("review_run_id"),
        source_file_id=payload.get("source_file_id"),
        parse_snapshot_id=payload.get("parse_snapshot_id"),
        decision=str(agent_review.get("decision", "REVIEW") or "REVIEW").upper(),
        findings=findings,
        matched_count=matched_count,
        unmatched_count=max(0, len(findings) - matched_count),
        model=str(payload.get("review_model", "") or "") or None,
        prompt_version=str(payload.get("prompt_version", "") or "") or None,
        version=str(payload.get("artifact_version", "") or "") or None,
        artifact_schema_version=str(payload.get("artifact_schema_version", "") or "") or None,
        degraded_reason=str(payload.get("degraded_reason", "") or "") or None,
        failure_reason=str(payload.get("failure_reason", "") or "") or None,
        prompt_hash=(
            str(llm_records[0].get("request_hash", "") or "")
            if llm_records and isinstance(llm_records[0], dict)
            else None
        ),
        created_at=str(payload.get("generated_at", "") or _utc_now()),
    )


@app.get("/internal/tickets")
async def list_tickets(
    tenant_id: str,
    collection_id: str | None = None,
    state: str | None = None,
) -> dict:
    """List approval tickets. Fail closed on tenant mismatch."""
    session = get_session()
    try:
        from reality_rag_persistence.repositories.approval_tickets import ApprovalTicketRepository
        repo = ApprovalTicketRepository(session)
        all_tickets = repo.list_all()
        items = []
        for t in all_tickets:
            view = _ticket_to_view(t, session=session)
            # Fail closed: filter by tenant
            if view.tenant_id != tenant_id:
                continue
            if collection_id and view.collection_id != collection_id:
                continue
            if state and view.state != state:
                continue
            items.append(view.model_dump(mode="json"))
        return {"items": items, "total": len(items)}
    finally:
        session.close()


@app.get("/internal/tickets/{ticket_id}")
async def get_ticket_internal(ticket_id: str) -> dict:
    session = get_session()
    try:
        svc = ApprovalService(session)
        ticket = svc._ticket_repo.get(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"Ticket not found: {ticket_id}")
        return _ticket_to_view(ticket, session=session).model_dump(mode="json")
    finally:
        session.close()


@app.post("/internal/tickets/{ticket_id}/decide")
async def decide_ticket_internal(ticket_id: str, request: DecideTicketRequest) -> dict:
    """Decide an approval ticket. Idempotent by idempotency_key."""
    # Check idempotency (scoped to ticket_id to prevent cross-ticket replay)
    if request.idempotency_key in _decision_idempotency.get(ticket_id, {}):
        return _decision_idempotency[ticket_id][request.idempotency_key]

    session = get_session()
    try:
        svc = ApprovalService(session)
        ticket = svc._ticket_repo.get(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"Ticket not found: {ticket_id}")

        action = request.payload.get("action", "").lower()
        reason = request.payload.get("reason")

        if action == "approve":
            result_ticket = svc.approve(
                ticket_id=ticket_id,
                actor_id=request.actor,
                confirmed_tags=[],
            )
        elif action == "reject":
            result_ticket = svc.reject(
                ticket_id=ticket_id,
                actor_id=request.actor,
                rejection_reason=reason or "",
            )
        elif action == "return":
            result_ticket, _ = svc.return_to_stage(
                ticket_id=ticket_id,
                actor_id=request.actor,
                return_target_stage="conversion",
                return_reason=reason or "",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

        session.commit()
        view = _ticket_to_view(result_ticket, session=session)
        result = view.model_dump(mode="json")
        _decision_idempotency.setdefault(ticket_id, {})[request.idempotency_key] = result
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        session.close()


@app.get("/internal/tickets/{ticket_id}/agent-review")
async def get_agent_review_internal(ticket_id: str) -> dict:
    """Return AgentReview artifact read model. Read-only."""
    session = get_session()
    try:
        svc = ApprovalService(session)
        ticket = svc._ticket_repo.get(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"Ticket not found: {ticket_id}")
        payload = _load_review_artifact_payload(session, ticket.intake_job_id)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"Agent review artifact not found for intake_job_id: {ticket.intake_job_id}",
            )

        artifact = _build_agent_review_artifact(ticket_id, ticket, payload)
        return artifact.model_dump(mode="json")
    finally:
        session.close()
