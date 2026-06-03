"""Publishing persistence adapter used by ingestion-worker stage execution.

The actual publishing facts remain owned by publishing-domain logic. This
adapter only delegates repo-backed persistence inside the current transaction;
it is not a remote-or-local selector anymore.
"""

from __future__ import annotations

from intake_runtime.publishing_persistence import persist_document_and_policy as _persist_document_and_policy
from reality_rag_contracts import CanonicalMetadata

__all__ = ["persist_document_and_policy"]


def persist_document_and_policy(
    canonical_metadata: CanonicalMetadata,
    *,
    document_repo=None,
    policy_repo=None,
    collection_authority_level: int = 0,
) -> tuple[bool, bool]:
    if document_repo is None:
        raise RuntimeError(
            "document_repo is required; publishing persistence must run inside the stage transaction."
        )
    return _persist_document_and_policy(
        canonical_metadata,
        document_repo=document_repo,
        policy_repo=policy_repo,
        collection_authority_level=collection_authority_level,
    )
