"""Collection catalog routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from reality_rag_contracts import AdminCollection
from reality_rag_contracts.enums import CollectionLifecycleState

from ..deps import get_db, require_auth, CurrentUser, require_role
from ..errors import not_found, forbidden
from .service import CollectionCatalogService
from .repository import CollectionCatalogRepository
from .models import (
    CollectionCreateRequest,
    CollectionUpdateRequest,
    CollectionListResponse,
    CollectionLifecycleTransitionRequest,
    ProfileBindingCreateRequest,
    ProfileBindingResponse,
)

router = APIRouter(prefix="/admin/collections")


def _get_service(session: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> CollectionCatalogService:
    return CollectionCatalogService(CollectionCatalogRepository(session), actor_id=user.user_id)


def _require_knowledge_admin(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    if not user.has_role("knowledge_admin") and not user.has_role("platform_admin"):
        raise forbidden("Knowledge admin or platform admin role required")
    return user


@router.get("", response_model=CollectionListResponse)
def list_collections(
    tenant_id: str | None = None,
    service: CollectionCatalogService = Depends(_get_service),
    user: CurrentUser = Depends(require_auth),
):
    if tenant_id and not user.can_access_tenant(tenant_id):
        raise forbidden("Access denied for this tenant")
    items = service.list_collections(tenant_id)
    return CollectionListResponse(items=items, total=len(items))


@router.post("", response_model=AdminCollection)
def create_collection(
    req: CollectionCreateRequest,
    service: CollectionCatalogService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    return service.create_collection(req)


@router.get("/{collection_id}")
def get_collection(
    collection_id: str,
    service: CollectionCatalogService = Depends(_get_service),
):
    result = service.get_collection(collection_id)
    if result is None:
        raise not_found(f"Collection {collection_id} not found")
    return result


@router.patch("/{collection_id}")
def update_collection(
    collection_id: str,
    req: CollectionUpdateRequest,
    service: CollectionCatalogService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    result = service.update_collection(collection_id, req)
    if result is None:
        raise not_found(f"Collection {collection_id} not found")
    return result


@router.post("/{collection_id}/lifecycle")
def transition_lifecycle(
    collection_id: str,
    req: CollectionLifecycleTransitionRequest,
    service: CollectionCatalogService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    result = service.transition_lifecycle(collection_id, req.target_state, req.reason)
    if result is None:
        raise not_found(f"Collection {collection_id} not found")
    return result


@router.get("/{collection_id}/bindings")
def list_bindings(
    collection_id: str,
    service: CollectionCatalogService = Depends(_get_service),
):
    return service.list_bindings(collection_id)


@router.get("/{collection_id}/bindings/current")
def get_current_binding(
    collection_id: str,
    service: CollectionCatalogService = Depends(_get_service),
):
    result = service.get_current_binding(collection_id)
    if result is None:
        raise not_found(f"No active binding for collection {collection_id}")
    return result


@router.post("/{collection_id}/bindings", response_model=ProfileBindingResponse)
def create_binding(
    collection_id: str,
    req: ProfileBindingCreateRequest,
    service: CollectionCatalogService = Depends(_get_service),
    user: CurrentUser = Depends(_require_knowledge_admin),
):
    # Determine tenant_id from collection
    collection = service.get_collection(collection_id)
    if collection is None:
        raise not_found(f"Collection {collection_id} not found")
    binding, prev_id = service.create_binding(collection_id, collection.tenant_id, req)
    return ProfileBindingResponse(binding=binding, previous_binding_id=prev_id)
