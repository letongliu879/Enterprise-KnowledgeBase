import asyncio
import uuid

import pytest
from reality_rag_contracts import IndexAssetBundle, OpenSearchIndexRecord, QdrantPointRecord

from reality_rag_indexing import backends as mod


def _bundle() -> IndexAssetBundle:
    return IndexAssetBundle(
        doc_id="doc-1",
        collection_id="col-1",
        index_version="v1",
        canonical_source="canonical/doc-1.md",
        chunks=[],
        opensearch_records=[
            OpenSearchIndexRecord(
                index_name="reality-rag-col-1-v1",
                document_id="chunk-1",
                body={"doc_id": "doc-1", "content": "hello"},
            )
        ],
        qdrant_points=[
            QdrantPointRecord(
                collection_name="reality-rag-col-1-v1",
                point_id="chunk-1",
                payload={"doc_id": "doc-1", "content": "hello"},
            )
        ],
    )


def test_get_index_backend_defaults_to_hybrid(monkeypatch):
    monkeypatch.setenv("INDEX_BACKEND_MODE", "hybrid")
    monkeypatch.setenv("OPENSEARCH_URL", "http://opensearch:9200")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    backend = mod.get_index_backend()
    assert isinstance(backend, mod.HybridIndexBackend)


def test_get_index_backend_explicit_noop(monkeypatch):
    monkeypatch.setenv("INDEX_BACKEND_MODE", "noop")
    backend = mod.get_index_backend()
    assert isinstance(backend, mod.NoopIndexBackend)


def test_get_index_backend_builds_hybrid(monkeypatch):
    monkeypatch.setenv("INDEX_BACKEND_MODE", "hybrid")
    monkeypatch.setenv("OPENSEARCH_URL", "http://opensearch:9200")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    backend = mod.get_index_backend()
    assert isinstance(backend, mod.HybridIndexBackend)


def test_get_index_backend_requires_hybrid_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("INDEX_BACKEND_MODE", "noop")
    with pytest.raises(RuntimeError, match="must be 'hybrid'"):
        mod.get_index_backend()


def test_opensearch_index_writer_posts_bulk_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def json(self):
            return {"errors": False, "items": []}

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, timeout=15.0, **kwargs):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, content, headers):
            captured["url"] = url
            captured["content"] = content
            captured["headers"] = headers
            return FakeResponse()

        async def put(self, url, json):
            captured["ensure_url"] = url
            captured["ensure_json"] = json
            return type("Resp", (), {"status_code": 200, "raise_for_status": lambda self: None})()

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    writer = mod.OpenSearchIndexWriter(base_url="http://opensearch:9200")
    count = asyncio.run(
        writer.write_records([_bundle().opensearch_records[0].model_dump(mode="json")])
    )

    assert count == 1
    assert captured["ensure_url"] == "http://opensearch:9200/reality-rag-col-1-v1"
    assert captured["url"] == "http://opensearch:9200/_bulk"
    assert '"_index":"reality-rag-col-1-v1"' in captured["content"]
    assert captured["headers"]["Content-Type"] == "application/x-ndjson"


def test_opensearch_index_writer_raises_on_bulk_item_errors(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "errors": True,
                "items": [
                    {
                        "index": {
                            "error": {"type": "mapper_parsing_exception"},
                        }
                    }
                ],
            }

    class FakeAsyncClient:
        def __init__(self, timeout=15.0, **kwargs):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, content, headers):
            return FakeResponse()

        async def put(self, url, json):
            return type("Resp", (), {"status_code": 200, "raise_for_status": lambda self: None})()

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    writer = mod.OpenSearchIndexWriter(base_url="http://opensearch:9200")
    with pytest.raises(RuntimeError, match="OpenSearch bulk indexing reported errors"):
        asyncio.run(
            writer.write_records([_bundle().opensearch_records[0].model_dump(mode="json")])
        )


def test_qdrant_point_writer_puts_points(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, timeout=15.0, **kwargs):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def put(self, url, json):
            if url.endswith("/collections/reality-rag-col-1-v1"):
                captured["ensure_url"] = url
                captured["ensure_json"] = json
                return type("Resp", (), {"status_code": 200, "raise_for_status": lambda self: None})()
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)
    async def fake_embed_texts(texts, *, config=None):
        assert texts == ["hello"]
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("reality_rag_indexing.backends.embed_texts", fake_embed_texts)

    writer = mod.QdrantPointWriter(base_url="http://qdrant:6333")
    count = asyncio.run(
        writer.write_points(
            "reality-rag-col-1-v1",
            [_bundle().qdrant_points[0].model_dump(mode="json")],
        )
    )

    assert count == 1
    assert captured["ensure_url"] == "http://qdrant:6333/collections/reality-rag-col-1-v1"
    assert captured["url"] == "http://qdrant:6333/collections/reality-rag-col-1-v1/points"
    assert captured["json"]["points"][0]["id"] == str(uuid.uuid5(uuid.NAMESPACE_URL, "chunk-1"))
    assert captured["json"]["points"][0]["vector"] == [0.1, 0.2, 0.3]
