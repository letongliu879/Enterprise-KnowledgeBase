"""Document policy repository."""

from sqlalchemy.orm import Session

from reality_rag_contracts import DocumentPolicy, PolicyCondition, PolicySubject

from ..models import DocumentPolicyModel


class DocumentPolicyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, policy_id: str) -> DocumentPolicy | None:
        row = self._session.get(DocumentPolicyModel, policy_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_doc_id(self, doc_id: str) -> DocumentPolicy | None:
        row = (
            self._session.query(DocumentPolicyModel)
            .filter(DocumentPolicyModel.doc_id == doc_id)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def list_for_docs(self, doc_ids: list[str]) -> list[DocumentPolicy]:
        if not doc_ids:
            return []
        rows = (
            self._session.query(DocumentPolicyModel)
            .filter(DocumentPolicyModel.doc_id.in_(doc_ids))
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def list_by_collection(self, collection_id: str) -> list[DocumentPolicy]:
        rows = (
            self._session.query(DocumentPolicyModel)
            .filter(DocumentPolicyModel.collection_id == collection_id)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def save(self, policy: DocumentPolicy) -> None:
        row = DocumentPolicyModel(
            policy_id=policy.policy_id,
            tenant_id=policy.tenant_id,
            collection_id=policy.collection_id,
            doc_id=policy.doc_id,
            effect=policy.effect,
            subjects=[subject.model_dump(mode="json") for subject in policy.subjects],
            conditions=[condition.model_dump(mode="json") for condition in policy.conditions],
            priority=policy.priority,
            policy_version=policy.policy_version,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
        self._session.merge(row)
        self._session.flush()

    @staticmethod
    def _to_contract(row: DocumentPolicyModel) -> DocumentPolicy:
        return DocumentPolicy(
            policy_id=row.policy_id,
            tenant_id=row.tenant_id,
            collection_id=row.collection_id,
            doc_id=row.doc_id,
            effect=row.effect,
            subjects=[PolicySubject(**item) for item in (row.subjects or [])],
            conditions=[PolicyCondition(**item) for item in (row.conditions or [])],
            priority=row.priority or 100,
            policy_version=row.policy_version or "v1",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
