"""FastAPI application for the Approval Service.

This service owns:
  - approval_tickets
  - approval_audit_log
  - final_doc_id generation
  - system decision (auto approve / auto reject)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from reality_rag_contracts import HealthResponse, PublishStatus
from reality_rag_persistence.database import get_session

from .approval_domain import ApprovalService, system_decide

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
