"""Retrieval-profile proxy routes — frontend calls workbench, workbench delegates to admin."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..downstream_clients import AdminClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, conflict, not_found

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


@router.post("")
async def create_retrieval_profile(
    body: dict,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.create_retrieval_profile(
            body,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin retrieval profiles API unavailable: {e.message}")
        raise downstream_unavailable(f"Admin retrieval profiles API error: {e.message}")
    return result


@router.get("/{profile_id}")
async def get_retrieval_profile(
    profile_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.get_retrieval_profile(
            profile_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin retrieval profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Retrieval profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin retrieval profiles API error: {e.message}")
    return result


@router.patch("/{profile_id}")
async def update_retrieval_profile(
    profile_id: str,
    body: dict,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.update_retrieval_profile(
            profile_id,
            body,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin retrieval profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Retrieval profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin retrieval profiles API error: {e.message}")
    return result


@router.delete("/{profile_id}")
async def delete_retrieval_profile(
    profile_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.delete_retrieval_profile(
            profile_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin retrieval profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Retrieval profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin retrieval profiles API error: {e.message}")
    return result


@router.post("/{profile_id}/publish")
async def publish_retrieval_profile(
    profile_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.publish_retrieval_profile(
            profile_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin retrieval profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Retrieval profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin retrieval profiles API error: {e.message}")
    return result


@router.post("/{profile_id}/clone")
async def clone_retrieval_profile(
    profile_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.clone_retrieval_profile(
            profile_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin retrieval profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Retrieval profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin retrieval profiles API error: {e.message}")
    return result
