import pytest

from reality_rag_contracts import CanonicalMetadata, IndexStatus, PublishStatus
from reality_rag_persistence.database import create_all, drop_all, get_session, override_url_for_testing
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.document_policies import DocumentPolicyRepository
from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository
from reality_rag_persistence.repositories.tenants import TenantRepository

from publishing_worker.publishing_domain import persist_document_and_policy


@pytest.fixture(autouse=True)
def _db():
    override_url_for_testing("sqlite:///:memory:")
    create_all()
    yield
    drop_all()


def _seed_dependencies(session) -> None:
    from reality_rag_contracts import Collection, Tenant

    if TenantRepository(session).get("default") is None:
        TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
    if CollectionRepository(session).get("col-1") is None:
        CollectionRepository(session).save(
            Collection(
                collection_id="col-1",
                tenant_id="default",
                name="Test Collection",
                authority_level=5,
            )
        )
    session.commit()


def test_persist_document_and_policy_writes_published_document_and_policy():
    session = get_session()
    try:
        _seed_dependencies(session)
        document_repo = DocumentRepository(session)
        policy_repo = DocumentPolicyRepository(session)

        metadata = CanonicalMetadata(
            tenant_id="default",
            collection_id="col-1",
            doc_id="doc-final-2",
            logical_document_id="logical-2",
            source_hash="sha256:src-2",
            source_content_hash="sha256:content-2",
            version=2,
            publish_status=PublishStatus.PUBLISHED,
            index_status=IndexStatus.INDEXING,
            authority_level=5,
            quality_summary="quality ok",
            processing_summary="processed",
            asset_paths={"canonical_md": __file__},
        )

        document_persisted, policy_persisted = persist_document_and_policy(
            metadata,
            document_repo=document_repo,
            policy_repo=policy_repo,
            collection_authority_level=5,
        )
        session.commit()

        assert document_persisted is True
        assert policy_persisted is True
        assert DocumentRepository(session).get("doc-final-2") is not None
        published = PublishedDocumentRepository(session).get_by_final_doc_id("doc-final-2")
        assert published is not None
        assert published.logical_document_id == "logical-2"
        assert published.version == 2
        assert published.source_content_hash == "sha256:content-2"
        assert DocumentPolicyRepository(session).get("dp-doc-final-2") is not None
    finally:
        session.close()
