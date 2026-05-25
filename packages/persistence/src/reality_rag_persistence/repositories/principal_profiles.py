"""Principal profile repository."""

from sqlalchemy.orm import Session

from reality_rag_contracts import PrincipalProfile

from ..models import PrincipalProfileModel


class PrincipalProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: str) -> PrincipalProfile | None:
        row = self._session.get(PrincipalProfileModel, user_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_by_tenant(self, tenant_id: str) -> list[PrincipalProfile]:
        rows = (
            self._session.query(PrincipalProfileModel)
            .filter(PrincipalProfileModel.tenant_id == tenant_id)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def save(self, profile: PrincipalProfile) -> None:
        row = PrincipalProfileModel(
            user_id=profile.user_id,
            tenant_id=profile.tenant_id,
            role_ids=profile.role_ids,
            group_ids=profile.group_ids,
            department_ids=profile.department_ids,
            clearance_level=profile.clearance_level,
            attributes=profile.attributes,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
        self._session.merge(row)
        self._session.flush()

    @staticmethod
    def _to_contract(row: PrincipalProfileModel) -> PrincipalProfile:
        return PrincipalProfile(
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            role_ids=row.role_ids or [],
            group_ids=row.group_ids or [],
            department_ids=row.department_ids or [],
            clearance_level=row.clearance_level or 0,
            attributes=row.attributes or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
