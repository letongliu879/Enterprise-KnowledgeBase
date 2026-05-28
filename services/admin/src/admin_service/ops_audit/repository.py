"""Ops audit repository wrapper."""

from sqlalchemy.orm import Session

from reality_rag_persistence.repositories import OpsAuditLogRepository


class OpsAuditRepository:
    def __init__(self, session: Session) -> None:
        self._repo = OpsAuditLogRepository(session)

    def save(self, entry):
        return self._repo.save(entry)

    def list_all(self, **kwargs):
        return self._repo.list_all(**kwargs)

    def count(self, **kwargs):
        return self._repo.count(**kwargs)
