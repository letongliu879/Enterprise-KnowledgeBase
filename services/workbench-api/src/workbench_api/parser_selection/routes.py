"""Parser profile selection routes."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..downstream_clients import AdminClient, IndexingClient
from ..errors import downstream_not_implemented
from .service import ParserSelectionService

router = APIRouter(prefix="/workbench/parser-profiles")


@router.get("")
async def list_parser_profiles(collection_id: str, user: CurrentUser = Depends(require_auth)):
    if not user.can_access_collection(collection_id):
        raise downstream_not_implemented("Collection access denied")

    service = ParserSelectionService(AdminClient(), IndexingClient())
    try:
        result = await service.list_profiles(collection_id, user)
    except Exception as e:
        # If admin API is not available, return explicit error
        raise downstream_not_implemented(f"Admin collection API not yet available: {e}")

    return {
        "items": [item.model_dump() for item in result.items],
        "default_parser_profile_id": result.default_parser_profile_id,
    }
