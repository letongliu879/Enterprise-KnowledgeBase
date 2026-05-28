"""API key registry repository.

Supports both legacy ApiKeyRegistryEntry (access-service compat) and
ApiKeyRegistryEntryAdmin (admin control panel) via adapter mapping.
"""

from sqlalchemy.orm import Session

from reality_rag_contracts import ApiKeyRegistryEntry, ApiKeyRegistryEntryAdmin

from ..models import ApiKeyRegistryModel


class ApiKeyRegistryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- legacy access-service compat --------------------------------------

    def get(self, api_key_id: str) -> ApiKeyRegistryEntry | None:
        row = self._session.get(ApiKeyRegistryModel, api_key_id)
        if row is None:
            return None
        return self._to_legacy_contract(row)

    def list_all(self) -> list[ApiKeyRegistryEntry]:
        rows = self._session.query(ApiKeyRegistryModel).all()
        return [self._to_legacy_contract(row) for row in rows]

    def list_enabled(self) -> list[ApiKeyRegistryEntry]:
        rows = (
            self._session.query(ApiKeyRegistryModel)
            .filter(ApiKeyRegistryModel.state == "active")
            .all()
        )
        return [self._to_legacy_contract(row) for row in rows]

    # -- admin control panel -----------------------------------------------

    def get_admin(self, api_key_id: str) -> ApiKeyRegistryEntryAdmin | None:
        row = self._session.get(ApiKeyRegistryModel, api_key_id)
        if row is None:
            return None
        return self._to_admin_contract(row)

    def list_all_admin(self) -> list[ApiKeyRegistryEntryAdmin]:
        rows = self._session.query(ApiKeyRegistryModel).all()
        return [self._to_admin_contract(row) for row in rows]

    def list_by_state(self, state: str) -> list[ApiKeyRegistryEntryAdmin]:
        rows = (
            self._session.query(ApiKeyRegistryModel)
            .filter(ApiKeyRegistryModel.state == state)
            .all()
        )
        return [self._to_admin_contract(row) for row in rows]

    def list_by_tenant(self, tenant_id: str) -> list[ApiKeyRegistryEntryAdmin]:
        rows = (
            self._session.query(ApiKeyRegistryModel)
            .filter(ApiKeyRegistryModel.tenant_id == tenant_id)
            .all()
        )
        return [self._to_admin_contract(row) for row in rows]

    def save_admin(self, entry: ApiKeyRegistryEntryAdmin) -> None:
        row = ApiKeyRegistryModel(
            api_key_id=entry.api_key_id,
            tenant_id=entry.tenant_id,
            display_name=entry.display_name,
            agent_type_id=entry.agent_type_id,
            key_hash=entry.key_hash,
            knowledge_scopes=entry.knowledge_scopes,
            roles=entry.roles,
            debug_permission=entry.debug_permission,
            max_context_tokens=entry.token_budget_limit,
            token_budget_limit=entry.token_budget_limit,
            state=entry.state.value,
            expires_at=entry.expires_at,
            created_by=entry.created_by,
            created_at=entry.created_at,
            updated_by=entry.updated_by,
            updated_at=entry.updated_at,
            last_rotated_at=entry.last_rotated_at,
        )
        self._session.merge(row)
        self._session.flush()

    @staticmethod
    def _to_legacy_contract(row: ApiKeyRegistryModel) -> ApiKeyRegistryEntry:
        return ApiKeyRegistryEntry(
            api_key_id=row.api_key_id,
            display_name=row.display_name or "",
            agent_type_id=row.agent_type_id or "",
            knowledge_scopes=row.knowledge_scopes or [],
            roles=row.roles or [],
            debug_permission=row.debug_permission or False,
            max_context_tokens=row.max_context_tokens or row.token_budget_limit or 4096,
            enabled=(row.state == "active"),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_admin_contract(row: ApiKeyRegistryModel) -> ApiKeyRegistryEntryAdmin:
        from reality_rag_contracts import ApiKeyState
        return ApiKeyRegistryEntryAdmin(
            api_key_id=row.api_key_id,
            tenant_id=row.tenant_id or "",
            display_name=row.display_name or "",
            agent_type_id=row.agent_type_id or "",
            key_hash=row.key_hash or "",
            knowledge_scopes=row.knowledge_scopes or [],
            roles=row.roles or [],
            debug_permission=row.debug_permission or False,
            token_budget_limit=row.token_budget_limit or row.max_context_tokens or 4096,
            state=ApiKeyState(row.state) if row.state else ApiKeyState.ACTIVE,
            expires_at=row.expires_at,
            created_by=row.created_by or "",
            created_at=row.created_at,
            updated_by=row.updated_by or "",
            updated_at=row.updated_at,
            last_rotated_at=row.last_rotated_at,
        )
