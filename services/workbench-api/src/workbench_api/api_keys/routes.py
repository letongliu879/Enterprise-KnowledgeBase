"""API key proxy routes — frontend calls workbench, workbench delegates to admin."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..downstream_clients import AdminClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, not_found

router = APIRouter(prefix="/workbench/api-keys")


@router.get("")
async def list_api_keys(user: CurrentUser = Depends(require_auth)):
    client = AdminClient()
    try:
        result = await client.list_api_keys(
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin API keys API unavailable: {e.message}")
        raise downstream_unavailable(f"Admin API keys API error: {e.message}")
    return result


@router.post("")
async def create_api_key(body: dict, user: CurrentUser = Depends(require_auth)):
    client = AdminClient()
    try:
        result = await client.create_api_key(
            body,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin API keys API unavailable: {e.message}")
        raise downstream_unavailable(f"Admin API keys API error: {e.message}")
    return result


@router.get("/{api_key_id}")
async def get_api_key_detail(api_key_id: str, user: CurrentUser = Depends(require_auth)):
    client = AdminClient()
    try:
        result = await client.get_api_key(
            api_key_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin API keys API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"API key not found: {api_key_id}")
        raise downstream_unavailable(f"Admin API keys API error: {e.message}")
    return result
