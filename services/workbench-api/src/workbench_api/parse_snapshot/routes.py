"""Parse snapshot routes."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..downstream_clients import IndexingClient
from .service import ParseSnapshotService

router = APIRouter()


@router.get("/workbench/parse-snapshots/{parse_snapshot_id}")
async def get_parse_snapshot(parse_snapshot_id: str, user: CurrentUser = Depends(require_auth)):
    service = ParseSnapshotService(IndexingClient())
    result = await service.get_snapshot(parse_snapshot_id, user)
    return result


@router.get("/workbench/parse-snapshots/{parse_snapshot_id}/chunks")
async def get_parse_snapshot_chunks(parse_snapshot_id: str, page: int = 1, page_size: int = 50, user: CurrentUser = Depends(require_auth)):
    service = ParseSnapshotService(IndexingClient())
    result = await service.get_snapshot_chunks(parse_snapshot_id, page, page_size, user)
    return result
