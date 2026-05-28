"""Retrieval profile admin repository."""

from sqlalchemy.orm import Session

from ..models import RetrievalProfileAdminModel


class RetrievalProfileAdminRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, retrieval_profile_id: str) -> RetrievalProfileAdminModel | None:
        return self._session.get(RetrievalProfileAdminModel, retrieval_profile_id)

    def list_all(self) -> list[RetrievalProfileAdminModel]:
        return self._session.query(RetrievalProfileAdminModel).all()

    def list_by_state(self, state: str) -> list[RetrievalProfileAdminModel]:
        return (
            self._session.query(RetrievalProfileAdminModel)
            .filter(RetrievalProfileAdminModel.state == state)
            .all()
        )

    def save(self, profile: RetrievalProfileAdminModel) -> None:
        self._session.merge(profile)
        self._session.flush()

    def delete(self, retrieval_profile_id: str) -> None:
        row = self._session.get(RetrievalProfileAdminModel, retrieval_profile_id)
        if row:
            self._session.delete(row)
            self._session.flush()
