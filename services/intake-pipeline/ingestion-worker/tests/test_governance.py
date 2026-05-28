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


class TestPipelineCreatesDocumentPolicy:
    def test_pipeline_creates_document_policy(self, monkeypatch, tmp_path):
        from ingestion_worker.pipeline import IngestionPipeline
        from tests.fake_converter import FakeConverter

        monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", str(tmp_path))

        # Seed tenant + collection with authority_level > 0
        session = get_session()
        try:
            TenantRepository(session).save(Tenant(tenant_id="default", name="Default Tenant"))
            CollectionRepository(session).save(
                Collection(
                    collection_id="col-gov",
                    tenant_id="default",
                    name="Governance Collection",
                    authority_level=5,
                )
            )
            session.commit()
        finally:
            session.close()

        converter = FakeConverter(canonical_md="D" * 240)
        reviewer = MagicMock()
        reviewer.review.return_value = AgentReview(
            doc_id="doc",
            decision=ReviewDecision("approve"),
            confidence=0.9,
            reasons=["ok"],
            risk_tags=[],
            suggested_actions=[],
            publish_recommendation=PublishStatus.PUBLISHED,
            sections_requiring_review=[],
            document_type="policy",
            suggested_authority_level=3,
            detected_pii=[],
            diff_summary="",
        )
        pipeline = IngestionPipeline(converters=[converter], agent_reviewer=reviewer)

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("D" * 240)
            source_path = f.name

        try:
            job = pipeline.run("col-gov", [source_path])
            detail = job.conversion_report.details[0]
            doc_id = detail.doc_id

            session = get_session()
            try:
                policy = DocumentPolicyRepository(session).get_by_doc_id(doc_id)
            finally:
                session.close()

            assert policy is not None
            assert policy.policy_id == f"dp-{doc_id}"
            assert policy.effect == "allow"
            assert policy.subjects[0].subject_type == "tenant"
            assert policy.subjects[0].subject_id == "default"
            assert policy.conditions[0].field == "clearance_level"
            assert policy.conditions[0].operator == "gte"
            assert policy.conditions[0].value == 5
            assert policy.priority == 100
            assert policy.policy_version == "v1"
        finally:
            Path(source_path).unlink()

    def test_pipeline_no_duplicate_policy(self, monkeypatch, tmp_path):
        from ingestion_worker.pipeline import IngestionPipeline
        from tests.fake_converter import FakeConverter

        monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", str(tmp_path))

        session = get_session()
        try:
            TenantRepository(session).save(Tenant(tenant_id="default", name="Default Tenant"))
            CollectionRepository(session).save(
                Collection(
                    collection_id="col-dedup",
                    tenant_id="default",
                    name="Dedup Collection",
                    authority_level=3,
                )
            )
            session.commit()
        finally:
            session.close()

        converter = FakeConverter(canonical_md="E" * 240)
        reviewer = MagicMock()
        reviewer.review.return_value = AgentReview(
            doc_id="doc",
            decision=ReviewDecision("approve"),
            confidence=0.9,
            reasons=["ok"],
            risk_tags=[],
            suggested_actions=[],
            publish_recommendation=PublishStatus.PUBLISHED,
            sections_requiring_review=[],
            document_type="policy",
            suggested_authority_level=3,
            detected_pii=[],
            diff_summary="",
        )
        pipeline = IngestionPipeline(converters=[converter], agent_reviewer=reviewer)

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("E" * 240)
            source_path = f.name

        try:
            job1 = pipeline.run("col-dedup", [source_path])
            doc_id = job1.conversion_report.details[0].doc_id

            # Re-run with same source file (same doc_id because same path)
            job2 = pipeline.run("col-dedup", [source_path])

            session = get_session()
            try:
                policies = (
                    session.query(
                        __import__(
                            "reality_rag_persistence.models", fromlist=["DocumentPolicyModel"]
                        ).DocumentPolicyModel
                    )
                    .filter_by(doc_id=doc_id)
                    .all()
                )
            finally:
                session.close()

            assert len(policies) == 1
        finally:
            Path(source_path).unlink()


class TestPipelineRejectsMissingCollection:
    def test_pipeline_rejects_missing_collection(self, monkeypatch, tmp_path):
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
    def test_pipeline_rejects_default_authority_level(self, monkeypatch, tmp_path):
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
