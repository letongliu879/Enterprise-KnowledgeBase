"""API key registry routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from reality_rag_contracts import ApiKeyRegistryEntryAdmin

from ..deps import get_db, require_auth, CurrentUser
from ..errors import not_found, forbidden
from .service import ApiKeyRegistryService
from .repository import ApiKeyRegistryAdminRepository
from .models import (
    ApiKeyCreateRequest,
    ApiKeyUpdateRequest,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
    ApiKeyRotateResponse,
)

router = APIRouter(prefix="/admin/api-keys")


def _get_service(session: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> ApiKeyRegistryService:
    return ApiKeyRegistryService(ApiKeyRegistryAdminRepository(session), actor_id=user.user_id)


def _require_knowledge_admin(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    if not user.has_role("knowledge_admin") and not user.has_role("platform_admin"):
        raise forbidden("Knowledge admin or platform admin role required")
    return user


@router.get("", response_model=ApiKeyListResponse)
def list_keys(
    tenant_id: str | None = None,
    state: str | None = None,
    service: ApiKeyRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(require_auth),
):
    if tenant_id and not user.can_access_tenant(tenant_id):
        raise forbidden("Access denied for this tenant")
    items = service.list_keys(tenant_id=tenant_id, state=state)
    return ApiKeyListResponse(items=items, total=len(items))


@router.post("", response_model=ApiKeyCreateResponse)
def create_key(
    req: ApiKeyCreateRequest,
    service: ApiKeyRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    entry, plaintext = service.create_key(req)
    return ApiKeyCreateResponse(entry=entry, plaintext_key=plaintext)


@router.get("/{api_key_id}")
def get_key(
    api_key_id: str,
    service: ApiKeyRegistryService = Depends(_get_service),
):
    result = service.get_key(api_key_id)
    if result is None:
        raise not_found(f"API key {api_key_id} not found")
    return result


@router.patch("/{api_key_id}")
def update_key(
    api_key_id: str,
    req: ApiKeyUpdateRequest,
    service: ApiKeyRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    result = service.update_key(api_key_id, req)
    if result is None:
        raise not_found(f"API key {api_key_id} not found")
    return result


@router.post("/{api_key_id}/rotate")
def rotate_key(
    api_key_id: str,
    service: ApiKeyRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    result = service.rotate_key(api_key_id)
    if result is None:
        raise not_found(f"API key {api_key_id} not found")
    entry, plaintext = result
    return ApiKeyRotateResponse(entry=entry, plaintext_key=plaintext)


@router.post("/{api_key_id}/disable")
def disable_key(
    api_key_id: str,
    service: ApiKeyRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    result = service.disable_key(api_key_id)
    if result is None:
        raise not_found(f"API key {api_key_id} not found")
    return result


@router.post("/{api_key_id}/revoke")
def revoke_key(
    api_key_id: str,
    service: ApiKeyRegistryService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    result = service.revoke_key(api_key_id)
    if result is None:
        raise not_found(f"API key {api_key_id} not found")
    return result
