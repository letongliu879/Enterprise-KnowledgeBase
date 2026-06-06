"""FastAPI routes for the Agent Review Worker.

This module defines all HTTP endpoints. The router is created and populated
before being included in the FastAPI app, avoiding the module-level ordering
bug where app.include_router() was called before routes were registered.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from reality_rag_contracts import HealthResponse

from intake_runtime.stages.schemas import ReviewStageInput
from intake_runtime.stages.pure_stages import run_review_stage
from intake_runtime.agent_review_cache import get_agent_review_cache
from intake_runtime.agent_reviewer import get_agent_reviewer, AgentReviewConfigurationError

router = APIRouter()


class ReviewRunRequest(BaseModel):
    intake_job_id: str = ""
    collection_id: str = ""
    preliminary_doc_id: str = ""
    logical_document_id: str = ""
    canonical_content: str = ""
    collection_authority_level: int = 0
    review_model: str = ""


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="agent-review-worker",
        version="0.1.0",
    )


@router.post("/internal/review/run")
async def run_review(request: ReviewRunRequest) -> dict:
    try:
        inp = ReviewStageInput(
            schema_version="v1",
            intake_job_id=request.intake_job_id,
            collection_id=request.collection_id,
            preliminary_doc_id=request.preliminary_doc_id,
            logical_document_id=request.logical_document_id,
            canonical_content=request.canonical_content,
            collection_authority_level=request.collection_authority_level,
            review_model=request.review_model,
        )
        reviewer = get_agent_reviewer()
        cache = get_agent_review_cache()
        out = run_review_stage(inp, reviewer, cache)
        return {
            "schema_version": out.schema_version,
            "input_hash": out.input_hash,
            "result_hash": out.result_hash,
            "decision": out.agent_review.decision.value if out.agent_review and out.agent_review.decision else None,
            "confidence": out.agent_review.confidence if out.agent_review else None,
            "cache_hit": out.cache_hit,
            "llm_call_records": out.review_context.get("llm_call_records", []),
        }
    except AgentReviewConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
