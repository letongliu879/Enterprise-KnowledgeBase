"""Parser profile repository."""

from sqlalchemy.orm import Session

from ..models import ParserProfileModel


class ParserProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, parser_profile_id: str) -> ParserProfileModel | None:
        return self._session.get(ParserProfileModel, parser_profile_id)

    def list_all(self) -> list[ParserProfileModel]:
        return self._session.query(ParserProfileModel).all()

    def list_by_state(self, state: str) -> list[ParserProfileModel]:
        return (
            self._session.query(ParserProfileModel)
            .filter(ParserProfileModel.state == state)
            .all()
        )

    def save(self, profile: ParserProfileModel) -> None:
        self._session.merge(profile)
        self._session.flush()

    def delete(self, parser_profile_id: str) -> None:
        row = self._session.get(ParserProfileModel, parser_profile_id)
        if row:
            self._session.delete(row)
            self._session.flush()
