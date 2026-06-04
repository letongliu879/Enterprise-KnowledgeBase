"""Shared publishing persistence helpers.

This module centralizes the actual persistence logic used by both
`publishing-worker` and the ingestion-worker compatibility wrappers so that
published document facts are written consistently in one place.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from reality_rag_contracts import (
    CanonicalMetadata,
    DocumentPolicy,
    PolicyCondition,
    PolicySubject,
    PublishStatus,
    PublishedDocumentState,
)


def persist_document_and_policy(
    canonical_metadata: CanonicalMetadata,
    *,
    document_repo,
    policy_repo,
    collection_authority_level: int = 0,
) -> tuple[bool, bool]:
    """Persist document/policy facts inside the caller's transaction."""
    document_persisted = False
    policy_persisted = False

    if document_repo is not None:
        document_repo.save(canonical_metadata)
        _upsert_published_document(canonical_metadata, document_repo=document_repo)
        document_persisted = True

    if policy_repo is not None and canonical_metadata.publish_status == PublishStatus.PUBLISHED:
        policy_id = f"dp-{canonical_metadata.doc_id}"
        existing = policy_repo.get(policy_id)
        if existing is None:
            policy_repo.save(
                DocumentPolicy(
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
            )
            policy_persisted = True

    return document_persisted, policy_persisted


def _upsert_published_document(
    canonical_metadata: CanonicalMetadata,
    *,
    document_repo,
) -> None:
    if canonical_metadata.publish_status != PublishStatus.PUBLISHED:
        return

    session = getattr(document_repo, "_session", None)
    if session is None:
        return

    from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository

    repo = PublishedDocumentRepository(session)
    existing = repo.get_by_final_doc_id(canonical_metadata.doc_id)
    if existing is not None:
        return

    repo.create(
        published_document_id=f"pub_{_stable_suffix(canonical_metadata.doc_id)}",
        final_doc_id=canonical_metadata.doc_id,
        logical_document_id=canonical_metadata.logical_document_id,
        tenant_id=canonical_metadata.tenant_id,
        collection_id=canonical_metadata.collection_id,
        version=canonical_metadata.version,
        source_content_hash=canonical_metadata.source_content_hash or canonical_metadata.source_hash,
        canonical_hash=_canonical_asset_hash(canonical_metadata.asset_paths.get("canonical_md", "")),
        state=PublishedDocumentState.PUBLISHED,
        active_index_version="",
        asset_paths=dict(canonical_metadata.asset_paths or {}),
    )


def _stable_suffix(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:20]


def _canonical_asset_hash(asset_ref: str) -> str:
    path = Path(asset_ref)
    if not asset_ref or not path.exists() or not path.is_file():
        return ""
    return "sha256:" + sha256(path.read_bytes()).hexdigest()
