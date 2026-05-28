"""Retrieval profile repository."""

from reality_rag_contracts import RetrievalProfile
from sqlalchemy.orm import Session

from ..models import RetrievalProfileModel


class RetrievalProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, profile_id: str, collection_id: str) -> RetrievalProfile | None:
        row = self._session.get(RetrievalProfileModel, (profile_id, collection_id))
        if row is None:
            return None
        return self._to_contract(row)

    def list_enabled(self) -> list[RetrievalProfile]:
        rows = (
            self._session.query(RetrievalProfileModel)
            .filter(RetrievalProfileModel.enabled.is_(True))
            .all()
        )
        return [self._to_contract(row) for row in rows]

    def save(self, profile: RetrievalProfile) -> None:
        row = RetrievalProfileModel(
            profile_id=profile.profile_id,
            collection_id=profile.collection_id,
            profile_version=profile.profile_version,
            profile_hash=profile.profile_hash,
            bm25_weight=profile.bm25_weight,
            vector_weight=profile.vector_weight,
            candidate_top_k=profile.candidate_top_k,
            similarity_threshold=profile.similarity_threshold,
            rerank_enabled=profile.rerank_enabled,
            rerank_model=profile.rerank_model,
            fail_policy=profile.fail_policy,
            expansion_policy=profile.expansion_policy,
            pack_budget=profile.pack_budget,
            enabled=profile.enabled,
            updated_at=profile.updated_at,
            updated_by=profile.updated_by,
        )
        self._session.merge(row)
        self._session.flush()

    @staticmethod
    def _to_contract(row: RetrievalProfileModel) -> RetrievalProfile:
        return RetrievalProfile(
            profile_id=row.profile_id,
            collection_id=row.collection_id,
            profile_version=row.profile_version or 1,
            profile_hash=row.profile_hash or "",
            bm25_weight=row.bm25_weight or 0.5,
            vector_weight=row.vector_weight or 0.5,
            candidate_top_k=row.candidate_top_k or 20,
            similarity_threshold=row.similarity_threshold or 0.0,
            rerank_enabled=True if row.rerank_enabled is None else row.rerank_enabled,
            rerank_model=row.rerank_model or "",
            fail_policy=row.fail_policy or "fail_closed",
            expansion_policy=row.expansion_policy or {},
            pack_budget=row.pack_budget or 1200,
            enabled=True if row.enabled is None else row.enabled,
            updated_at=row.updated_at,
            updated_by=row.updated_by or "system",
        )
