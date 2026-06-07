"""Parse snapshot routes."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..deps import CurrentUser, get_db, require_auth
from ..downstream_clients import IndexingClient, IntakeClient
from ..upload_sessions.repository import UploadSessionRepository
from .service import ParseSnapshotService

router = APIRouter()


def _content_disposition(filename: str) -> str:
    ascii_fallback = "".join(ch if ord(ch) < 128 else "_" for ch in filename) or "source.bin"
    utf8_name = quote(filename, safe="")
    return f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_name}"


def _get_service(session: Session = Depends(get_db)) -> ParseSnapshotService:
    return ParseSnapshotService(
        IndexingClient(),
        IntakeClient(),
        session,
        UploadSessionRepository(session),
    )


@router.get("/workbench/parse-snapshots/{parse_snapshot_id}")
async def get_parse_snapshot(parse_snapshot_id: str, service: ParseSnapshotService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    result = await service.get_snapshot(parse_snapshot_id, user)
    return result


@router.get("/workbench/parse-snapshots/{parse_snapshot_id}/chunks")
async def get_parse_snapshot_chunks(parse_snapshot_id: str, page: int = 1, page_size: int = 50, service: ParseSnapshotService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    result = await service.get_snapshot_chunks(parse_snapshot_id, page, page_size, user)
    return result


@router.get("/workbench/parse-snapshots/{parse_snapshot_id}/source")
async def get_parse_snapshot_source(
    parse_snapshot_id: str,
    service: ParseSnapshotService = Depends(_get_service),
    user: CurrentUser = Depends(require_auth),
):
    filename, content_type, content = await service.get_snapshot_source(
        parse_snapshot_id,
        user,
    )
    headers = {
        "Content-Disposition": _content_disposition(filename),
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type=content_type, headers=headers)
