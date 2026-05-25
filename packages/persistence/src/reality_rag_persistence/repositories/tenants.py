"""Tenant repository."""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from reality_rag_contracts import Tenant

from ..models import TenantModel


class TenantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tenant_id: str) -> Tenant | None:
        row = self._session.get(TenantModel, tenant_id)
        if row is None:
            return None
        return Tenant(tenant_id=row.tenant_id, name=row.name)

    def list_all(self) -> list[Tenant]:
        rows = self._session.query(TenantModel).all()
        return [Tenant(tenant_id=r.tenant_id, name=r.name) for r in rows]

    def save(self, tenant: Tenant) -> None:
        row = TenantModel(tenant_id=tenant.tenant_id, name=tenant.name)
        self._session.execute(
            pg_insert(TenantModel)
            .values(tenant_id=row.tenant_id, name=row.name)
            .on_conflict_do_update(
                index_elements=["tenant_id"],
                set_={"name": row.name},
            )
        )
        self._session.flush()
