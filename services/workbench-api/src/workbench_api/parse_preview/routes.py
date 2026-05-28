"""Parse preview routes."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, require_role, CurrentUser
from ..downstream_clients import IndexingClient
from .models import ParsePreviewCreateRequest
from .service import ParsePreviewService

router = APIRouter(prefix="/workbench/parse-previews")


@router.post("", status_code=202)
async def create_parse_preview(req: ParsePreviewCreateRequest, user: CurrentUser = Depends(require_role("uploader"))):
    service = ParsePreviewService(IndexingClient())
    result = await service.create_preview(req, user)
    return result.model_dump()


@router.get("/{request_id}")
async def get_parse_preview(request_id: str, user: CurrentUser = Depends(require_auth)):
    # Parse preview results are stored in indexing service
    # For now, return a pending response since downstream may not have GET endpoint
    return {
        "request_id": request_id,
        "status": "pending",
        "parse_snapshot_id": None,
        "error_message": None,
    }
