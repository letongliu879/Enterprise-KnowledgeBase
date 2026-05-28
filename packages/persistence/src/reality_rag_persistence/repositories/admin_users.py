"""Admin user and session repositories."""

from sqlalchemy.orm import Session

from reality_rag_contracts import AdminRole

from ..models import AdminUserModel, AdminSessionModel


class AdminUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: str) -> AdminUserModel | None:
        return self._session.get(AdminUserModel, user_id)

    def get_by_email(self, email: str) -> AdminUserModel | None:
        return (
            self._session.query(AdminUserModel)
            .filter(AdminUserModel.email == email)
            .first()
        )

    def save(self, user: AdminUserModel) -> None:
        self._session.merge(user)
        self._session.flush()

    def list_all(self) -> list[AdminUserModel]:
        return self._session.query(AdminUserModel).all()


class AdminSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, session_id: str) -> AdminSessionModel | None:
        return self._session.get(AdminSessionModel, session_id)

    def save(self, session: AdminSessionModel) -> None:
        self._session.merge(session)
        self._session.flush()

    def delete(self, session_id: str) -> None:
        row = self._session.get(AdminSessionModel, session_id)
        if row:
            self._session.delete(row)
            self._session.flush()

    def delete_by_user(self, user_id: str) -> None:
        self._session.query(AdminSessionModel).filter(
            AdminSessionModel.user_id == user_id
        ).delete()
        self._session.flush()
