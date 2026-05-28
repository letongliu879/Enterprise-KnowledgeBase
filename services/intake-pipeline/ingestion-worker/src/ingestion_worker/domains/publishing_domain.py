"""Publishing domain — remote-or-local fallback selector.

If PUBLISHING_WORKER_URL is set, HTTP calls are forwarded to the remote
publishing-worker process.  Otherwise the local same-process logic is used.
This lets the monolith run standalone while allowing gradual splitting of
the publishing owner into its own deployable unit.

API contract (request/response models) is unchanged.
"""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from typing import Any

from reality_rag_contracts import CanonicalMetadata, PublishedDocumentState

__all__ = ["persist_document_and_policy"]

_REMOTE_URL: str | None = None


def _get_remote_url() -> str | None:
    global _REMOTE_URL
    if _REMOTE_URL is None:
        _REMOTE_URL = os.environ.get("PUBLISHING_WORKER_URL", "").rstrip("/") or None
    return _REMOTE_URL


def _url(path: str) -> str:
    base = _get_remote_url()
    assert base is not None
    return f"{base}{path}"


class _RemotePublishingService:
    """HTTP client facade that mirrors PublishingService API."""

    def persist(
        self,
        canonical_metadata: CanonicalMetadata,
        *,
        collection_authority_level: int = 0,
    ) -> tuple[bool, bool]:
        import httpx

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _url("/internal/publishing/persist"),
                json={
                    "canonical_metadata": canonical_metadata.model_dump(mode="json"),
                    "collection_authority_level": collection_authority_level,
                },
            )
            if resp.status_code >= 400:
                raise RuntimeError(resp.text)
            result = resp.json()
            return result["document_persisted"], result["policy_persisted"]


def persist_document_and_policy(
    canonical_metadata: CanonicalMetadata,
    *,
    document_repo=None,
    policy_repo=None,
    collection_authority_level: int = 0,
) -> tuple[bool, bool]:
    """Persist canonical metadata and optional policy.

    If PUBLISHING_WORKER_URL is set, forwards to remote publishing-worker.
    Otherwise uses local document_repo / policy_repo directly.
    """
    if document_repo is not None or policy_repo is not None:
        remote_url = None
    else:
        remote_url = _get_remote_url()

    if remote_url is not None:
        return _RemotePublishingService().persist(
            canonical_metadata,
            collection_authority_level=collection_authority_level,
        )

    # Local fallback — use the passed-in repos directly
    document_persisted = False
    policy_persisted = False

    if document_repo is not None:
        document_repo.save(canonical_metadata)
        _upsert_published_document(canonical_metadata, document_repo=document_repo)
        document_persisted = True

    if policy_repo is not None and canonical_metadata.publish_status.value == "published":
        from reality_rag_contracts import DocumentPolicy, PolicyCondition, PolicySubject

        policy_id = f"dp-{canonical_metadata.doc_id}"
        existing = policy_repo.get(policy_id)
        if existing is None:
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

    return document_persisted, policy_persisted


def _upsert_published_document(
    canonical_metadata: CanonicalMetadata,
    *,
    document_repo,
) -> None:
    if canonical_metadata.publish_status.value != "published":
        return
    session = getattr(document_repo, "_session", None)
    if session is None:
        return
    from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository

    repo = PublishedDocumentRepository(session)
    existing = repo.get_by_final_doc_id(canonical_metadata.doc_id)
    if existing is not None:
        return
    canonical_hash = _canonical_asset_hash(canonical_metadata.asset_paths.get("canonical_md", ""))
    repo.create(
        published_document_id=f"pub_{_stable_suffix(canonical_metadata.doc_id)}",
        final_doc_id=canonical_metadata.doc_id,
        logical_document_id=canonical_metadata.logical_document_id,
        tenant_id=canonical_metadata.tenant_id,
        collection_id=canonical_metadata.collection_id,
        version=canonical_metadata.version,
        source_content_hash=canonical_metadata.source_content_hash or canonical_metadata.source_hash,
        canonical_hash=canonical_hash,
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
