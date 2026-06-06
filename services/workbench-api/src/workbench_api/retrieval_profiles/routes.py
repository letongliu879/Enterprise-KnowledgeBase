"""Retrieval-profile proxy routes — frontend calls workbench, workbench delegates to admin."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..downstream_clients import AdminClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, conflict

router = APIRouter(prefix="/workbench/retrieval-profiles")


@router.get("")
async def list_retrieval_profiles(
    state: str | None = None,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.list_retrieval_profiles(
            state,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin retrieval profiles API unavailable: {e.message}")
        elif e.code == "CONFLICT":
            raise conflict(e.message)
        else:
            raise downstream_unavailable(f"Admin retrieval profiles API error: {e.message}")
    return result
