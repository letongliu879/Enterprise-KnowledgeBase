from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_parse_preview_rejects_empty_binary(tmp_path):
    from indexing_service.main import app

    empty_file = tmp_path / "empty.docx"
    empty_file.write_bytes(b"")

    client = TestClient(app)
    response = client.post(
        "/internal/parse-previews",
        json={
            "request_id": "req_empty_preview",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "source_file_id": "src_empty_preview",
            "source_binary_ref": str(empty_file),
            "filename": empty_file.name,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "trace_id": "trc_empty_preview",
        },
    )

    assert response.status_code == 422
    assert "source binary is empty" in response.json()["detail"]
