"""Retrieval verification proxy.

Frontend uses JWT against workbench-api.
Workbench-api validates role/collection scope, then calls access service
server-side. Browser never sends X-API-Key.

Each request/response is recorded in workbench_query_runs.
"""

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, CurrentUser
from ..downstream_clients import AccessClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_unavailable, forbidden, bad_request
from ..projections.repository import QueryRunRepository

router = APIRouter()


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1)
    collection_id: str
    token_budget: int = Field(default=4096, gt=0)
    max_results: int = Field(default=10, gt=0)
    budget_policy: str = Field(default="balanced")
    application_profile_id: str = Field(default="workbench_default")
    retrieval_profile_id: str | None = Field(default=None)
    debug: str = Field(default="none")


@router.post("/workbench/retrieve")
async def retrieve(
    req: RetrieveRequest,
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Proxy retrieval request to access service with server-side credentials."""
    if not user.can_access_collection(req.collection_id):
        raise forbidden("Collection access denied")

    query_run_id = f"qr_{uuid.uuid4().hex[:16]}"
    trace_id = f"trc_{uuid.uuid4().hex[:16]}"

    access_payload: dict = {
        "query": req.query,
        "tenant_id": user.tenant_id,
        "application_profile_id": req.application_profile_id,
        "user_id": user.user_id,
        "max_results": req.max_results,
        "token_budget": req.token_budget,
        "budget_policy": req.budget_policy,
    }
    if req.retrieval_profile_id:
        access_payload["retrieval_profile_id"] = req.retrieval_profile_id
    if req.debug and req.debug != "none":
        access_payload["debug"] = req.debug

    repo = QueryRunRepository(session)
    repo.create({
        "query_run_id": query_run_id,
        "tenant_id": user.tenant_id,
        "user_id": user.user_id,
        "collection_id": req.collection_id,
        "query": req.query,
        "token_budget": req.token_budget,
        "request_json": access_payload,
        "status": "pending",
        "trace_id": trace_id,
    })
    session.commit()

    started_at = time.monotonic()
    try:
        access_client = AccessClient()
        result = await access_client.retrieve(access_payload)
        latency_ms = int((time.monotonic() - started_at) * 1000)

        knowledge_context = result.get("knowledge_context", {})
        repo.update(query_run_id, {
            "access_response_json": result,
            "knowledge_context_json": knowledge_context,
            "latency_ms": latency_ms,
            "status": "success",
            "error_code": None,
            "error_message": None,
        })
        session.commit()

        return {
            "query_run_id": query_run_id,
            "knowledge_context": knowledge_context,
            "latency_ms": latency_ms,
            "trace_id": trace_id,
            "evidence_items": knowledge_context.get("evidence_items", []),
            "token_budget_used": knowledge_context.get("token_budget_used", 0),
        }
    except DownstreamError as e:
        latency_ms = int((time.monotonic() - started_at) * 1000)
        repo.update(query_run_id, {
            "latency_ms": latency_ms,
            "status": "failed",
            "error_code": e.code,
            "error_message": e.message,
        })
        session.commit()
        raise downstream_unavailable(f"Access retrieval failed: {e.message}")


@router.get("/workbench/query-runs")
async def list_query_runs(
    collection_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    repo = QueryRunRepository(session)
    items, total = repo.list(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        collection_id=collection_id,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [
            {
                "query_run_id": item.query_run_id,
                "collection_id": item.collection_id,
                "query": item.query,
                "token_budget": item.token_budget,
                "latency_ms": item.latency_ms,
                "cache_hit": item.cache_hit,
                "status": item.status,
                "error_code": item.error_code,
                "error_message": item.error_message,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
        "total": total,
    }


@router.get("/workbench/query-runs/{query_run_id}")
async def get_query_run(
    query_run_id: str,
    session: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    repo = QueryRunRepository(session)
    item = repo.get(query_run_id)
    if item is None or item.tenant_id != user.tenant_id:
        from ..errors import not_found
        raise not_found("Query run not found")
    if not user.can_access_collection(item.collection_id):
        raise forbidden("Collection access denied")
    return {
        "query_run_id": item.query_run_id,
        "tenant_id": item.tenant_id,
        "user_id": item.user_id,
        "collection_id": item.collection_id,
        "query": item.query,
        "token_budget": item.token_budget,
        "request_json": item.request_json,
        "access_response_json": item.access_response_json,
        "knowledge_context_json": item.knowledge_context_json,
        "latency_ms": item.latency_ms,
        "cache_hit": item.cache_hit,
        "status": item.status,
        "error_code": item.error_code,
        "error_message": item.error_message,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
