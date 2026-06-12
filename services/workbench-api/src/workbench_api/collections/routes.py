"""Collection proxy routes — frontend calls workbench, workbench delegates to admin."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, require_role, CurrentUser
from ..downstream_clients import AdminClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, conflict, not_found

router = APIRouter(prefix="/workbench/collections")


@router.get("")
async def list_collections(
    tenant_id: str | None = None,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.list_collections(
            tenant_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin collections API unavailable: {e.message}")
        elif e.code == "CONFLICT":
            raise conflict(e.message)
        else:
            raise downstream_unavailable(f"Admin collections API error: {e.message}")
    return result


@router.get("/{collection_id}")
async def get_collection(
    collection_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.get_collection(
            collection_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin collections API unavailable: {e.message}")
        elif e.code == "NOT_FOUND":
            raise not_found(e.message)
        elif e.code == "CONFLICT":
            raise conflict(e.message)
        else:
            raise downstream_unavailable(f"Admin collections API error: {e.message}")
    return result


@router.patch("/{collection_id}")
async def patch_collection(
    collection_id: str,
    req: dict,
    user: CurrentUser = Depends(require_role("knowledge_admin")),
):
    client = AdminClient()
    try:
        result = await client.patch_collection(
            collection_id,
            req,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin collections API unavailable: {e.message}")
        elif e.code == "NOT_FOUND":
            raise not_found(e.message)
        elif e.code == "CONFLICT":
            raise conflict(e.message)
        else:
            raise downstream_unavailable(f"Admin collections API error: {e.message}")
    return result


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    user: CurrentUser = Depends(require_role("knowledge_admin")),
):
    client = AdminClient()
    try:
        result = await client.delete_collection(
            collection_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin collections API unavailable: {e.message}")
        elif e.code == "NOT_FOUND":
            raise not_found(e.message)
        elif e.code == "CONFLICT":
            raise conflict(e.message)
        else:
            raise downstream_unavailable(f"Admin collections API error: {e.message}")
    return result


@router.post("")
async def create_collection(
    req: dict,
    user: CurrentUser = Depends(require_role("knowledge_admin")),
):
    client = AdminClient()
    try:
        result = await client.create_collection(
            req,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin collections API unavailable: {e.message}")
        elif e.code == "CONFLICT":
            raise conflict(e.message)
        else:
            raise downstream_unavailable(f"Admin collections API error: {e.message}")
    return result
