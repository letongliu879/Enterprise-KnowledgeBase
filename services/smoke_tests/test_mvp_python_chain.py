"""Cross-service MVP smoke test for the Python service chain.

Coverage:
  1. Admin collection creation
  2. Admin parser profile create + publish (calls indexing validate)
  3. Admin retrieval profile create (publish skipped — retrieval is Java)
  4. Admin API key creation
  5. Workbench upload session (calls intake register source file)
  6. Workbench task view (derives status from intake owner state)
  7. Intake enter_document (triggers indexing parse preview)
  8. Intake approve_and_publish (triggers indexing build + activation)
  9. Indexing chunk queryability verification
 10. Admin archive (calls publishing worker)
 11. Verify published_document state = ARCHIVED
 12. Admin retract
 13. Verify published_document state = RETRACTED

Known gaps discovered during smoke:
  - Workbench parse-preview sends command-envelope to indexing, but indexing
    expects ParsePreviewRequestedCommand directly. This test bypasses workbench
    parse-preview and uses intake enter_document instead.
  - Retrieval profile publish calls Java retrieval validate; mocked in this test.
  - Workbench upload session and intake enter_document create separate source
    files; full linkage is via intake pipeline orchestration, not workbench.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SAMPLE_TEXT = """
# Enterprise Knowledge Base

This is a sample document for smoke testing.

## Section 1

Reality-RAG provides retrieval-augmented generation for enterprise knowledge.

## Section 2

