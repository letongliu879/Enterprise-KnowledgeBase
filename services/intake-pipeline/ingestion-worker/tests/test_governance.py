"""Governance tests: DocumentPolicy auto-creation and authority_level enforcement."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from reality_rag_contracts import AgentReview, Collection, PublishStatus, ReviewDecision, Tenant
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.document_policies import DocumentPolicyRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.tenants import TenantRepository


class TestPipelineRejectsMissingCollection:
    def test_pipeline_rejects_missing_collection(self, monkeypatch, tmp_path, inprocess_document_owner):
        from tests.fake_converter import FakeConverter
        from ingestion_worker.pipeline import IngestionPipeline

        monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", str(tmp_path))

        converter = FakeConverter(canonical_md="test")
        reviewer = MagicMock()
        pipeline = IngestionPipeline(converters=[converter], agent_reviewer=reviewer)

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("test")
            source_path = f.name

        try:
            with pytest.raises(ValueError, match="Collection 'col-missing' not found"):
                pipeline.run("col-missing", [source_path])
        finally:
            Path(source_path).unlink()


class TestPipelineRejectsDefaultAuthorityLevel:
    def test_pipeline_rejects_default_authority_level(self, monkeypatch, tmp_path, inprocess_document_owner):
        from tests.fake_converter import FakeConverter
        from ingestion_worker.pipeline import IngestionPipeline

        monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", str(tmp_path))

        # Seed tenant + collection with authority_level == 0 (default)
        session = get_session()
        try:
            TenantRepository(session).save(Tenant(tenant_id="default", name="Default Tenant"))
            CollectionRepository(session).save(
                Collection(
                    collection_id="col-zero",
                    tenant_id="default",
                    name="Zero Authority Collection",
                    authority_level=0,
                )
            )
            session.commit()
        finally:
            session.close()

        converter = FakeConverter(canonical_md="test")
        reviewer = MagicMock()
        pipeline = IngestionPipeline(converters=[converter], agent_reviewer=reviewer)

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("test")
            source_path = f.name

        try:
            with pytest.raises(
                ValueError, match="Collection 'col-zero' authority_level must be explicitly set"
            ):
                pipeline.run("col-zero", [source_path])
        finally:
            Path(source_path).unlink()
