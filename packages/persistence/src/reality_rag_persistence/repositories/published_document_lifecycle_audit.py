"""Published document lifecycle audit repository. Owner: publishing domain."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import PublishedDocumentLifecycleAudit

from ..models import PublishedDocumentLifecycleAuditModel


class PublishedDocumentLifecycleAuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, audit_id: str) -> PublishedDocumentLifecycleAudit | None:
        row = self._session.get(PublishedDocumentLifecycleAuditModel, audit_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_by_published_document(
        self, published_document_id: str
    ) -> list[PublishedDocumentLifecycleAudit]:
        rows = (
            self._session.query(PublishedDocumentLifecycleAuditModel)
            .filter(
                PublishedDocumentLifecycleAuditModel.published_document_id
                == published_document_id
            )
            .order_by(PublishedDocumentLifecycleAuditModel.created_at)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def create(
        self,
        audit_id: str,
        published_document_id: str,
        final_doc_id: str,
        actor_id: str,
        action: str,
        before_state: str | None = None,
        after_state: str | None = None,
        reason: str | None = None,
        payload_hash: str = "",
    ) -> PublishedDocumentLifecycleAudit:
        now = datetime.now(timezone.utc)
        row = PublishedDocumentLifecycleAuditModel(
            audit_id=audit_id,
            published_document_id=published_document_id,
            final_doc_id=final_doc_id,
            actor_id=actor_id,
            action=action,
            before_state=before_state,
            after_state=after_state,
            reason=reason,
            payload_hash=payload_hash,
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    @staticmethod
    def _to_contract(
        row: PublishedDocumentLifecycleAuditModel,
    ) -> PublishedDocumentLifecycleAudit:
        return PublishedDocumentLifecycleAudit(
            audit_id=row.audit_id,
            published_document_id=row.published_document_id,
            final_doc_id=row.final_doc_id,
            actor_id=row.actor_id,
            action=row.action,
            before_state=row.before_state,
            after_state=row.after_state,
            reason=row.reason,
            payload_hash=row.payload_hash,
            created_at=row.created_at,
        )
