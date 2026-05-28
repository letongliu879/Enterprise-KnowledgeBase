"""API key registry repository wrapper."""

from sqlalchemy.orm import Session

from reality_rag_persistence.repositories import ApiKeyRegistryRepository


class ApiKeyRegistryAdminRepository:
    def __init__(self, session: Session) -> None:
        self._repo = ApiKeyRegistryRepository(session)

    def get(self, api_key_id: str):
        return self._repo.get_admin(api_key_id)

    def list_all(self):
        return self._repo.list_all_admin()

    def list_by_state(self, state: str):
        return self._repo.list_by_state(state)

    def list_by_tenant(self, tenant_id: str):
        return self._repo.list_by_tenant(tenant_id)

    def save(self, entry):
        return self._repo.save_admin(entry)
