import asyncio

from fastapi.testclient import TestClient

from reality_rag_contracts import IndexJobRequest

import ingestion_worker.indexing_service as mod
from ingestion_worker.app_factory import create_app


class _FakeIndexedDocument:
    def __init__(self, chunk_count: int):
        self.chunk_count = chunk_count


class _FakeIndexedDocumentRepository:
    def __init__(self, session):
        self._session = session

    def get_by_final_doc_and_version(self, final_doc_id: str, index_version: str):
        return _FakeIndexedDocument(chunk_count=7)


class _FakeSession:
    def close(self):
        return None


def _prepared_document(*, parse_snapshot_id: str = "") -> mod._PreparedIndexDocument:
    return mod._PreparedIndexDocument(
        source_file_id="src-1",
        intake_job_id="job-1",
        tenant_id="default",
        collection_id="col-1",
        filename="policy.md",
        visibility="internal",
        trace_id="trace-1",
        parse_snapshot_id=parse_snapshot_id,
        final_doc_id="doc-1",
        document_version="v1",
        publish_version="v1",
        source_binary_ref="C:/tmp/policy.md",
        canonical_asset_ref="C:/tmp/policy.md",
        sanitized_asset_ref="C:/tmp/policy.md",
        quality_report_ref=None,
        metadata_ref="C:/tmp/meta.json",
        approval_ref="C:/tmp/approval.json",
        governance_overlay_ref="C:/tmp/governance.json",
        source_metadata={"source_file_id": "src-1"},
    )


class _FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.text)


