"""Workspace detail aggregation routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..chunk_edits.repository import ChunkEditRepository
from ..deps import get_db, require_auth, CurrentUser
from ..downstream_clients.clients import ApprovalClient, IndexingClient, IntakeClient
from ..errors import not_found
from ..projections.repository import (
    AgentReviewProjectionRepository,
    DocumentProjectionRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)
from .models import WorkspaceDetailView
from .service import WorkspaceService

router = APIRouter()

_intake_client: IntakeClient | None = None
_approval_client: ApprovalClient | None = None
_indexing_client: IndexingClient | None = None


def init_workspace_clients() -> None:
    global _intake_client, _approval_client, _indexing_client
    _intake_client = IntakeClient()
    _approval_client = ApprovalClient()
    _indexing_client = IndexingClient()


async def close_workspace_clients() -> None:
    global _intake_client, _approval_client, _indexing_client
    if _intake_client is not None:
        await _intake_client.close()
    if _approval_client is not None:
        await _approval_client.close()
    if _indexing_client is not None:
        await _indexing_client.close()


def _get_service(session: Session = Depends(get_db)) -> WorkspaceService:
    return WorkspaceService(
        task_repo=TaskProjectionRepository(session),
        ticket_repo=TicketProjectionRepository(session),
        document_repo=DocumentProjectionRepository(session),
        agent_review_repo=AgentReviewProjectionRepository(session),
        chunk_edit_repo=ChunkEditRepository(session),
        intake_client=_intake_client or IntakeClient(),
        approval_client=_approval_client or ApprovalClient(),
        indexing_client=_indexing_client or IndexingClient(),
    )


@router.get("/workbench/tickets/{ticket_id}/workspace", response_model=WorkspaceDetailView)
async def get_workspace(
    ticket_id: str,
    service: WorkspaceService = Depends(_get_service),
    user: CurrentUser = Depends(require_auth),
):
    trace_id = f"trc_{uuid.uuid4().hex[:16]}"
    result = await service.get_workspace(ticket_id, user, trace_id)
    if result.get("error") == "ticket_not_found":
        raise not_found("Ticket not found")
    if result.get("error") == "collection_access_denied":
        from ..errors import forbidden
        raise forbidden("Collection access denied")
    return result
