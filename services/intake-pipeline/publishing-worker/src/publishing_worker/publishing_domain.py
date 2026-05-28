"""Publishing domain — asset write and document persistence.

Owner: publishing-worker (in monolith: publishing_domain module).

Rules:
  - May write sidecar assets.
  - May write Document and DocumentPolicy tables.
  - May NOT write intake_jobs, stage_tasks, stage_attempts, stage_results.
  - May NOT generate final_doc_id (only approval-service does that).
"""

from __future__ import annotations

from reality_rag_contracts import (
    CanonicalMetadata,
    DocumentPolicy,
    PublishStatus,
    PublishedDocumentState,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.document_policies import DocumentPolicyRepository
from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository


class PublishingService:
    """Publishing service — persists documents and policies.

    Owner: publishing-worker (in monolith: publishing_domain module).
    """

    def persist(
        self,
        canonical_metadata: CanonicalMetadata,
        *,
        collection_authority_level: int = 0,
    ) -> tuple[bool, bool]:
        """Persist canonical metadata and optional policy.

        Returns (document_persisted, policy_persisted).
        """
        session = get_session()
        try:
            document_repo = DocumentRepository(session)
            policy_repo = DocumentPolicyRepository(session)

            document_persisted = False
            policy_persisted = False

            document_repo.save(canonical_metadata)
            document_persisted = True

            if canonical_metadata.publish_status == PublishStatus.PUBLISHED:
                policy_id = f"dp-{canonical_metadata.doc_id}"
                existing = policy_repo.get(policy_id)
                if existing is None:
                    from reality_rag_contracts import PolicyCondition, PolicySubject

                    policy = DocumentPolicy(
                        policy_id=policy_id,
                        tenant_id=canonical_metadata.tenant_id,
                        collection_id=canonical_metadata.collection_id,
                        doc_id=canonical_metadata.doc_id,
                        effect="allow",
                        subjects=[
                            PolicySubject(
                                subject_type="tenant",
                                subject_id=canonical_metadata.tenant_id,
                            )
                        ],
                        conditions=[
                            PolicyCondition(
                                field="clearance_level",
                                operator="gte",
                                value=collection_authority_level,
                            )
                        ],
                        priority=100,
                        policy_version="v1",
                    )
                    policy_repo.save(policy)
                    policy_persisted = True

            session.commit()
            return document_persisted, policy_persisted
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def update_published_document_state(
    final_doc_id: str,
    new_state: PublishedDocumentState,
    *,
    actor_id: str = "system",
    reason: str = "",
) -> tuple[bool, str]:
    """Update published document state. Returns (success, previous_state)."""
    session = get_session()
    try:
        repo = PublishedDocumentRepository(session)
        doc = repo.get_by_final_doc_id(final_doc_id)
        if doc is None:
            raise ValueError(f"Published document not found: {final_doc_id}")
        previous_state = doc.state.value if doc.state else ""
        if previous_state == new_state.value:
            return True, previous_state
        repo.update_state(doc.published_document_id, new_state, previous_state=previous_state)
        session.commit()
        return True, previous_state
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
