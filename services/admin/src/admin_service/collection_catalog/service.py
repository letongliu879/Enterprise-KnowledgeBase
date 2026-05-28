"""Collection catalog service."""

from datetime import datetime, timezone
import hashlib
import secrets

from reality_rag_contracts import AdminCollection, CollectionProfileBinding
from reality_rag_contracts.enums import CollectionLifecycleState
from reality_rag_persistence.models import CollectionModel, CollectionProfileBindingModel

from .repository import CollectionCatalogRepository
from .models import (
    CollectionCreateRequest,
    CollectionUpdateRequest,
    ProfileBindingCreateRequest,
)


def _to_admin_collection(row: CollectionModel) -> AdminCollection:
    return AdminCollection(
        collection_id=row.collection_id,
        tenant_id=row.tenant_id,
        name=row.name,
        description=row.description or "",
        lifecycle_state=CollectionLifecycleState(row.lifecycle_state)
        if row.lifecycle_state else CollectionLifecycleState.ACTIVE,
        authority_level=row.authority_level or 0,
        access_policy=row.access_policy or {},
        default_parser_profile_id=row.default_parser_profile_id or "",
        default_retrieval_profile_id=row.default_retrieval_profile_id or "",
        default_approval_policy_id=row.default_approval_policy_id or "",
        created_by=row.created_by or "",
        created_at=row.created_at,
        updated_by=row.updated_by or "",
        updated_at=row.updated_at,
    )


def _to_binding_contract(row: CollectionProfileBindingModel) -> CollectionProfileBinding:
    return CollectionProfileBinding(
        binding_id=row.binding_id,
        tenant_id=row.tenant_id,
        collection_id=row.collection_id,
        parser_profile_id=row.parser_profile_id or "",
        retrieval_profile_id=row.retrieval_profile_id or "",
        approval_policy_id=row.approval_policy_id or "",
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        binding_version=row.binding_version or 1,
        config_hash=row.config_hash or "",
        created_by=row.created_by or "",
        created_at=row.created_at,
    )


class CollectionCatalogService:
    def __init__(self, repo: CollectionCatalogRepository, actor_id: str = ""):
        self._repo = repo
        self._actor_id = actor_id

    def list_collections(self, tenant_id: str | None = None) -> list[AdminCollection]:
        rows = self._repo.list_collections(tenant_id)
        return [_to_admin_collection(r) for r in rows]

    def get_collection(self, collection_id: str) -> AdminCollection | None:
        row = self._repo.get_collection(collection_id)
        if row is None:
            return None
        return _to_admin_collection(row)

    def create_collection(self, req: CollectionCreateRequest) -> AdminCollection:
        now = datetime.now(timezone.utc)
        collection = CollectionModel(
            collection_id=req.collection_id,
            tenant_id=req.tenant_id,
            name=req.name,
            description=req.description,
            lifecycle_state=CollectionLifecycleState.ACTIVE.value,
            authority_level=req.authority_level,
            access_policy=req.access_policy,
            default_parser_profile_id=req.default_parser_profile_id,
            default_retrieval_profile_id=req.default_retrieval_profile_id,
            default_approval_policy_id=req.default_approval_policy_id,
            created_by=self._actor_id,
            created_at=now,
            updated_by=self._actor_id,
            updated_at=now,
        )
        self._repo.save_collection(collection)
        return _to_admin_collection(collection)

    def update_collection(self, collection_id: str, req: CollectionUpdateRequest) -> AdminCollection | None:
        row = self._repo.get_collection(collection_id)
        if row is None:
            return None
        if req.name is not None:
            row.name = req.name
        if req.description is not None:
            row.description = req.description
        if req.authority_level is not None:
            row.authority_level = req.authority_level
        if req.access_policy is not None:
            row.access_policy = req.access_policy
        if req.default_parser_profile_id is not None:
            row.default_parser_profile_id = req.default_parser_profile_id
        if req.default_retrieval_profile_id is not None:
            row.default_retrieval_profile_id = req.default_retrieval_profile_id
        if req.default_approval_policy_id is not None:
            row.default_approval_policy_id = req.default_approval_policy_id
        row.updated_by = self._actor_id
        row.updated_at = datetime.now(timezone.utc)
        self._repo.save_collection(row)
        return _to_admin_collection(row)

    def transition_lifecycle(self, collection_id: str, target_state: CollectionLifecycleState, reason: str = "") -> AdminCollection | None:
        row = self._repo.get_collection(collection_id)
        if row is None:
            return None
        row.lifecycle_state = target_state.value
        row.updated_by = self._actor_id
        row.updated_at = datetime.now(timezone.utc)
        self._repo.save_collection(row)
        return _to_admin_collection(row)

    def list_bindings(self, collection_id: str) -> list[CollectionProfileBinding]:
        rows = self._repo.list_bindings(collection_id)
        return [_to_binding_contract(r) for r in rows]

    def get_current_binding(self, collection_id: str) -> CollectionProfileBinding | None:
        row = self._repo.get_current_binding(collection_id)
        if row is None:
            return None
        return _to_binding_contract(row)

    def create_binding(self, collection_id: str, tenant_id: str, req: ProfileBindingCreateRequest) -> tuple[CollectionProfileBinding, str | None]:
        """Create a new binding version. Returns (new_binding, previous_binding_id)."""
        now = datetime.now(timezone.utc)
        previous = self._repo.get_current_binding(collection_id)
        previous_binding_id = previous.binding_id if previous else None

        if previous:
            self._repo.close_current_binding(collection_id)

        next_version = 1
        if previous:
            next_version = (previous.binding_version or 1) + 1

        config_str = f"{req.parser_profile_id}:{req.retrieval_profile_id}:{req.approval_policy_id}"
        config_hash = hashlib.sha256(config_str.encode("utf-8")).hexdigest()

        binding = CollectionProfileBindingModel(
            binding_id=secrets.token_urlsafe(32),
            tenant_id=tenant_id,
            collection_id=collection_id,
            parser_profile_id=req.parser_profile_id,
            retrieval_profile_id=req.retrieval_profile_id,
            approval_policy_id=req.approval_policy_id,
            effective_from=now,
            effective_to=None,
            binding_version=next_version,
            config_hash=config_hash,
            created_by=self._actor_id,
            created_at=now,
        )
        self._repo.save_binding(binding)
        return _to_binding_contract(binding), previous_binding_id
