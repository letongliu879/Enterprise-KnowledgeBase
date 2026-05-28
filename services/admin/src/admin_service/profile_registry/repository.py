"""Profile registry repository wrapper."""

from sqlalchemy.orm import Session

from reality_rag_persistence.models import ParserProfileModel, RetrievalProfileAdminModel
from reality_rag_persistence.repositories import ParserProfileRepository, RetrievalProfileAdminRepository


class ProfileRegistryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._parser = ParserProfileRepository(session)
        self._retrieval = RetrievalProfileAdminRepository(session)

    # Parser profiles
    def get_parser(self, parser_profile_id: str) -> ParserProfileModel | None:
        return self._parser.get(parser_profile_id)

    def list_parsers(self, state: str | None = None) -> list[ParserProfileModel]:
        if state:
            return self._parser.list_by_state(state)
        return self._parser.list_all()

    def save_parser(self, profile: ParserProfileModel) -> None:
        self._parser.save(profile)

    def delete_parser(self, parser_profile_id: str) -> None:
        self._parser.delete(parser_profile_id)

    # Retrieval profiles
    def get_retrieval(self, retrieval_profile_id: str) -> RetrievalProfileAdminModel | None:
        return self._retrieval.get(retrieval_profile_id)

    def list_retrievals(self, state: str | None = None) -> list[RetrievalProfileAdminModel]:
        if state:
            return self._retrieval.list_by_state(state)
        return self._retrieval.list_all()

    def save_retrieval(self, profile: RetrievalProfileAdminModel) -> None:
        self._retrieval.save(profile)

    def delete_retrieval(self, retrieval_profile_id: str) -> None:
        self._retrieval.delete(retrieval_profile_id)
