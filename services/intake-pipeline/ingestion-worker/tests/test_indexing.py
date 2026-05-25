import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from reality_rag_contracts import AgentReview, IndexJobRequest, IndexStatus, PublishStatus, ReviewDecision
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.index_registry import IndexRegistryRepository
from reality_rag_persistence.repositories.jobs import JobRepository

from ingestion_worker.domains.indexing_domain import IndexBuildInput, PerDocumentIndexResult
from ingestion_worker.main import app
from ingestion_worker.indexing_service import IndexingService


client = TestClient(app)


class _FakeIndexBackend:
    mode = "noop-test"

    def __init__(self):
        self.bundles = []

    async def index_bundle(self, bundle):
        self.bundles.append(bundle)
        return len(bundle.opensearch_records), len(bundle.qdrant_points)


def _approving_reviewer():
    reviewer = MagicMock()
    reviewer.review.return_value = AgentReview(
        doc_id="doc-approved",
        decision=ReviewDecision.APPROVE,
        confidence=0.99,
        reasons=["Approved for publication"],
        risk_tags=[],
        suggested_actions=[],
        publish_recommendation=PublishStatus.PUBLISHED,
        sections_requiring_review=[],
    )
    return reviewer


def _build_success_job(monkeypatch, tmp_path):
    from ingestion_worker.converters.markitdown_converter import MarkItDownConverter
    from ingestion_worker.pipeline import IngestionPipeline

    monkeypatch.setenv("REALITY_RAG_SIDECAR_DIR", str(tmp_path))
    converter = MarkItDownConverter()
    pipeline = IngestionPipeline(converters=[converter], agent_reviewer=_approving_reviewer())

    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("# Travel Policy\n\n" + ("Employees may reimburse travel and keep receipts. " * 8))
        source_path = f.name

    try:
        with patch.object(converter._markitdown, "convert") as mock_convert:
            mock_result = MagicMock()
            mock_result.text_content = "# Travel Policy\n\n" + ("Employees may reimburse travel and keep receipts. " * 8)
            mock_convert.return_value = mock_result
            job = pipeline.run("col-1", [source_path])
    finally:
        Path(source_path).unlink()

    return job


def test_indexing_service_updates_registry_and_document(monkeypatch, tmp_path):
    job = _build_success_job(monkeypatch, tmp_path)
    backend = _FakeIndexBackend()
    monkeypatch.setattr(
        "reality_rag_indexing.backends.get_index_backend", lambda: backend
    )

    service = IndexingService()

    import asyncio

    index_result = asyncio.run(
        service.run(
            IndexJobRequest(
                job_id=job.job_id,
                collection_id="col-1",
                index_version="col-1-v-final",
                options={},
            )
        )
    )

    assert index_result.status.value == "completed"
    assert index_result.documents_indexed == 1
    assert index_result.chunks_indexed >= 1
    assert index_result.backend_mode == "noop-test"

    detail = job.conversion_report.details[0]
    session = get_session()
    try:
        document = DocumentRepository(session).get(detail.doc_id)
        registry = IndexRegistryRepository(session).get("col-1")
        job_info = JobRepository(session).get(index_result.job_id)
    finally:
        session.close()

    assert document is not None
    assert document.index_status == IndexStatus.INDEXED
    assert registry is not None
    assert registry.index_version == "col-1-v-final"
    assert registry.status == "indexed"
    assert job_info is not None
    assert job_info.status.value == "completed"
    assert backend.bundles[0].opensearch_records[0].index_name == "reality-rag-col-1-v-final"
    assert backend.bundles[0].qdrant_points[0].collection_name == "reality-rag-col-1-v-final"
    assert backend.bundles[0].opensearch_records[0].body["chunk_metadata"]["index_status"] == "indexed"


