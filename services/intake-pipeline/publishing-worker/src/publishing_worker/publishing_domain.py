"""Publishing domain — asset write and document persistence.

Owner: publishing-worker (in monolith: publishing_domain module).

Rules:
  - May write sidecar assets.
  - May write Document and DocumentPolicy tables.
  - May NOT write intake_jobs, stage_tasks, stage_attempts, stage_results.
  - May NOT generate final_doc_id (only approval-service does that).
"""

from __future__ import annotations

from intake_runtime.publishing_persistence import persist_document_and_policy as _persist_document_and_policy
from reality_rag_contracts import CanonicalMetadata, PublishedDocumentState
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.document_policies import DocumentPolicyRepository
from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository


def persist_document_and_policy(
    canonical_metadata: CanonicalMetadata,
    *,
    document_repo=None,
    policy_repo=None,
    collection_authority_level: int = 0,
) -> tuple[bool, bool]:
    """Persist canonical metadata and optional policy.

    When repos are provided, use the caller's transaction boundary.
    Otherwise fall back to the owner service entrypoint.
    """
    if document_repo is None and policy_repo is None:
        return PublishingService().persist(
            canonical_metadata,
            collection_authority_level=collection_authority_level,
        )
    return _persist_document_and_policy(
        canonical_metadata,
        document_repo=document_repo,
        policy_repo=policy_repo,
        collection_authority_level=collection_authority_level,
    )


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

            document_persisted, policy_persisted = persist_document_and_policy(
                canonical_metadata,
                document_repo=document_repo,
                policy_repo=policy_repo,
                collection_authority_level=collection_authority_level,
            )

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
