"""Chunk routes."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, require_role, CurrentUser
from ..downstream_clients import IndexingClient
from ..errors import not_found
from .service import ChunkService

router = APIRouter()


@router.get("/workbench/chunks/{evidence_id}")
async def get_chunk(evidence_id: str, user: CurrentUser = Depends(require_auth)):
    service = ChunkService(IndexingClient())
    result = await service.get_chunk(evidence_id, user)
    return result


@router.patch("/workbench/chunks/{evidence_id}", status_code=202)
async def patch_chunk(evidence_id: str, req: dict, user: CurrentUser = Depends(require_role("chunk_editor"))):
    service = ChunkService(IndexingClient())
    result = await service.patch_chunk(evidence_id, req, user)
    return result