def test_indexing_endpoint_runs_index_job(monkeypatch, tmp_path):
    job = _build_success_job(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "reality_rag_indexing.backends.get_index_backend", lambda: _FakeIndexBackend()
    )

    resp = client.post(
        "/internal/indexing/run",
        json={
            "job_id": job.job_id,
            "collection_id": "col-1",
            "index_version": "col-1-v-api",
            "options": {},
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["collection_id"] == "col-1"
    assert data["index_version"] == "col-1-v-api"
    assert data["status"] == "completed"
    assert data["documents_indexed"] == 1
    assert data["backend_mode"] == "noop-test"


def test_indexing_activate_and_rollback_endpoints(monkeypatch, tmp_path):
    job = _build_success_job(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "reality_rag_indexing.backends.get_index_backend", lambda: _FakeIndexBackend()
    )

    index_resp = client.post(
        "/internal/indexing/run",
        json={
            "job_id": job.job_id,
            "collection_id": "col-1",
            "index_version": "col-1-v-next",
            "options": {},
        },
    )
    assert index_resp.status_code == 200

    activate_resp = client.post(
        "/internal/indexing/activate",
        json={"collection_id": "col-1", "index_version": "col-1-v-next"},
    )
    assert activate_resp.status_code == 200
    activate_data = activate_resp.json()
    assert activate_data["active_index_version"] == "col-1-v-next"
    assert activate_data["status"] == "indexed"

    rollback_resp = client.post(
        "/internal/indexing/rollback",
        json={"collection_id": "col-1", "index_version": "col-1-v1"},
    )
    assert rollback_resp.status_code == 200
    rollback_data = rollback_resp.json()
    assert rollback_data["active_index_version"] == "col-1-v1"
    assert rollback_data["status"] == "indexed"


def test_run_build_consumes_explicit_input_without_ingestion_context(monkeypatch, tmp_path):
    """Core _run_build takes explicit doc_ids — it does NOT query IngestionRepository."""
    job = _build_success_job(monkeypatch, tmp_path)
    backend = _FakeIndexBackend()
    monkeypatch.setattr(
        "reality_rag_indexing.backends.get_index_backend", lambda: backend
    )

    service = IndexingService()

    # Extract the published doc_id directly from the ingestion job result.
    detail = job.conversion_report.details[0]
    doc_id = detail.doc_id

    # Prepare session and mark registry as indexing (normally done by run() adapter).
    session = get_session()
    try:
        registry_repo = IndexRegistryRepository(session)
        registry_repo.mark_indexing("col-1", "col-1-v-explicit")
        session.commit()

        build_input = IndexBuildInput(
            collection_id="col-1",
            index_version="col-1-v-explicit",
            doc_ids=[doc_id],
        )

        import asyncio

        output = asyncio.run(
            service._run_build(build_input, session=session, backend=backend)
        )

        # Verify output structure seeds future IndexReady.
        assert output.documents_indexed == 1
        assert output.chunks_indexed >= 1
        assert output.backend_mode == "noop-test"
        assert output.indexed_doc_ids == [doc_id]
        assert len(output.per_document_results) == 1
        assert output.per_document_results[0].doc_id == doc_id
        assert output.per_document_results[0].indexed is True
        assert output.per_document_results[0].chunk_count >= 1

        # Verify document was updated in DB.
        document = DocumentRepository(session).get(doc_id)
        assert document.index_status == IndexStatus.INDEXED

        # Verify registry was NOT activated by _run_build (caller responsibility).
        registry = registry_repo.get("col-1")
        assert registry.status == "indexing"  # still indexing, not activated yet
    finally:
        session.close()


def test_run_build_skips_unpublished_and_missing_docs(monkeypatch, tmp_path):
    """_run_build gracefully skips docs that are missing or not published."""
    job = _build_success_job(monkeypatch, tmp_path)
    backend = _FakeIndexBackend()
    monkeypatch.setattr(
        "reality_rag_indexing.backends.get_index_backend", lambda: backend
    )

    service = IndexingService()
    detail = job.conversion_report.details[0]

    session = get_session()
    try:
        registry_repo = IndexRegistryRepository(session)
        registry_repo.mark_indexing("col-1", "col-1-v-skip")
        session.commit()

        build_input = IndexBuildInput(
            collection_id="col-1",
            index_version="col-1-v-skip",
            doc_ids=[detail.doc_id, "missing-doc-id"],
        )

        import asyncio

        output = asyncio.run(
            service._run_build(build_input, session=session, backend=backend)
        )

        assert output.documents_indexed == 1
        assert output.missing_doc_ids == ["missing-doc-id"]
        assert output.indexed_doc_ids == [detail.doc_id]

        # Per-document results include both indexed and skipped.
        assert len(output.per_document_results) == 2
        by_doc = {r.doc_id: r for r in output.per_document_results}
        assert by_doc[detail.doc_id].indexed is True
        assert by_doc["missing-doc-id"].skip_reason == "missing"
    finally:
        session.close()
