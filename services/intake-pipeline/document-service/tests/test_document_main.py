"""Tests for document-service FastAPI app."""

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.responses import Response

from reality_rag_contracts import CanonicalMetadata, IndexStatus, PublishStatus
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.outbox_events import OutboxEventRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository


@pytest.fixture
def client():
    from document_service.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "document-service"


def test_upload_creates_source_file_and_outbox(client: TestClient, monkeypatch, tmp_path):
    monkeypatch.setenv("DOCUMENT_STAGING_DIR", str(tmp_path))

    resp = client.post(
        "/upload",
        data={"collection_id": "col_policy", "visibility": "internal"},
        files={"file": ("report.docx", b"hello reality rag", "application/octet-stream")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["duplicate"] is False
    assert data["status"] == "ready"
    assert data["collection_id"] == "col_policy"
    assert data["visibility"] == "INTERNAL"
    assert data["content_hash"].startswith("sha256:")

    session = get_session()
    try:
        source_file = SourceFileRepository(session).get(data["source_file_id"])
        assert source_file is not None
        assert source_file.state.value == "ready"
        assert source_file.upload_id == data["upload_id"]
        assert source_file.object_id == data["object_id"]
        staged_path = Path(tmp_path) / "_tmp" / data["upload_id"] / "report.docx"
        assert staged_path.exists()

        events = OutboxEventRepository(session).list_pending(limit=10)
        file_ready = [evt for evt in events if evt.aggregate_id == data["source_file_id"]]
        assert len(file_ready) == 1
        assert file_ready[0].event_type == "FileReady"
        assert file_ready[0].payload["content_hash"] == data["content_hash"]
    finally:
        session.close()


def test_upload_returns_existing_active_source_file(client: TestClient, monkeypatch, tmp_path):
    monkeypatch.setenv("DOCUMENT_STAGING_DIR", str(tmp_path))

    first = client.post(
        "/upload",
        data={"collection_id": "col_policy"},
        files={"file": ("dup.docx", b"same bytes", "application/octet-stream")},
    )
    assert first.status_code == 200
    first_payload = first.json()

    second = client.post(
        "/upload",
        data={"collection_id": "col_policy"},
        files={"file": ("dup-again.docx", b"same bytes", "application/octet-stream")},
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["duplicate"] is True
    assert second_payload["reason"] == "duplicate_active_source_file"
    assert second_payload["source_file_id"] == first_payload["source_file_id"]
    assert second_payload["object_id"] == first_payload["object_id"]
    assert second_payload["intake_job_id"] is None
    assert second_payload["status"] == "ready"


def test_upload_returns_existing_published_document(client: TestClient, monkeypatch, tmp_path):
    monkeypatch.setenv("DOCUMENT_STAGING_DIR", str(tmp_path))
    content = b"published bytes"
    content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

    session = get_session()
    try:
        DocumentRepository(session).save(
            CanonicalMetadata(
                doc_id="doc-published-1",
                logical_document_id="logical-published-1",
                tenant_id="default",
                collection_id="col_policy",
                source_hash="sha256:published-bytes",
                source_content_hash=content_hash,
                version=1,
                publish_status=PublishStatus.PUBLISHED,
                index_status=IndexStatus.INDEXED,
            )
        )
        session.commit()
    finally:
        session.close()

    resp = client.post(
        "/upload",
        data={"collection_id": "col_policy"},
        files={"file": ("published.docx", content, "application/octet-stream")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["duplicate"] is True
    assert data["reason"] == "duplicate_published_document"
    assert data["existing_doc_id"] == "doc-published-1"
    assert data["source_file_id"] is None
    assert data["intake_job_id"] is None


def test_source_preview_returns_native_text_descriptor(client: TestClient, monkeypatch, tmp_path):
    monkeypatch.setenv("DOCUMENT_STAGING_DIR", str(tmp_path))

    upload = client.post(
        "/upload",
        data={"collection_id": "col_policy"},
        files={"file": ("notes.md", b"# title\nbody", "text/markdown")},
    )
    assert upload.status_code == 200
    source_file_id = upload.json()["source_file_id"]

    preview = client.get(f"/internal/source-files/{source_file_id}/preview")
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["preview_available"] is True
    assert payload["preview_kind"] == "text"
    assert payload["preview_status"] == "ready"
    assert payload["preview_url"] == f"/internal/source-files/{source_file_id}/preview/content"


def test_source_preview_delegates_to_conversion_worker(client: TestClient, monkeypatch, tmp_path):
    monkeypatch.setenv("DOCUMENT_STAGING_DIR", str(tmp_path))

    async def fake_request_generated_preview(**kwargs):
        assert kwargs["filename"] == "slides.pptx"
        assert kwargs["source_file_id"].startswith("src_")
        return {
            "source_file_id": kwargs["source_file_id"],
            "filename": kwargs["filename"],
            "mime_type": kwargs["mime_type"],
            "preview_available": True,
            "preview_status": "ready",
            "preview_kind": "pdf",
            "preview_mime_type": "application/pdf",
            "preview_url": f"/internal/source-previews/{kwargs['source_file_id']}/content",
            "thumbnail_url": None,
            "page_count": 7,
        }

    async def fake_proxy_generated_preview_content(**kwargs):
        assert kwargs["filename"] == "slides.pptx"
        return Response(
            content=b"%PDF-1.4 delegated preview",
            media_type="application/pdf",
            headers={"Cache-Control": "no-store"},
        )

    monkeypatch.setattr("document_service.main._request_generated_preview", fake_request_generated_preview)
    monkeypatch.setattr("document_service.main._proxy_generated_preview_content", fake_proxy_generated_preview_content)

    upload = client.post(
        "/upload",
        data={"collection_id": "col_policy"},
        files={
            "file": (
                "slides.pptx",
                b"pptx-bytes",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert upload.status_code == 200
    source_file_id = upload.json()["source_file_id"]

    preview = client.get(f"/internal/source-files/{source_file_id}/preview")
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["preview_available"] is True
    assert payload["preview_kind"] == "pdf"
    assert payload["preview_status"] == "ready"
    assert payload["page_count"] == 7
    assert payload["preview_url"] == f"/internal/source-files/{source_file_id}/preview/content"

    content = client.get(f"/internal/source-files/{source_file_id}/preview/content")
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("application/pdf")
    assert content.content.startswith(b"%PDF-1.4")