def test_indexing_service_run_forwards_to_modern_owner(monkeypatch):
    calls: list[tuple[str, str]] = []
    updates: list[tuple[str, str, str]] = []

    class FakeAsyncClient:
        def __init__(self, timeout=180.0, **kwargs):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None):
            calls.append(("POST", url))
            if url.endswith("/internal/parse-previews"):
                return _FakeResponse({"parse_snapshot_id": "snap-1"})
            if url.endswith("/internal/index-jobs"):
                return _FakeResponse({"build_job_id": "build-1"})
            if url.endswith("/internal/index-versions/ver-1/activate"):
                return _FakeResponse({})
            raise AssertionError(f"unexpected POST {url}")

        async def get(self, url):
            calls.append(("GET", url))
            if url.endswith("/internal/index-jobs/build-1"):
                return _FakeResponse(
                    {
                        "build_job_id": "build-1",
                        "status": "READY",
                        "index_version_id": "ver-1",
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setenv("INDEXING_SERVICE_URL", "http://indexing-owner:18080")
    monkeypatch.setattr(mod, "_REMOTE_URL", None)
    monkeypatch.setattr(mod, "_load_prepared_documents", lambda request: [_prepared_document()])
    monkeypatch.setattr(mod, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(mod, "IndexedDocumentRepository", _FakeIndexedDocumentRepository)
    monkeypatch.setattr(
        mod,
        "_update_document_index_state",
        lambda final_doc_id, *, index_version_id, status: updates.append(
            (final_doc_id, index_version_id, status.value)
        ),
    )
    monkeypatch.setattr(
        mod,
        "_build_publish_request_payload",
        lambda *, document, parse_snapshot_id, index_profile_id, target_index_version_id=None: {
            "document_id": document.final_doc_id,
            "parse_snapshot_id": parse_snapshot_id,
            "index_profile_id": index_profile_id,
            "target_index_version_id": target_index_version_id,
        },
    )
    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        mod.IndexingService().run(
            IndexJobRequest(
                job_id="job-1",
                collection_id="col-1",
                index_version="ver-1",
                options={},
            )
        )
    )

    assert result.status.value == "completed"
    assert result.documents_indexed == 1
    assert result.chunks_indexed == 7
    assert result.backend_mode == "modern-indexing-service"
    assert updates == [("doc-1", "ver-1", "indexed")]
    assert calls == [
        ("POST", "http://indexing-owner:18080/internal/parse-previews"),
        ("POST", "http://indexing-owner:18080/internal/index-jobs"),
        ("GET", "http://indexing-owner:18080/internal/index-jobs/build-1"),
        ("POST", "http://indexing-owner:18080/internal/index-versions/ver-1/activate"),
    ]


def test_run_intake_job_skips_preview_when_snapshot_exists(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeAsyncClient:
        def __init__(self, timeout=180.0, **kwargs):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json=None):
            calls.append(("POST", url))
            if url.endswith("/internal/index-jobs"):
                return _FakeResponse({"build_job_id": "build-2"})
            raise AssertionError(f"unexpected POST {url}")

        async def get(self, url):
            calls.append(("GET", url))
            if url.endswith("/internal/index-jobs/build-2"):
                return _FakeResponse(
                    {
                        "build_job_id": "build-2",
                        "status": "READY",
                        "index_version_id": "ver-2",
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setenv("INDEXING_SERVICE_URL", "http://indexing-owner:18080")
    monkeypatch.setattr(mod, "_REMOTE_URL", None)
    monkeypatch.setattr(
        mod,
        "_load_prepared_document_for_intake_job",
        lambda intake_job_id, publish_version_override=None: _prepared_document(parse_snapshot_id="snap-existing"),
    )
    monkeypatch.setattr(mod, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(mod, "IndexedDocumentRepository", _FakeIndexedDocumentRepository)
    monkeypatch.setattr(mod, "_update_document_index_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        mod,
        "_build_publish_request_payload",
        lambda *, document, parse_snapshot_id, index_profile_id, target_index_version_id=None: {
            "document_id": document.final_doc_id,
            "parse_snapshot_id": parse_snapshot_id,
            "index_profile_id": index_profile_id,
            "target_index_version_id": target_index_version_id,
        },
    )
    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        mod.IndexingService().run_intake_job(
            intake_job_id="job-2",
            collection_id="col-1",
            index_version="ver-2",
            options={"activate_index_version": False},
        )
    )

    assert result.status.value == "completed"
    assert result.documents_indexed == 1
    assert calls == [
        ("POST", "http://indexing-owner:18080/internal/index-jobs"),
        ("GET", "http://indexing-owner:18080/internal/index-jobs/build-2"),
    ]


def test_activate_and_rollback_use_remote_owner(monkeypatch):
    calls: list[str] = []

    class FakeAsyncClient:
        def __init__(self, timeout=30.0, **kwargs):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url):
            calls.append(url)
            return _FakeResponse({})

    monkeypatch.setenv("INDEXING_SERVICE_URL", "http://indexing-owner:18080")
    monkeypatch.setattr(mod, "_REMOTE_URL", None)
    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(mod._RemoteIndexingService, "_active_index_version", staticmethod(lambda collection_id: "ver-active"))
    monkeypatch.setattr(mod._RemoteIndexingService, "_latest_index_version", staticmethod(lambda collection_id: "ver-latest"))
    monkeypatch.setattr(mod._RemoteIndexingService, "_previous_index_version", staticmethod(lambda index_version_id: "ver-previous"))

    service = mod.IndexingService()
    activated = service.activate("col-1")
    rolled_back = service.rollback("col-1", "ver-active")

    assert activated.active_index_version == "ver-latest"
    assert activated.previous_index_version == "ver-active"
    assert rolled_back.active_index_version == "ver-previous"
    assert rolled_back.previous_index_version == "ver-active"
    assert calls == [
        "http://indexing-owner:18080/internal/index-versions/ver-latest/activate",
        "http://indexing-owner:18080/internal/index-versions/ver-active/rollback",
    ]


def test_indexing_endpoints_delegate_to_service(monkeypatch):
    class FakeIndexingService:
        async def run(self, request):
            return {"job_id": request.job_id, "collection_id": request.collection_id, "index_version": request.index_version, "status": "completed", "documents_indexed": 1, "chunks_indexed": 2, "backend_mode": "fake"}

        def activate(self, collection_id, index_version):
            return {"collection_id": collection_id, "active_index_version": index_version, "previous_index_version": "old", "target_index_version": index_version, "status": "indexed"}

        def rollback(self, collection_id, index_version):
            return {"collection_id": collection_id, "active_index_version": "old", "previous_index_version": index_version, "target_index_version": "old", "status": "indexed"}

    with TestClient(
        create_app(
            indexing_service_factory=lambda: FakeIndexingService(),
            include_monitor_routes=False,
            start_background_poller=False,
        )
    ) as client:

        run_resp = client.post(
            "/internal/indexing/run",
            json={"job_id": "job-1", "collection_id": "col-1", "index_version": "ver-1", "options": {}},
        )
        activate_resp = client.post(
            "/internal/indexing/activate",
            json={"collection_id": "col-1", "index_version": "ver-1"},
        )
        rollback_resp = client.post(
            "/internal/indexing/rollback",
            json={"collection_id": "col-1", "index_version": "ver-1"},
        )

        assert run_resp.status_code == 200
        assert run_resp.json()["backend_mode"] == "fake"
        assert activate_resp.status_code == 200
        assert activate_resp.json()["active_index_version"] == "ver-1"
        assert rollback_resp.status_code == 200
        assert rollback_resp.json()["active_index_version"] == "old"
