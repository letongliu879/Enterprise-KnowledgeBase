"""Dashboard aggregation route — displays summary stats from SQL projections."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from reality_rag_persistence.models import (
    WorkbenchDocumentProjectionModel,
    WorkbenchTaskProjectionModel,
    WorkbenchTicketProjectionModel,
)

from ..deps import CurrentUser, get_db, require_auth

router = APIRouter(prefix="/workbench/dashboard")

_EMPTY = {
    "stats": {
        "today_uploads": 0,
        "pending_review_count": 0,
        "total_documents": 0,
        "stale_ratio": 0.0,
    },
    "recent_tickets": [],
}


@router.get("")
async def get_dashboard(
    user: CurrentUser = Depends(require_auth),
    session: Session = Depends(get_db),
):
    tenant_id = user.tenant_id
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        today_uploads = (
            session.query(func.count(WorkbenchTaskProjectionModel.projection_id))
            .filter(
                WorkbenchTaskProjectionModel.tenant_id == tenant_id,
                WorkbenchTaskProjectionModel.created_at >= today_start,
            )
            .scalar()
            or 0
        )

        pending_count = (
            session.query(func.count(WorkbenchTicketProjectionModel.ticket_id))
            .filter(
                WorkbenchTicketProjectionModel.tenant_id == tenant_id,
                WorkbenchTicketProjectionModel.state == "pending",
            )
            .scalar()
            or 0
        )

        total_docs = (
            session.query(func.count(WorkbenchDocumentProjectionModel.doc_id))
            .filter(WorkbenchDocumentProjectionModel.tenant_id == tenant_id)
            .scalar()
            or 0
        )

        stale_docs = (
            session.query(func.count(WorkbenchDocumentProjectionModel.doc_id))
            .filter(
                WorkbenchDocumentProjectionModel.tenant_id == tenant_id,
                WorkbenchDocumentProjectionModel.is_stale.is_(True),
            )
            .scalar()
            or 0
        )
        stale_ratio = round(stale_docs / total_docs, 2) if total_docs > 0 else 0.0

        recent_tickets_raw = (
            session.query(WorkbenchTicketProjectionModel)
            .filter(WorkbenchTicketProjectionModel.tenant_id == tenant_id)
            .order_by(WorkbenchTicketProjectionModel.created_at.desc())
            .limit(10)
            .all()
        )

        recent_tickets = []
        for t in recent_tickets_raw:
            recent_tickets.append({
                "ticket_id": t.ticket_id,
                "collection_id": t.collection_id,
                "state": t.state,
                "title": t.title or "",
                "filename": t.filename or "",
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })

        return {
            "stats": {
                "today_uploads": today_uploads,
                "pending_review_count": pending_count,
                "total_documents": total_docs,
                "stale_ratio": stale_ratio,
            },
            "recent_tickets": recent_tickets,
        }
    except OperationalError:
        return {**_EMPTY, "error": "database_unavailable"}
