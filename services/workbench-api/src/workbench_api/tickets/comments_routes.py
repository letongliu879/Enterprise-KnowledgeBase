"""Ticket comments CRUD routes.

Comments are simple SQL rows owned by the workbench-api directly
(not projected from downstream services).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from reality_rag_persistence.models import TicketCommentModel

from ..deps import get_db, require_auth, CurrentUser
from ..errors import not_found, forbidden, bad_request
from ..projections.repository import TicketProjectionRepository

router = APIRouter()


class CreateCommentRequest(BaseModel):
    content: str


class UpdateCommentRequest(BaseModel):
    content: str


@router.get("/workbench/tickets/{ticket_id}/comments")
def list_ticket_comments(
    ticket_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """List all comments for a ticket."""
    # Verify ticket exists
    ticket_repo = TicketProjectionRepository(db)
    ticket = ticket_repo.get(ticket_id)
    if ticket is None:
        raise not_found("Ticket not found")
    if not user.can_access_collection(ticket.collection_id):
        raise not_found("Ticket not found")

    comments = (
        db.query(TicketCommentModel)
        .filter_by(ticket_id=ticket_id, tenant_id=user.tenant_id)
        .order_by(TicketCommentModel.created_at.asc())
        .all()
    )
    return {
        "items": [
            {
                "comment_id": c.comment_id,
                "ticket_id": c.ticket_id,
                "user_id": c.user_id,
                "content": c.content,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in comments
        ],
        "total": len(comments),
    }


@router.post("/workbench/tickets/{ticket_id}/comments", status_code=201)
def create_ticket_comment(
    ticket_id: str,
    req: CreateCommentRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Create a comment on a ticket."""
    if not req.content or not req.content.strip():
        raise bad_request("Comment content cannot be empty")

    # Verify ticket exists
    ticket_repo = TicketProjectionRepository(db)
    ticket = ticket_repo.get(ticket_id)
    if ticket is None:
        raise not_found("Ticket not found")
    if not user.can_access_collection(ticket.collection_id):
        raise not_found("Ticket not found")

    now = datetime.now(timezone.utc)
    comment = TicketCommentModel(
        comment_id=f"cmt_{uuid.uuid4().hex[:12]}",
        ticket_id=ticket_id,
        tenant_id=user.tenant_id,
        collection_id=ticket.collection_id,
        user_id=user.user_id,
        content=req.content.strip(),
        created_at=now,
        updated_at=now,
    )
    db.add(comment)
    db.commit()

    return {
        "comment_id": comment.comment_id,
        "ticket_id": comment.ticket_id,
        "user_id": comment.user_id,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
    }


@router.patch("/workbench/comments/{comment_id}")
def update_comment(
    comment_id: str,
    req: UpdateCommentRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Update own comment."""
    comment = db.query(TicketCommentModel).filter_by(comment_id=comment_id).first()
    if comment is None:
        raise not_found("Comment not found")

    if comment.user_id != user.user_id or comment.tenant_id != user.tenant_id:
        raise forbidden("You can only update your own comments")

    if not req.content or not req.content.strip():
        raise bad_request("Comment content cannot be empty")

    comment.content = req.content.strip()
    comment.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "comment_id": comment.comment_id,
        "ticket_id": comment.ticket_id,
        "user_id": comment.user_id,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
    }


@router.delete("/workbench/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
):
    """Delete own comment."""
    comment = db.query(TicketCommentModel).filter_by(comment_id=comment_id).first()
    if comment is None:
        raise not_found("Comment not found")

    if comment.user_id != user.user_id or comment.tenant_id != user.tenant_id:
        raise forbidden("You can only delete your own comments")

    db.delete(comment)
    db.commit()
    return None
