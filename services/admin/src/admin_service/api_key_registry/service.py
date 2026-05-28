"""API key registry service."""

from datetime import datetime, timezone
import secrets

from reality_rag_contracts import ApiKeyRegistryEntryAdmin
from reality_rag_contracts.enums import ApiKeyState

from .repository import ApiKeyRegistryAdminRepository
from .models import ApiKeyCreateRequest, ApiKeyUpdateRequest


def _generate_key() -> str:
    return f"rrag_{secrets.token_urlsafe(32)}"


def _hash_key(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class ApiKeyRegistryService:
    def __init__(self, repo: ApiKeyRegistryAdminRepository, actor_id: str = ""):
        self._repo = repo
        self._actor_id = actor_id

    def list_keys(self, tenant_id: str | None = None, state: str | None = None) -> list[ApiKeyRegistryEntryAdmin]:
        if tenant_id:
            return self._repo.list_by_tenant(tenant_id)
        if state:
            return self._repo.list_by_state(state)
        return self._repo.list_all()

    def get_key(self, api_key_id: str) -> ApiKeyRegistryEntryAdmin | None:
        return self._repo.get(api_key_id)

    def create_key(self, req: ApiKeyCreateRequest) -> tuple[ApiKeyRegistryEntryAdmin, str]:
        now = datetime.now(timezone.utc)
        plaintext = _generate_key()
        entry = ApiKeyRegistryEntryAdmin(
            api_key_id=req.api_key_id,
            tenant_id=req.tenant_id,
            key_hash=_hash_key(plaintext),
            display_name=req.display_name,
            agent_type_id="",
            knowledge_scopes=req.knowledge_scopes,
            roles=req.roles,
            debug_permission=req.debug_permission,
            token_budget_limit=req.token_budget_limit,
            state=ApiKeyState.ACTIVE,
            expires_at=req.expires_at,
            created_by=self._actor_id,
            created_at=now,
            updated_by=self._actor_id,
            updated_at=now,
            last_rotated_at=None,
        )
        self._repo.save(entry)
        return entry, plaintext

    def update_key(self, api_key_id: str, req: ApiKeyUpdateRequest) -> ApiKeyRegistryEntryAdmin | None:
        entry = self._repo.get(api_key_id)
        if entry is None:
            return None
        if req.display_name is not None:
            entry.display_name = req.display_name
        if req.knowledge_scopes is not None:
            entry.knowledge_scopes = req.knowledge_scopes
        if req.roles is not None:
            entry.roles = req.roles
        if req.debug_permission is not None:
            entry.debug_permission = req.debug_permission
        if req.token_budget_limit is not None:
            entry.token_budget_limit = req.token_budget_limit
        if req.expires_at is not None:
            entry.expires_at = req.expires_at
        entry.updated_by = self._actor_id
        entry.updated_at = datetime.now(timezone.utc)
        self._repo.save(entry)
        return entry

    def rotate_key(self, api_key_id: str) -> tuple[ApiKeyRegistryEntryAdmin, str] | None:
        entry = self._repo.get(api_key_id)
        if entry is None:
            return None
        plaintext = _generate_key()
        entry.key_hash = _hash_key(plaintext)
        entry.last_rotated_at = datetime.now(timezone.utc)
        entry.updated_by = self._actor_id
        entry.updated_at = datetime.now(timezone.utc)
        self._repo.save(entry)
        return entry, plaintext

    def disable_key(self, api_key_id: str) -> ApiKeyRegistryEntryAdmin | None:
        entry = self._repo.get(api_key_id)
        if entry is None:
            return None
        entry.state = ApiKeyState.DISABLED
        entry.updated_by = self._actor_id
        entry.updated_at = datetime.now(timezone.utc)
        self._repo.save(entry)
        return entry

    def revoke_key(self, api_key_id: str) -> ApiKeyRegistryEntryAdmin | None:
        entry = self._repo.get(api_key_id)
        if entry is None:
            return None
        entry.state = ApiKeyState.REVOKED
        entry.updated_by = self._actor_id
        entry.updated_at = datetime.now(timezone.utc)
        self._repo.save(entry)
        return entry
