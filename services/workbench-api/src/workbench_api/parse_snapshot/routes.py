"""Parse snapshot routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import require_auth, CurrentUser, get_db
from ..downstream_clients import IndexingClient
from ..upload_sessions.repository import UploadSessionRepository
from .service import ParseSnapshotService

router = APIRouter()


def _get_service(session: Session = Depends(get_db)) -> ParseSnapshotService:
    return ParseSnapshotService(IndexingClient(), UploadSessionRepository(session))


@router.get("/workbench/parse-snapshots/{parse_snapshot_id}")
async def get_parse_snapshot(parse_snapshot_id: str, service: ParseSnapshotService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    result = await service.get_snapshot(parse_snapshot_id, user)
    return result


@router.get("/workbench/parse-snapshots/{parse_snapshot_id}/chunks")
async def get_parse_snapshot_chunks(parse_snapshot_id: str, page: int = 1, page_size: int = 50, service: ParseSnapshotService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    result = await service.get_snapshot_chunks(parse_snapshot_id, page, page_size, user)
    return result
