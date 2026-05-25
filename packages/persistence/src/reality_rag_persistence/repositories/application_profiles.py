"""Application Profile repository."""

from sqlalchemy.orm import Session

from reality_rag_contracts import ApplicationProfile

from ..models import ApplicationProfileModel


class ApplicationProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, profile_id: str) -> ApplicationProfile | None:
        row = self._session.get(ApplicationProfileModel, profile_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_all(self) -> list[ApplicationProfile]:
        rows = self._session.query(ApplicationProfileModel).all()
        return [self._to_contract(r) for r in rows]

    def list_by_tenant(self, tenant_id: str) -> list[ApplicationProfile]:
        rows = (
            self._session.query(ApplicationProfileModel)
            .filter(ApplicationProfileModel.tenant_id == tenant_id)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def save(self, profile: ApplicationProfile) -> None:
        row = ApplicationProfileModel(
            application_profile_id=profile.application_profile_id,
            tenant_id=profile.tenant_id,
            name=profile.name,
            allowed_collections=profile.allowed_collections,
            default_collections=profile.default_collections,
            allow_cross_collection=profile.allow_cross_collection,
            default_token_budget=profile.default_token_budget,
            default_budget_policy=profile.default_budget_policy.value,
            metadata_policy=profile.metadata_policy,
            debug_permission=profile.debug_permission,
            rate_limit=profile.rate_limit,
        )
        self._session.merge(row)
        self._session.flush()

    @staticmethod
    def _to_contract(row: ApplicationProfileModel) -> ApplicationProfile:
        return ApplicationProfile(
            application_profile_id=row.application_profile_id,
            tenant_id=row.tenant_id,
            name=row.name,
            allowed_collections=row.allowed_collections or [],
            default_collections=row.default_collections or [],
            allow_cross_collection=row.allow_cross_collection or False,
            default_token_budget=row.default_token_budget or 4096,
            default_budget_policy=row.default_budget_policy or "balanced",
            metadata_policy=row.metadata_policy or "minimal",
            debug_permission=row.debug_permission or False,
            rate_limit=row.rate_limit or 100,
        )
