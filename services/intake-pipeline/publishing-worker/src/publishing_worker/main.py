"""FastAPI application for the Publishing Worker.

This service owns:
  - Document persistence
  - DocumentPolicy persistence
  - Asset write (sidecar)
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from reality_rag_contracts import CanonicalMetadata, HealthResponse, StageName
from reality_rag_persistence.database import get_session
from reality_rag_persistence.outbox import OutboxDispatcher

from ingestion_worker.stage_runtime import execute_publishing_task
from ingestion_worker.stage_task_worker import make_stage_task_deliver, make_stage_task_filter
from .publishing_domain import PublishingService, update_published_document_state

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Publishing Worker",
    description="Document and policy persistence for Reality-RAG",
    version="0.1.0",
)
_outbox_dispatcher_task: asyncio.Task[None] | None = None


def _sync_lifecycle_to_retrieval(
    final_doc_id: str,
    new_state: str,
    collection_id: str,
    index_version_id: str,
    trace_id: str = "",
) -> None:
    """Sync document lifecycle change to retrieval runtime. Fail-open."""
    retrieval_url = os.environ.get("RETRIEVAL_SERVICE_URL", "").rstrip("/")
    if not retrieval_url:
        return

    try:
        import httpx

        payload = {
            "collection_id": collection_id,
            "index_version_id": index_version_id,
            "sync_mode": "lifecycle_patch",
            "final_doc_id": final_doc_id,
            "lifecycle_state": new_state,
        }
        sync_command = {
            "command_id": f"cmd_lifecycle_{uuid.uuid4().hex[:12]}",
            "trace_id": trace_id or f"trace_{uuid.uuid4().hex[:8]}",
            "idempotency_key": f"idemp_lifecycle_{collection_id}_{final_doc_id}_{new_state}_{uuid.uuid4().hex[:8]}",
            "actor": "publishing-worker",
            "tenant_id": "default",
            "target_type": "index_projection",
            "target_id": f"{collection_id}:{index_version_id}",
            "payload": payload,
        }

        resp = httpx.post(
            f"{retrieval_url}/internal/index-projections/sync",
            json=sync_command,
            timeout=10.0,
        )
        if resp.status_code >= 400:
            logger.warning("retrieval lifecycle sync failed: %s %s", resp.status_code, resp.text)
    except Exception:
        logger.warning("retrieval lifecycle sync failed with exception", exc_info=True)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="publishing-worker",
        version="0.1.0",
    )


class LifecycleRequest(BaseModel):
    state: str
    actor_id: str = "system"
    reason: str = ""
    idempotency_key: str = ""


class LifecycleResponse(BaseModel):
    success: bool
    final_doc_id: str
    previous_state: str
    new_state: str


def _get_published_document_info(final_doc_id: str) -> dict[str, str] | None:
    """Get collection_id and active_index_version for a published document."""
    from reality_rag_persistence.database import get_session
    from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository

    session = get_session()
    try:
        repo = PublishedDocumentRepository(session)
        doc = repo.get_by_final_doc_id(final_doc_id)
        if doc is None:
            return None
        return {
            "collection_id": doc.collection_id,
            "active_index_version": doc.active_index_version,
        }
    finally:
        session.close()


@app.post("/internal/published-documents/{final_doc_id}/archive")
async def archive_published_document(final_doc_id: str, request: LifecycleRequest) -> LifecycleResponse:
    try:
        from reality_rag_contracts import PublishedDocumentState
        success, previous = update_published_document_state(
            final_doc_id,
            PublishedDocumentState.ARCHIVED,
            actor_id=request.actor_id,
            reason=request.reason,
        )
        doc_info = _get_published_document_info(final_doc_id)
        if doc_info and doc_info.get("active_index_version"):
            _sync_lifecycle_to_retrieval(
                final_doc_id=final_doc_id,
                new_state="ARCHIVED",
                collection_id=doc_info["collection_id"],
                index_version_id=doc_info["active_index_version"],
            )
        return LifecycleResponse(
            success=success,
            final_doc_id=final_doc_id,
            previous_state=previous,
            new_state="ARCHIVED",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/internal/published-documents/{final_doc_id}/retract")
async def retract_published_document(final_doc_id: str, request: LifecycleRequest) -> LifecycleResponse:
    try:
        from reality_rag_contracts import PublishedDocumentState
        success, previous = update_published_document_state(
            final_doc_id,
            PublishedDocumentState.RETRACTED,
            actor_id=request.actor_id,
            reason=request.reason,
        )
        doc_info = _get_published_document_info(final_doc_id)
        if doc_info and doc_info.get("active_index_version"):
            _sync_lifecycle_to_retrieval(
                final_doc_id=final_doc_id,
                new_state="RETRACTED",
                collection_id=doc_info["collection_id"],
                index_version_id=doc_info["active_index_version"],
            )
        return LifecycleResponse(
            success=success,
            final_doc_id=final_doc_id,
            previous_state=previous,
            new_state="RETRACTED",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Persist Document and Policy ───────────────────────────────────────

class PersistRequest(BaseModel):
    canonical_metadata: dict
    collection_authority_level: int = 0


@app.post("/internal/publishing/persist")
async def persist(request: PersistRequest) -> dict:
    try:
        metadata = CanonicalMetadata.model_validate(request.canonical_metadata)
        svc = PublishingService()
        document_persisted, policy_persisted = svc.persist(
            metadata,
            collection_authority_level=request.collection_authority_level,
        )
        return {
            "document_persisted": document_persisted,
            "policy_persisted": policy_persisted,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _outbox_poll_loop() -> None:
    dispatcher = OutboxDispatcher(
        session_factory=get_session,
        deliver=make_stage_task_deliver(
            stage_name=StageName.PUBLISHING,
            consumer_id="publishing-worker:stage-task",
            worker_id="worker-publishing",
            execute=execute_publishing_task,
        ),
        should_process=make_stage_task_filter(StageName.PUBLISHING),
    )
    interval = float(os.environ.get("OUTBOX_POLL_INTERVAL_SECONDS", "5"))
    while True:
        try:
            dispatcher.poll_and_dispatch()
        except Exception:
            logger.exception("publishing outbox poll failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _outbox_dispatcher_task
    _outbox_dispatcher_task = asyncio.create_task(_outbox_poll_loop())
    try:
        yield
    finally:
        if _outbox_dispatcher_task is not None:
            _outbox_dispatcher_task.cancel()
            try:
                await _outbox_dispatcher_task
            except asyncio.CancelledError:
                pass


app.router.lifespan_context = _lifespan
