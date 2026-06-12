"""Parser profile selection routes."""

from fastapi import APIRouter, Depends

from ..deps import require_auth, CurrentUser
from ..downstream_clients import AdminClient, IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, not_found
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
        raise downstream_not_implemented(f"Admin collection API not yet available: {e}")

    return {
        "items": [item.model_dump() for item in result.items],
        "default_parser_profile_id": result.default_parser_profile_id,
    }


@router.get("/{profile_id}")
async def get_parser_profile(
    profile_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.get_parser_profile(
            profile_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin parser profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Parser profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin parser profiles API error: {e.message}")
    return result


@router.post("")
async def create_parser_profile(
    body: dict,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.create_parser_profile(
            body,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin parser profiles API unavailable: {e.message}")
        raise downstream_unavailable(f"Admin parser profiles API error: {e.message}")
    return result


@router.patch("/{profile_id}")
async def update_parser_profile(
    profile_id: str,
    body: dict,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.update_parser_profile(
            profile_id,
            body,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin parser profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Parser profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin parser profiles API error: {e.message}")
    return result


@router.delete("/{profile_id}")
async def delete_parser_profile(
    profile_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.delete_parser_profile(
            profile_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin parser profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Parser profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin parser profiles API error: {e.message}")
    return result


@router.post("/{profile_id}/publish")
async def publish_parser_profile(
    profile_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.publish_parser_profile(
            profile_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin parser profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Parser profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin parser profiles API error: {e.message}")
    return result


@router.post("/{profile_id}/clone")
async def clone_parser_profile(
    profile_id: str,
    user: CurrentUser = Depends(require_auth),
):
    client = AdminClient()
    try:
        result = await client.clone_parser_profile(
            profile_id,
            headers={"Authorization": f"Bearer {user.token}"},
        )
    except DownstreamError as e:
        if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
            raise downstream_not_implemented(f"Admin parser profiles API unavailable: {e.message}")
        if e.code == "NOT_FOUND":
            raise not_found(f"Parser profile not found: {profile_id}")
        raise downstream_unavailable(f"Admin parser profiles API error: {e.message}")
    return result
