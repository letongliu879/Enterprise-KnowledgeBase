"""Retrieval-profile proxy routes — frontend calls workbench, workbench delegates to admin."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..downstream_clients import AdminClient
from ..errors import downstream_not_implemented

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
    except Exception as e:
        raise downstream_not_implemented(f"Admin retrieval profiles API unavailable: {e}")
    return result
