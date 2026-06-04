"""Tests for Phase 1 stage schemas, adapters, and pure executors.

Principles:
  - Schema tests do NOT depend on real DB session.
  - Pure executors work with mock/stub data.
  - Adapters correctly map legacy StageContext <-> new schemas.
  - Hash computation is deterministic.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from reality_rag_contracts import (
    AgentReview,
    CanonicalMetadata,
    Collection,
    ConversionResult,
    ConversionStatus,
    DocumentSupportTier,
    IndexStatus,
    PublishStatus,
    QualityReport,
    ReviewDecision,
    Tenant,
)

from ingestion_worker.domains.publishing_domain import persist_document_and_policy

from intake_runtime.stages import (
    ConversionStageInput,
    ConversionStageOutput,
    PublishingStageInput,
    PublishingStageOutput,
    ReviewStageInput,
    ReviewStageOutput,
    VersionConflictInfo,
    adapters,
    hash_utils,
    pure_stages,
)
from intake_runtime.stages.protocol import StageContext


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_collection(authority_level: int = 5) -> Collection:
    return Collection(
        collection_id="col-1",
        tenant_id="default",
        name="Test Collection",
        authority_level=authority_level,
    )


def _make_tenant() -> Tenant:
    return Tenant(tenant_id="default", name="Default Tenant")


def _make_ctx(**overrides) -> StageContext:
    defaults = {
        "collection_id": "col-1",
        "source_file_path": "/tmp/test.txt",
        "collection": _make_collection(),
        "tenant": _make_tenant(),
        "job_id": "job-test",
        "index_version": "v1",
    }
    defaults.update(overrides)
    return StageContext(**defaults)


def _success_result(canonical_md: str = "Hello world") -> ConversionResult:
    return ConversionResult(
        source_file_path="/tmp/test.txt",
        conversion_status=ConversionStatus.SUCCESS,
        canonical_md=canonical_md,
        metadata={"converter": "test", "extension": ".txt"},
    )


def _quality_report() -> QualityReport:
    return QualityReport(
        doc_id="doc-test",
        support_tier=DocumentSupportTier.A,
        conversion_score=1.0,
        recommended_review_status=PublishStatus.PUBLISHED,
    )


def _agent_review(decision: ReviewDecision = ReviewDecision.APPROVE) -> AgentReview:
    return AgentReview(
        doc_id="doc-test",
        decision=decision,
        confidence=0.95,
        publish_recommendation=PublishStatus.PUBLISHED,
    )


# ── Schema Dataclass Tests ────────────────────────────────────────────────────


class TestSchemaDataclasses:
    """[RETAIN] Schema dataclasses must be constructible and round-trip via asdict."""

    def test_conversion_stage_input_defaults(self):
        inp = ConversionStageInput()
        assert inp.schema_version == "v1"
        assert inp.intake_job_id == ""
        assert inp.collection_authority_level == 0

    def test_conversion_stage_output_hash_fields(self):
        out = ConversionStageOutput(
            input_hash="abc123",
            result_hash="def456",
            preliminary_doc_id="pre-doc-1",
            logical_document_id="log-doc-1",
        )
        assert out.input_hash == "abc123"
        assert out.result_hash == "def456"
        assert out.preliminary_doc_id == "pre-doc-1"
        assert out.logical_document_id == "log-doc-1"
        assert out.dedup_skipped is False

    def test_version_conflict_info(self):
        vc = VersionConflictInfo(
            logical_document_id="log-1",
            existing_version=1,
            proposed_version=2,
            existing_doc_id="doc-old",
            conflict_type="new_version",
        )
        assert vc.proposed_version == 2
        assert vc.conflict_type == "new_version"

    def test_review_stage_input(self):
        qr = _quality_report()
        inp = ReviewStageInput(
            intake_job_id="job-1",
            preliminary_doc_id="pre-doc-1",
            canonical_content="Hello world",
            quality_report=qr,
        )
        assert inp.quality_report is qr
        assert inp.review_model == ""

    def test_publishing_stage_input_requires_publish_status(self):
        inp = PublishingStageInput(
            intake_job_id="job-1",
            preliminary_doc_id="pre-doc-1",
            publish_status=PublishStatus.PUBLISHED,
        )
        assert inp.publish_status == PublishStatus.PUBLISHED

    def test_asdict_roundtrip(self):
        """Schemas must serialize for hashing via canonical_json."""
        from intake_runtime.stages.hash_utils import canonical_json

        out = ConversionStageOutput(
            preliminary_doc_id="pre-1",
            conversion_result=_success_result(),
        )
        d = asdict(out)
        assert d["preliminary_doc_id"] == "pre-1"
        # Pydantic models inside dataclasses need canonical_json for full serialization
        json_str = canonical_json(out)
        assert '"preliminary_doc_id":"pre-1"' in json_str
        assert '"conversion_status":"success"' in json_str


# ── Hash Utils Tests ──────────────────────────────────────────────────────────


class TestHashUtils:
    """[RETAIN] Hash computation must be deterministic and sensitive to content."""

    def test_canonical_json_sorts_keys(self):
        d = {"z": 1, "a": 2, "m": 3}
        s = hash_utils.canonical_json(d)
        assert s == '{"a":2,"m":3,"z":1}'

    def test_canonical_json_handles_enum(self):
        from reality_rag_contracts import PublishStatus

        d = {"status": PublishStatus.PUBLISHED}
        s = hash_utils.canonical_json(d)
        assert "published" in s

    def test_same_input_same_hash(self):
        inp = ConversionStageInput(intake_job_id="j1", collection_id="c1")
        h1 = hash_utils.compute_input_hash(inp)
        h2 = hash_utils.compute_input_hash(inp)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_input_different_hash(self):
        inp1 = ConversionStageInput(intake_job_id="j1")
        inp2 = ConversionStageInput(intake_job_id="j2")
        h1 = hash_utils.compute_input_hash(inp1)
        h2 = hash_utils.compute_input_hash(inp2)
        assert h1 != h2

    def test_result_hash_excludes_hash_fields(self):
        out = ConversionStageOutput(input_hash="abc", result_hash="def")
        h = hash_utils.compute_result_hash(out)
        # Changing hash fields should NOT change result_hash
        out2 = ConversionStageOutput(input_hash="xyz", result_hash="uvw")
        h2 = hash_utils.compute_result_hash(out2)
        assert h == h2

    def test_result_hash_sensitive_to_business_fields(self):
        out1 = ConversionStageOutput(preliminary_doc_id="a")
        out2 = ConversionStageOutput(preliminary_doc_id="b")
        assert hash_utils.compute_result_hash(out1) != hash_utils.compute_result_hash(out2)


# ── Adapter Tests ─────────────────────────────────────────────────────────────


class TestAdapters:
    """[RETAIN] Adapters must correctly map legacy StageContext <-> new schemas."""

    def test_ctx_to_conversion_input(self):
        ctx = _make_ctx(job_id="job-abc", source_file_path="/docs/file.txt")
        inp = adapters.ctx_to_conversion_input(ctx)
        assert inp.intake_job_id == "job-abc"
        assert inp.source_file_path == "/docs/file.txt"
        assert inp.tenant_id == "default"
        assert inp.collection_authority_level == 5

    def test_conversion_output_to_ctx(self):
        ctx = _make_ctx()
        out = ConversionStageOutput(
            preliminary_doc_id="pre-doc-1",
            logical_document_id="log-1",
            version=2,
            source_hash="sha256:abc",
            dedup_skipped=True,
            skip_reason="duplicate",
        )
        ctx = adapters.conversion_output_to_ctx(out, ctx)
        assert ctx.doc_id == "pre-doc-1"  # legacy field
        assert ctx.logical_document_id == "log-1"
        assert ctx.version == 2
        assert ctx.source_hash == "sha256:abc"
        assert ctx.skipped is True
        assert ctx.skip_reason == "duplicate"

    def test_ctx_to_review_input(self):
        ctx = _make_ctx(
            doc_id="pre-doc-1",
            logical_document_id="log-1",
            result=_success_result(),
            quality_report=_quality_report(),
        )
        inp = adapters.ctx_to_review_input(ctx)
        assert inp.preliminary_doc_id == "pre-doc-1"
        assert inp.logical_document_id == "log-1"
        assert inp.canonical_content == "Hello world"
        assert inp.quality_report is not None

    def test_ctx_to_publishing_input(self):
        ctx = _make_ctx(
            doc_id="pre-doc-1",
            final_doc_id="doc-final-1",
            logical_document_id="log-1",
            version=2,
            source_hash="sha256:abc",
            result=_success_result(),
            quality_report=_quality_report(),
            agent_review=_agent_review(),
            publish_status=PublishStatus.PUBLISHED,
        )
        inp = adapters.ctx_to_publishing_input(ctx)
        assert inp.preliminary_doc_id == "pre-doc-1"
        assert inp.final_doc_id == "doc-final-1"
        assert inp.version == 2
        assert inp.publish_status == PublishStatus.PUBLISHED
        assert inp.agent_review is not None

    def test_preliminary_doc_id_and_final_doc_id_are_distinct_fields(self):
        """[RETAIN] publishing input keeps both candidate and final identities."""
        ctx = _make_ctx(doc_id="pre-doc-1", final_doc_id="doc-final-1")
        inp = adapters.ctx_to_publishing_input(ctx)
        assert inp.preliminary_doc_id == "pre-doc-1"
        assert inp.final_doc_id == "doc-final-1"


# ── Pure Conversion Executor Tests ────────────────────────────────────────────


class FakeConverter:
    """Test converter that produces deterministic output."""

    def supported_extensions(self):
        return [".txt", ".md"]

    def convert(self, request):
        return ConversionResult(
            source_file_path=request.source_file_path,
            conversion_status=ConversionStatus.SUCCESS,
            canonical_md="Fake converted content",
            metadata={"converter": "fake", "extension": ".txt"},
        )


class TestPureConversionStage:
    """[RETAIN] Pure conversion executor works without DB session."""

    def test_successful_conversion(self):
        inp = ConversionStageInput(
            intake_job_id="job-1",
            collection_id="col-1",
            source_file_path="/tmp/test.txt",
        )
        out = pure_stages.run_conversion_stage(inp, [FakeConverter()])
        assert out.conversion_result is not None
        assert out.conversion_result.conversion_status == ConversionStatus.SUCCESS
        assert out.preliminary_doc_id != ""
        assert out.logical_document_id != ""
        assert out.version == 1
        assert out.quality_report is not None
        assert out.dedup_skipped is False
        assert out.input_hash != ""
        assert out.result_hash != ""

    def test_unsupported_extension(self):
        inp = ConversionStageInput(source_file_path="/tmp/test.unknown")
        out = pure_stages.run_conversion_stage(inp, [FakeConverter()])
        assert out.conversion_result.conversion_status == ConversionStatus.UNSUPPORTED
        assert out.preliminary_doc_id == ""
        assert out.quality_report is None

    def test_dedup_skip(self):
        """[TRANSITIONAL] Dedup lookup result injected, no DB needed."""
        inp = ConversionStageInput(source_file_path="/tmp/test.txt")
        out = pure_stages.run_conversion_stage(
            inp,
            [FakeConverter()],
            existing_published_doc_id="existing-doc-1",
        )
        assert out.dedup_skipped is True
        assert out.skip_reason == "duplicate"
        assert out.preliminary_doc_id == "existing-doc-1"

    def test_version_conflict_detected(self):
        """[TRANSITIONAL] Version conflict info when latest_version > 0."""
        inp = ConversionStageInput(source_file_path="/tmp/test.txt")
        out = pure_stages.run_conversion_stage(
            inp,
            [FakeConverter()],
            latest_version=3,
        )
        assert out.version == 4
        assert out.version_conflict is not None
        assert out.version_conflict.existing_version == 3
        assert out.version_conflict.proposed_version == 4
        assert out.version_conflict.conflict_type == "new_version"

    def test_no_version_conflict_on_first_version(self):
        inp = ConversionStageInput(source_file_path="/tmp/test.txt")
        out = pure_stages.run_conversion_stage(inp, [FakeConverter()])
        assert out.version == 1
        assert out.version_conflict is None

    def test_quality_report_blocking_reasons(self):
        class BadConverter:
            def supported_extensions(self):
                return [".txt"]

            def convert(self, request):
                return ConversionResult(
                    source_file_path=request.source_file_path,
                    conversion_status=ConversionStatus.SUCCESS,
                    canonical_md="",
                    metadata={"file_size": 0},
                )

        inp = ConversionStageInput(source_file_path="/tmp/test.txt")
        out = pure_stages.run_conversion_stage(inp, [BadConverter()])
        assert out.quality_report is not None
        assert "Empty canonical markdown" in out.quality_report.blocking_reasons
        assert out.quality_report.support_tier == DocumentSupportTier.D


# ── Pure Review Executor Tests ────────────────────────────────────────────────


class FakeReviewer:
    def review(self, *, doc_id, canonical_content, quality_report, event_hook=None):
        return AgentReview(
            doc_id=doc_id,
            decision=ReviewDecision.APPROVE,
            confidence=0.99,
            publish_recommendation=PublishStatus.PUBLISHED,
        )


class TestPureReviewStage:
    """[RETAIN] Pure review executor works without DB session."""

    def test_review_success(self):
        inp = ReviewStageInput(
            preliminary_doc_id="pre-1",
            canonical_content="Hello world",
            quality_report=_quality_report(),
        )
        out = pure_stages.run_review_stage(inp, FakeReviewer())
        assert out.agent_review is not None
        assert out.agent_review.decision == ReviewDecision.APPROVE
        assert out.cache_hit is False
        assert out.input_hash != ""
        assert out.result_hash != ""

    def test_review_skipped_without_quality_report(self):
        inp = ReviewStageInput(preliminary_doc_id="pre-1")
        out = pure_stages.run_review_stage(inp, FakeReviewer())
        assert out.agent_review is None
        assert out.input_hash != ""

    def test_review_with_cache_hit(self):
        from intake_runtime.agent_review_cache import InMemoryAgentReviewCache

        cache = InMemoryAgentReviewCache()
        cached = AgentReview(
            doc_id="",
            decision=ReviewDecision.REJECT,
            confidence=0.8,
        )
        # Inject into cache via public API
        cache.set("fake-key", cached, ttl_seconds=99999999)

        # Patch build_cache_key to return our fake key
        import intake_runtime.agent_review_cache as arc
        original_build = arc.build_cache_key
        try:
            arc.build_cache_key = lambda **kwargs: "fake-key"
            inp = ReviewStageInput(
                preliminary_doc_id="pre-1",
                canonical_content="Hello",
                quality_report=_quality_report(),
            )
            out = pure_stages.run_review_stage(inp, FakeReviewer(), cache)
            assert out.cache_hit is True
            assert out.agent_review.decision == ReviewDecision.REJECT
            assert out.agent_review.doc_id == "pre-1"
        finally:
            arc.build_cache_key = original_build


# ── Pure Publishing Executor Tests ────────────────────────────────────────────


class TestPurePublishingStage:
    """[RETAIN] Pure publishing executor works without DB (optional repos)."""

    def test_publishing_success(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", tmp)
            inp = PublishingStageInput(
                intake_job_id="job-1",
                collection_id="col-1",
                preliminary_doc_id="pre-doc-1",
                final_doc_id="doc-final-1",
                logical_document_id="log-1",
                version=1,
                source_hash="sha256:abc",
                tenant_id="default",
                collection_authority_level=5,
                conversion_result=_success_result(),
                quality_report=_quality_report(),
                agent_review=_agent_review(),
                publish_status=PublishStatus.PUBLISHED,
            )
            out = pure_stages.run_publishing_stage(inp)
            assert out.asset_paths != {}
            assert out.asset_bundle is not None
            assert out.canonical_metadata is not None
            assert out.document_persisted is False  # no repo
            assert out.policy_persisted is False
            assert out.input_hash != ""
            assert out.result_hash != ""

            # Verify sidecar files were written
            assert Path(out.asset_paths["canonical_md"]).exists()
            assert Path(out.asset_paths["canonical_meta"]).exists()
            assert Path(out.asset_paths["chunk_manifest"]).exists()
            assert "doc-final-1" in out.asset_paths["canonical_md"]

    def test_publishing_skips_on_conversion_failure(self):
        inp = PublishingStageInput(
            conversion_result=ConversionResult(
                source_file_path="/tmp/test.txt",
                conversion_status=ConversionStatus.FAILED,
            ),
        )
        out = pure_stages.run_publishing_stage(inp)
        assert out.asset_paths == {}
        assert out.asset_bundle is None
        assert out.canonical_metadata is None

    def test_publishing_with_repos(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", tmp)
            doc_repo = MagicMock()
            doc_repo._session = None
            policy_repo = MagicMock()
            policy_repo._session = None
            policy_repo.get.return_value = None

            inp = PublishingStageInput(
                collection_id="col-1",
                preliminary_doc_id="pre-doc-1",
                final_doc_id="doc-final-1",
                tenant_id="default",
                collection_authority_level=5,
                conversion_result=_success_result(),
                publish_status=PublishStatus.PUBLISHED,
            )
            out = pure_stages.run_publishing_stage(
                inp, document_repo=doc_repo, policy_repo=policy_repo, persist_fn=persist_document_and_policy
            )
            assert out.document_persisted is True
            assert out.policy_persisted is True
            doc_repo.save.assert_called_once()
            policy_repo.save.assert_called_once()
            assert doc_repo.save.call_args[0][0].doc_id == "doc-final-1"

    def test_canonical_metadata_uses_final_doc_id_when_present(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", tmp)
            inp = PublishingStageInput(
                collection_id="col-1",
                preliminary_doc_id="pre-doc-1",
                final_doc_id="doc-final-1",
                logical_document_id="log-1",
                conversion_result=_success_result(),
                publish_status=PublishStatus.PUBLISHED,
            )
            out = pure_stages.run_publishing_stage(inp)
            assert out.canonical_metadata.doc_id == "doc-final-1"
            assert out.canonical_metadata.logical_document_id == "log-1"

    def test_canonical_metadata_falls_back_to_preliminary_doc_id(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", tmp)
            inp = PublishingStageInput(
                collection_id="col-1",
                preliminary_doc_id="pre-doc-1",
                logical_document_id="log-1",
                conversion_result=_success_result(),
                publish_status=PublishStatus.PUBLISHED,
            )
            out = pure_stages.run_publishing_stage(inp)
            assert out.canonical_metadata.doc_id == "pre-doc-1"


# ── Pure Stage Runtime Independence Tests ─────────────────────────────────────


class TestPureStageRuntimeIndependence:
    def test_pure_conversion_does_not_use_session(self):
        inp = ConversionStageInput(
            intake_job_id="job-1",
            collection_id="col-1",
            source_file_path="/tmp/test.txt",
        )
        out = pure_stages.run_conversion_stage(inp, [FakeConverter()])
        assert out.conversion_result is not None

    def test_pure_review_does_not_use_session(self):
        inp = ReviewStageInput(
            preliminary_doc_id="pre-1",
            canonical_content="Hello world",
            quality_report=_quality_report(),
        )
        out = pure_stages.run_review_stage(inp, FakeReviewer())
        assert out.agent_review is not None

    def test_pure_publishing_does_not_require_session(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            import os

            os.environ["REALITY_RAG_SIDECAR_DIR"] = tmp
            try:
                inp = PublishingStageInput(
                    collection_id="col-1",
                    preliminary_doc_id="pre-doc-1",
                    conversion_result=_success_result(),
                    publish_status=PublishStatus.PUBLISHED,
                )
                out = pure_stages.run_publishing_stage(inp)
                assert out.asset_paths != {}
                assert out.document_persisted is False
                assert out.policy_persisted is False
            finally:
                del os.environ["REALITY_RAG_SIDECAR_DIR"]

    def test_adapter_does_not_add_session(self):
        ctx = _make_ctx()
        assert ctx.session is None
        inp = adapters.ctx_to_conversion_input(ctx)
        assert not hasattr(inp, "session")

    def test_pure_conversion_stage_produces_complete_identity_fields(self):
        inp_pure = ConversionStageInput(
            source_file_path="/tmp/test.txt",
            collection_id="col-1",
        )
        out_pure = pure_stages.run_conversion_stage(inp_pure, [FakeConverter()])

        assert out_pure.conversion_result is not None
        assert out_pure.conversion_result.conversion_status == ConversionStatus.SUCCESS
        assert out_pure.preliminary_doc_id.startswith("doc-")
        assert out_pure.logical_document_id != ""
        assert out_pure.version == 1


class TestIdempotencyKeyComposition:
    """[RETAIN] Verify that input_hash participates in idempotency correctly."""

    def test_same_input_same_hash(self):
        """Re-execution with identical input yields identical input_hash."""
        inp = ConversionStageInput(intake_job_id="j1", collection_id="c1")
        h1 = hash_utils.compute_input_hash(inp)
        h2 = hash_utils.compute_input_hash(inp)
        assert h1 == h2

    def test_schema_version_affects_hash(self):
        """Different schema_version = different input_hash."""
        inp1 = ConversionStageInput(schema_version="v1", intake_job_id="j1")
        inp2 = ConversionStageInput(schema_version="v2", intake_job_id="j1")
        h1 = hash_utils.compute_input_hash(inp1)
        h2 = hash_utils.compute_input_hash(inp2)
        assert h1 != h2

    def test_different_source_file_different_hash(self):
        inp1 = ConversionStageInput(source_file_path="/a.txt")
        inp2 = ConversionStageInput(source_file_path="/b.txt")
        assert hash_utils.compute_input_hash(inp1) != hash_utils.compute_input_hash(inp2)
