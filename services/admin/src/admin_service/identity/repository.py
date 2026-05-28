"""Admin user and session repository wrappers."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_persistence.models import AdminUserModel, AdminSessionModel
from reality_rag_persistence.repositories import AdminUserRepository, AdminSessionRepository


class IdentityRepository:
    def __init__(self, session: Session):
        self._session = session
        self._users = AdminUserRepository(session)
        self._sessions = AdminSessionRepository(session)

    def get_user(self, user_id: str) -> AdminUserModel | None:
        return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> AdminUserModel | None:
        return self._users.get_by_email(email)

    def save_user(self, user: AdminUserModel) -> None:
        self._users.save(user)

    def save_session(self, session: AdminSessionModel) -> None:
        self._sessions.save(session)

    def delete_session(self, session_id: str) -> None:
        self._sessions.delete(session_id)

    def get_session(self, session_id: str) -> AdminSessionModel | None:
        return self._sessions.get(session_id)
