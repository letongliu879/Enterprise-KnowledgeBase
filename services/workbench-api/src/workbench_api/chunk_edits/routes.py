"""Chunk edit routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_auth, require_role, CurrentUser
from ..downstream_clients import IndexingClient
from ..errors import not_found, forbidden, conflict
from .models import ChunkEditCreateRequest, ChunkEditUpdateRequest
from .repository import ChunkEditRepository
from .service import ChunkEditService

router = APIRouter()


def _get_service(session: Session = Depends(get_db)) -> ChunkEditService:
    return ChunkEditService(ChunkEditRepository(session), IndexingClient())


@router.post("/workbench/parse-snapshots/{parse_snapshot_id}/chunk-edits", status_code=201)
def create_chunk_edit(parse_snapshot_id: str, req: ChunkEditCreateRequest, service: ChunkEditService = Depends(_get_service), user: CurrentUser = Depends(require_role("chunk_editor"))):
    # Source file ID is typically passed via request or derived; here we use a placeholder
    source_file_id = req.base_evidence_id.split("_")[0] if "_" in req.base_evidence_id else "unknown"
    edit = service.create_chunk_edit(
        parse_snapshot_id=parse_snapshot_id,
        source_file_id=source_file_id,
        tenant_id=user.tenant_id,
        collection_id="col_default",
        req=req,
        user=user,
    )
    return edit.model_dump()


@router.get("/workbench/parse-snapshots/{parse_snapshot_id}/chunk-edits")
def list_chunk_edits(parse_snapshot_id: str, service: ChunkEditService = Depends(_get_service), user: CurrentUser = Depends(require_auth)):
    edits = service.list_chunk_edits(parse_snapshot_id)
    return {"items": [e.model_dump() for e in edits], "total": len(edits)}


@router.put("/workbench/chunk-edits/{chunk_edit_id}")
def update_chunk_edit(chunk_edit_id: str, req: ChunkEditUpdateRequest, service: ChunkEditService = Depends(_get_service), user: CurrentUser = Depends(require_role("chunk_editor"))):
    edit = service.update_chunk_edit(chunk_edit_id, req, user)
    if not edit:
        raise not_found("Chunk edit not found or not owned by user")
    return edit.model_dump()


@router.delete("/workbench/chunk-edits/{chunk_edit_id}", status_code=204)
def delete_chunk_edit(chunk_edit_id: str, service: ChunkEditService = Depends(_get_service), user: CurrentUser = Depends(require_role("chunk_editor"))):
    if not service.delete_chunk_edit(chunk_edit_id, user):
        raise not_found("Chunk edit not found or not owned by user")


@router.post("/workbench/chunk-edits/{chunk_edit_id}/submit", status_code=200)
async def submit_chunk_edit(chunk_edit_id: str, service: ChunkEditService = Depends(_get_service), user: CurrentUser = Depends(require_role("chunk_editor"))):
    from ..downstream_clients.errors import DownstreamError
    try:
        edit = await service.submit_chunk_edit(chunk_edit_id, user)
    except DownstreamError as e:
        raise conflict(f"Indexing service rejected submission: {e.message}")
    if not edit:
        raise not_found("Chunk edit not found or not owned by user")
    return edit.model_dump()
