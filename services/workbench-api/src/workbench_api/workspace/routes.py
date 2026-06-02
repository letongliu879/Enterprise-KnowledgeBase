"""Workspace detail aggregation routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..chunk_edits.repository import ChunkEditRepository
from ..deps import get_db, require_auth, CurrentUser
from ..downstream_clients import ApprovalClient, IndexingClient, IntakeClient
from ..errors import not_found
from ..projections.repository import (
    AgentReviewProjectionRepository,
    TaskProjectionRepository,
    TicketProjectionRepository,
)
from .service import WorkspaceService

router = APIRouter()


def _get_service(session: Session = Depends(get_db)) -> WorkspaceService:
    return WorkspaceService(
        task_repo=TaskProjectionRepository(session),
        ticket_repo=TicketProjectionRepository(session),
        agent_review_repo=AgentReviewProjectionRepository(session),
        chunk_edit_repo=ChunkEditRepository(session),
        intake_client=IntakeClient(),
        approval_client=ApprovalClient(),
        indexing_client=IndexingClient(),
    )


@router.get("/workbench/tickets/{ticket_id}/workspace")
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