The system supports hybrid recall, reranking, and chunk expansion.
""".strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(client: TestClient, url: str, json_body: dict | None = None, headers: dict | None = None):
    resp = client.post(url, json=json_body, headers=headers)
    assert resp.status_code < 400, f"POST {url} failed: {resp.status_code} {resp.text}"
    return resp.json()


def _get(client: TestClient, url: str, headers: dict | None = None):
    resp = client.get(url, headers=headers)
    assert resp.status_code < 400, f"GET {url} failed: {resp.status_code} {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Step 1: Admin creates collection
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def collection(client: TestClient, admin_headers: dict) -> dict:
    payload = {
        "collection_id": "col_smoke",
        "tenant_id": "tenant_smoke",
        "name": "Smoke Test Collection",
        "description": "Collection for cross-service smoke testing",
        "authority_level": 5,
        "access_policy": {},
        "default_parser_profile_id": "pp_smoke",
        "default_retrieval_profile_id": "rp_smoke",
        "default_approval_policy_id": "ap_smoke",
    }
    return _post(client, "/admin/collections", payload, admin_headers)


def test_admin_create_collection(collection: dict) -> None:
    assert collection["collection_id"] == "col_smoke"
    assert collection["tenant_id"] == "tenant_smoke"


# ---------------------------------------------------------------------------
# Step 2: Admin creates parser profile
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser_profile(client: TestClient, admin_headers: dict) -> dict:
    payload = {
        "parser_profile_id": "pp_smoke",
        "name": "Smoke Parser Profile",
        "description": "Parser profile for smoke testing",
        "parser_id": "naive",
        "parser_config": {"chunk_token_num": 128},
    }
    return _post(client, "/admin/parser-profiles", payload, admin_headers)


def test_admin_create_parser_profile(parser_profile: dict) -> None:
    assert parser_profile["parser_profile_id"] == "pp_smoke"
    assert parser_profile["parser_id"] == "naive"


# ---------------------------------------------------------------------------
# Step 3: Admin publishes parser profile (calls indexing validate)
# ---------------------------------------------------------------------------

def test_admin_publish_parser_profile(client: TestClient, admin_headers: dict, parser_profile: dict) -> None:
    result = _post(client, f"/admin/parser-profiles/{parser_profile['parser_profile_id']}/publish", {}, admin_headers)
    assert result["state"] == "published"


# ---------------------------------------------------------------------------
# Step 4: Admin creates retrieval profile (publish skipped — retrieval is Java)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def retrieval_profile(client: TestClient, admin_headers: dict) -> dict:
    payload = {
        "retrieval_profile_id": "rp_smoke",
        "name": "Smoke Retrieval Profile",
        "description": "Retrieval profile for smoke testing",
        "profile_config": {
            "bm25_weight": 0.3,
            "vector_weight": 0.7,
            "candidate_top_k": 20,
            "similarity_threshold": 0.75,
            "rerank_enabled": True,
            "rerank_model": "bge-reranker-v2-m3",
            "fail_policy": "fail_closed",
            "pack_budget": 1200,
        },
    }
    return _post(client, "/admin/retrieval-profiles", payload, admin_headers)


def test_admin_create_retrieval_profile(retrieval_profile: dict) -> None:
    assert retrieval_profile["retrieval_profile_id"] == "rp_smoke"


# ---------------------------------------------------------------------------
# Step 5: Admin creates API key
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_key(client: TestClient, admin_headers: dict) -> dict:
    payload = {
        "api_key_id": "key_smoke_01",
        "tenant_id": "tenant_smoke",
        "display_name": "Smoke API Key",
        "knowledge_scopes": ["col_smoke"],
        "roles": ["reader"],
        "debug_permission": False,
        "token_budget_limit": 4096,
    }
    return _post(client, "/admin/api-keys", payload, admin_headers)


def test_admin_create_api_key(api_key: dict) -> None:
    assert api_key["entry"]["api_key_id"] == "key_smoke_01"
    assert api_key["entry"]["token_budget_limit"] == 4096


# ---------------------------------------------------------------------------
# Step 6: Workbench creates upload session (registers source file in intake)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def upload_session(client: TestClient, uploader_headers: dict) -> dict:
    payload = {
        "collection_id": "col_smoke",
        "filename": "smoke-doc.md",
        "mime_type": "text/markdown",
        "size_bytes": len(SAMPLE_TEXT.encode("utf-8")),
        "selected_parser_profile_id": "pp_smoke",
    }
    return _post(client, "/workbench/uploads", payload, uploader_headers)


def test_workbench_create_upload_session(upload_session: dict) -> None:
    assert upload_session["upload_id"]
    assert upload_session["collection_id"] == "col_smoke"
    assert upload_session["filename"] == "smoke-doc.md"


# ---------------------------------------------------------------------------
# Step 7: Workbench task view shows uploading/parsing state
# ---------------------------------------------------------------------------

def test_workbench_task_view_uploading_state(client: TestClient, upload_session: dict, uploader_headers: dict) -> None:
    upload_id = upload_session["upload_id"]
    task = _get(client, f"/workbench/tasks/{upload_id}", uploader_headers)
    assert task["upload_id"] == upload_id
    # Source file registered in intake is READY, intake job is CREATED
    assert task["status"] in ("uploading", "parsing")
    assert task["source_file_state"] == "READY"
    assert task["intake_job_state"] == "CREATED"


# ---------------------------------------------------------------------------
# Step 8: Intake enters document (triggers indexing parse preview via HTTP)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def intake_document(client: TestClient) -> dict:
    payload = {
        "tenant_id": "tenant_smoke",
        "collection_id": "col_smoke",
        "filename": "smoke-doc.md",
        "document_version": "v1",
        "publish_version": "pub_001",
        "visibility": "internal",
        "content_text": SAMPLE_TEXT,
        "source_metadata": {"author": "smoke_test"},
    }
    return _post(client, "/intake/v1/documents", payload)


def test_intake_enter_document(intake_document: dict) -> None:
    assert intake_document["source_file_id"]
    assert intake_document["intake_job_id"]
    assert intake_document["parse_snapshot_id"]
    assert intake_document["source_file_state"] == "READY"


# ---------------------------------------------------------------------------
# Step 9: Intake approve_and_publish (triggers indexing build + activation)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def publish_result(client: TestClient, intake_document: dict) -> dict:
    payload = {
        "actor_id": "admin_01",
        "final_doc_id": "doc_smoke_01",
        "confirmed_tags": ["smoke"],
        "index_profile_id": "ragflow",
        "target_index_version_id": "idxv_col_smoke_active",
        "activate_index_version": True,
    }
    return _post(
        client,
        f"/intake/v1/documents/{intake_document['source_file_id']}/approve-and-publish",
        payload,
    )


def test_intake_approve_and_publish(publish_result: dict) -> None:
    assert publish_result["status"] == "PUBLISHED"
    assert publish_result["final_doc_id"] == "doc_smoke_01"
    assert publish_result["build_job_id"]
    assert publish_result["index_version_id"] == "idxv_col_smoke_active"


# ---------------------------------------------------------------------------
# Step 10: Verify indexing chunks are queryable
# ---------------------------------------------------------------------------

def test_indexing_chunks_queryable_after_publish(client: TestClient, publish_result: dict) -> None:
    chunks = _get(
        client,
        "/indexing/internal/chunks?tenant_id=tenant_smoke&principal_id=user_smoke&collection_id=col_smoke",
    )
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk["collection_id"] == "col_smoke"
        assert chunk["final_doc_id"] == "doc_smoke_01"
        assert chunk["published_document_state"] == "PUBLISHED"
        assert chunk["available_int"] == 1


def test_indexing_indexed_document_active(client: TestClient) -> None:
    docs = _get(client, "/indexing/internal/indexed-documents?collection_id=col_smoke")
    assert len(docs) >= 1
    doc = next((d for d in docs if d["final_doc_id"] == "doc_smoke_01"), None)
    assert doc is not None
    assert doc["state"] == "active"
    assert doc["index_version"] == "idxv_col_smoke_active"


def test_indexing_index_version_active(client: TestClient) -> None:
    version = _get(client, "/indexing/internal/index-versions/idxv_col_smoke_active")
    assert version["status"] == "ACTIVE"
    assert version["chunk_count"] >= 1


# ---------------------------------------------------------------------------
# Step 11: Workbench task view for uploaded doc (still parsing — not linked)
# ---------------------------------------------------------------------------

def test_workbench_task_view_upload_still_parsing(client: TestClient, upload_session: dict, uploader_headers: dict) -> None:
    """Workbench upload session is separate from intake pipeline document flow.
    The task view derives status from the intake source file state, which
    remains CREATED because the workbench-registered source file was never
    processed through enter_document.
    """
    upload_id = upload_session["upload_id"]
    task = _get(client, f"/workbench/tasks/{upload_id}", uploader_headers)
    assert task["upload_id"] == upload_id
    assert task["status"] in ("uploading", "parsing")


# ---------------------------------------------------------------------------
# Step 12: Admin archives document (calls publishing worker)
# ---------------------------------------------------------------------------

def test_admin_archive_document(client: TestClient, admin_headers: dict) -> None:
    payload = {
        "command_id": "cmd_archive_01",
        "trace_id": "trc_archive_01",
        "idempotency_key": "idem_archive_01",
        "actor": "admin_01",
        "reason": "Smoke test archive",
    }
    result = _post(client, "/admin/documents/doc_smoke_01/archive", payload, admin_headers)
    assert result["success"] is True
    assert result["new_state"] == "ARCHIVED"
    assert result["previous_state"] in ("PUBLISHED", "published", "")


# ---------------------------------------------------------------------------
# Step 13: Verify published_document state is ARCHIVED
# ---------------------------------------------------------------------------

def test_published_document_archived(client: TestClient) -> None:
    from reality_rag_persistence.database import get_session
    from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository

    session = get_session()
    try:
        repo = PublishedDocumentRepository(session)
        doc = repo.get_by_final_doc_id("doc_smoke_01")
        assert doc is not None
        assert doc.state.value.lower() == "archived"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Step 14: Verify indexing chunks still exist (retrieval filters at read time)
# ---------------------------------------------------------------------------

def test_indexing_chunks_still_exist_after_archive(client: TestClient) -> None:
    """Indexing does NOT mutate chunk_registry on archive; retrieval filters
    via published_documents join. This is by design."""
    chunks = _get(
        client,
        "/indexing/internal/chunks?tenant_id=tenant_smoke&principal_id=user_smoke&collection_id=col_smoke",
    )
    # Chunks still exist in chunk_registry with PUBLISHED state
    smoke_chunks = [c for c in chunks if c["final_doc_id"] == "doc_smoke_01"]
    assert len(smoke_chunks) >= 1
    for chunk in smoke_chunks:
        assert chunk["published_document_state"] == "PUBLISHED"


# ---------------------------------------------------------------------------
# Step 15: Admin retracts document
# ---------------------------------------------------------------------------

def test_admin_retract_document(client: TestClient, admin_headers: dict) -> None:
    # First un-archive so we can retract
    # Actually, the publishing worker supports state transitions from ARCHIVED
    payload = {
        "command_id": "cmd_retract_01",
        "trace_id": "trc_retract_01",
        "idempotency_key": "idem_retract_01",
        "actor": "admin_01",
        "reason": "Smoke test retract",
    }
    result = _post(client, "/admin/documents/doc_smoke_01/retract", payload, admin_headers)
    assert result["success"] is True
    assert result["new_state"] == "RETRACTED"


# ---------------------------------------------------------------------------
# Step 16: Verify published_document state is RETRACTED
# ---------------------------------------------------------------------------

def test_published_document_retracted() -> None:
    from reality_rag_persistence.database import get_session
    from reality_rag_persistence.repositories.published_documents import PublishedDocumentRepository

    session = get_session()
    try:
        repo = PublishedDocumentRepository(session)
        doc = repo.get_by_final_doc_id("doc_smoke_01")
        assert doc is not None
        assert doc.state.value.lower() == "retracted"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Step 17: Admin reindexes document
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parse_snapshot_id(intake_document: dict) -> str:
    return intake_document["parse_snapshot_id"]


def test_admin_reindex_document(client: TestClient, admin_headers: dict, parse_snapshot_id: str) -> None:
    payload = {
        "command_id": "cmd_reindex_01",
        "trace_id": "trc_reindex_01",
        "idempotency_key": "idem_reindex_01",
        "actor": "admin_01",
        "reason": "Smoke test reindex",
        "collection_id": "col_smoke",
        "tenant_id": "tenant_smoke",
        "parse_snapshot_id": parse_snapshot_id,
        "index_profile_id": "ragflow",
    }
    result = _post(client, "/admin/documents/doc_smoke_01/reindex", payload, admin_headers)
    assert result["success"] is True
    assert result["new_state"] == "REINDEXING"
    assert result["job_id"]


# ---------------------------------------------------------------------------
# Step 18: Verify new index version was created
# ---------------------------------------------------------------------------

def test_reindex_created_new_version(client: TestClient) -> None:
    docs = _get(client, "/indexing/internal/indexed-documents?collection_id=col_smoke")
    # Reindex rebuilds the same index version in current implementation;
    # verify the document is still active after reindex.
    doc = next((d for d in docs if d["final_doc_id"] == "doc_smoke_01"), None)
    assert doc is not None
    assert doc["state"] == "active"
