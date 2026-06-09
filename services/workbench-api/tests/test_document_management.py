from datetime import datetime, timezone

import respx
import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from conftest import _make_token
from reality_rag_persistence.models import WorkbenchDocumentProjectionModel
from workbench_api.projections.projector import ProjectionProjector
from workbench_api.workspace.service import WorkspaceService


def _task_event(*, upload_id: str, doc_id: str, source_file_id: str, parse_snapshot_id: str, ticket_id: str) -> dict:
    return {
        "event_id": f"ev_task_{upload_id}",
        "event_type": "TASK_CREATED",
        "tenant_id": "tenant_acme",
        "collection_id": "col_default",
        "aggregate_type": "task",
        "aggregate_id": upload_id,
        "aggregate_version": 30,
        "occurred_at": datetime(2026, 6, 9, 10, 0, 0, tzinfo=timezone.utc),
        "payload": {
            "projection_id": upload_id,
            "tenant_id": "tenant_acme",
            "user_id": "user-001",
            "collection_id": "col_default",
            "upload_id": upload_id,
            "filename": "document.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "size_bytes": 1024,
            "source_file_id": source_file_id,
            "parse_snapshot_id": parse_snapshot_id,
            "ticket_id": ticket_id,
            "doc_id": doc_id,
            "source_file_state": "ready",
            "intake_job_state": "review_running",
            "progress_pct": 75,
        },
        "trace_id": upload_id,
    }


def _ticket_event(*, ticket_id: str, doc_id: str, source_file_id: str, parse_snapshot_id: str) -> dict:
    return {
        "event_id": f"ev_ticket_{ticket_id}",
        "event_type": "TicketCreated",
        "tenant_id": "tenant_acme",
        "collection_id": "col_default",
        "aggregate_type": "ticket",
        "aggregate_id": ticket_id,
        "aggregate_version": 10,
        "occurred_at": datetime(2026, 6, 9, 10, 5, 0, tzinfo=timezone.utc),
        "payload": {
            "ticket_id": ticket_id,
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "doc_id": doc_id,
            "source_file_id": source_file_id,
            "parse_snapshot_id": parse_snapshot_id,
            "filename": "document.docx",
            "state": "pending",
            "agent_finding_count": 1,
            "agent_blocking_finding_count": 1,
        },
        "trace_id": ticket_id,
    }


def _document_event(*, doc_id: str, upload_id: str, source_file_id: str, parse_snapshot_id: str) -> dict:
    return {
        "event_id": f"ev_doc_{doc_id}",
        "event_type": "PublishCompleted",
        "tenant_id": "tenant_acme",
        "collection_id": "col_default",
        "aggregate_type": "document",
        "aggregate_id": doc_id,
        "aggregate_version": 40,
        "occurred_at": datetime(2026, 6, 9, 10, 10, 0, tzinfo=timezone.utc),
        "payload": {
            "doc_id": doc_id,
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "source_file_id": source_file_id,
            "parse_snapshot_id": parse_snapshot_id,
            "published_doc_id": "pub_001",
            "upload_id": upload_id,
            "filename": "document.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "document_state": "ACTIVE",
            "publish_state": "published",
            "active_index_version": "idx_v1",
            "chunk_count": 3,
            "page_count": 5,
        },
        "trace_id": doc_id,
    }


def _agent_review_event(*, ticket_id: str, doc_id: str, source_file_id: str, parse_snapshot_id: str) -> dict:
    return {
        "event_id": f"ev_agent_{ticket_id}",
        "event_type": "AgentReviewCompleted",
        "tenant_id": "tenant_acme",
        "collection_id": "col_default",
        "aggregate_type": "agent_review",
        "aggregate_id": f"finding_{ticket_id}",
        "aggregate_version": 1,
        "occurred_at": datetime(2026, 6, 9, 10, 12, 0, tzinfo=timezone.utc),
        "payload": {
            "finding_id": f"finding_{ticket_id}",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "ticket_id": ticket_id,
            "doc_id": doc_id,
            "source_file_id": source_file_id,
            "parse_snapshot_id": parse_snapshot_id,
            "severity": "high",
            "category": "factual_error",
            "problem_summary": "Mismatch",
            "source_quote": "quoted text",
            "evidence_id": "ev_001",
            "page_from": 1,
            "page_to": 1,
            "state": "open",
            "confidence": 0.8,
        },
        "trace_id": ticket_id,
    }


def _seed_document_workspace(db_session: Session, *, doc_id: str = "doc_001", parse_snapshot_id: str = "ps_001") -> None:
    projector = ProjectionProjector(db_session)
    projector.record_and_apply(
        _task_event(
            upload_id="upload_001",
            doc_id=doc_id,
            source_file_id="sf_001",
            parse_snapshot_id=parse_snapshot_id,
            ticket_id="ticket_001",
        )
    )
    projector.record_and_apply(
        _ticket_event(
            ticket_id="ticket_001",
            doc_id=doc_id,
            source_file_id="sf_001",
            parse_snapshot_id=parse_snapshot_id,
        )
    )
    projector.record_and_apply(
        _document_event(
            doc_id=doc_id,
            upload_id="upload_001",
            source_file_id="sf_001",
            parse_snapshot_id=parse_snapshot_id,
        )
    )
    projector.record_and_apply(
        _agent_review_event(
            ticket_id="ticket_001",
            doc_id=doc_id,
            source_file_id="sf_001",
            parse_snapshot_id=parse_snapshot_id,
        )
    )
    db_session.commit()


def test_get_document_workspace_returns_document_task_and_ticket(
    client: TestClient,
    reviewer_token: str,
    db_session: Session,
):
    _seed_document_workspace(db_session)

    with respx.mock:
        respx.get("http://localhost:8004/internal/tickets/ticket_001").respond(
            200,
            json={
                "ticket_id": "ticket_001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "status": "pending",
                "doc_id": "doc_001",
                "created_at": "2026-06-09T10:00:00Z",
            },
        )
        respx.get("http://localhost:8006/internal/source-files/sf_001").respond(
            200,
            json={
                "source_file_id": "sf_001",
                "upload_id": "upload_001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "original_name": "document.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size_bytes": 1024,
                "state": "ready",
            },
        )
        respx.get("http://localhost:8002/internal/parse-snapshots/ps_001").respond(
            200,
            json={
                "parse_snapshot_id": "ps_001",
                "source_file_id": "sf_001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "source_filename": "document.docx",
                "source_suffix": "docx",
                "parser_id": "docling",
                "parser_backend": "ragflow_app",
                "preview_text": "hello world",
                "warnings": [],
            },
        )
        respx.get("http://localhost:8002/internal/parse-snapshots/ps_001/chunks").respond(
            200,
            json={
                "items": [
                    {
                        "evidence_id": "ev_001",
                        "doc_id": "doc_001",
                        "content": "hello world",
                        "section_path": ["sec1"],
                        "page_spans": [{"page_from": 1, "page_to": 1}],
                    }
                ],
                "total": 1,
            },
        )

        resp = client.get(
            "/workbench/documents/doc_001/workspace",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["doc_id"] == "doc_001"
    assert data["task"]["upload_id"] == "upload_001"
    assert data["task"]["status"] == "reviewing"
    assert data["ticket"]["ticket_id"] == "ticket_001"
    assert data["agent_review"]["source"] == "projection"
    assert data["capabilities"]["can_reindex"] is False


def test_document_workspace_respects_collection_access(client: TestClient, db_session: Session):
    _seed_document_workspace(db_session)
    denied_token = _make_token(
        "user-777",
        "denied@example.com",
        ["reviewer"],
        tenant_id="tenant_acme",
        allowed_collections=["col_other"],
    )

    resp = client.get(
        "/workbench/documents/doc_001/workspace",
        headers={"Authorization": f"Bearer {denied_token}"},
    )

    assert resp.status_code == 403


def test_archive_document_proxies_to_admin(client: TestClient, admin_token: str, db_session: Session):
    _seed_document_workspace(db_session)

    with respx.mock:
        route = respx.post("http://localhost:8005/admin/documents/doc_001/archive").respond(
            200,
            json={
                "success": True,
                "final_doc_id": "doc_001",
                "previous_state": "PUBLISHED",
                "new_state": "ARCHIVED",
            },
        )
        resp = client.post(
            "/workbench/documents/doc_001/archive",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "cleanup"},
        )

    assert resp.status_code == 200
    assert route.called
    assert resp.json()["new_state"] == "ARCHIVED"


def test_archive_document_requires_admin(client: TestClient, uploader_token: str, db_session: Session):
    _seed_document_workspace(db_session)

    resp = client.post(
        "/workbench/documents/doc_001/archive",
        headers={"Authorization": f"Bearer {uploader_token}"},
        json={"reason": "cleanup"},
    )

    assert resp.status_code == 403


def test_reindex_document_requires_parse_snapshot(client: TestClient, admin_token: str, db_session: Session):
    _seed_document_workspace(db_session, doc_id="doc_no_snapshot", parse_snapshot_id="")

    resp = client.post(
        "/workbench/documents/doc_no_snapshot/reindex",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "rebuild"},
    )

    assert resp.status_code == 409


def test_pending_document_lifecycle_actions_are_not_exposed_or_executable(
    client: TestClient,
    admin_token: str,
    db_session: Session,
):
    projector = ProjectionProjector(db_session)
    projector.record_and_apply(
        _document_event(
            doc_id="doc_pending",
            upload_id="upload_pending",
            source_file_id="sf_pending",
            parse_snapshot_id="ps_pending",
        )
    )
    doc_proj = db_session.query(WorkbenchDocumentProjectionModel).filter_by(doc_id="doc_pending").first()
    doc_proj.document_state = "PENDING"
    doc_proj.publish_state = None
    doc_proj.active_index_version = None
    doc_proj.published_doc_id = None
    db_session.commit()

    resp = client.get(
        "/workbench/documents/doc_pending/workspace",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["capabilities"]["can_archive"] is False
    assert data["capabilities"]["can_retract"] is False
    assert data["capabilities"]["can_reindex"] is False

    archive_resp = client.post(
        "/workbench/documents/doc_pending/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "should fail"},
    )
    assert archive_resp.status_code == 409


def test_reindex_document_uses_fresh_idempotency_key_per_request(
    client: TestClient,
    admin_token: str,
    db_session: Session,
):
    _seed_document_workspace(db_session, doc_id="doc_reindex", parse_snapshot_id="ps_reindex")
    seen_keys: list[str] = []

    def _capture(request):
        payload = request.content.decode("utf-8")
        import json

        seen_keys.append(json.loads(payload)["idempotency_key"])
        return Response(
            200,
            json={
                "success": True,
                "final_doc_id": "doc_reindex",
                "previous_state": "PUBLISHED",
                "new_state": "REINDEXING",
                "job_id": "job_123",
            },
        )

    with respx.mock:
        respx.post("http://localhost:8005/admin/documents/doc_reindex/reindex").mock(side_effect=_capture)

        for _ in range(2):
            resp = client.post(
                "/workbench/documents/doc_reindex/reindex",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"reason": "refresh", "index_profile_id": "ragflow"},
            )
            assert resp.status_code == 200

    assert len(seen_keys) == 2
    assert seen_keys[0] != seen_keys[1]


def test_document_list_does_not_call_per_document_workspace_resolvers(
    client: TestClient,
    reviewer_token: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    _seed_document_workspace(db_session)

    def _fail(*args, **kwargs):
        raise AssertionError("per-document resolver should not be used for list endpoint")

    monkeypatch.setattr(WorkspaceService, "_resolve_task_projection_for_document", _fail)
    monkeypatch.setattr(WorkspaceService, "_resolve_ticket_projection_for_document", _fail)

    resp = client.get(
        "/workbench/documents",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_batch_reindex_documents_returns_mixed_results(
    client: TestClient,
    admin_token: str,
    db_session: Session,
):
    _seed_document_workspace(db_session, doc_id="doc_ok", parse_snapshot_id="ps_ok")
    _seed_document_workspace(db_session, doc_id="doc_bad", parse_snapshot_id="")

    with respx.mock:
        respx.post("http://localhost:8005/admin/documents/doc_ok/reindex").respond(
            200,
            json={
                "success": True,
                "final_doc_id": "doc_ok",
                "previous_state": "PUBLISHED",
                "new_state": "REINDEXING",
                "job_id": "job_123",
            },
        )

        resp = client.post(
            "/workbench/documents/batch/reindex",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "doc_ids": ["doc_ok", "doc_bad"],
                "reason": "refresh",
                "index_profile_id": "ragflow",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1
    ok_item = next(item for item in data["items"] if item["doc_id"] == "doc_ok")
    bad_item = next(item for item in data["items"] if item["doc_id"] == "doc_bad")
    assert ok_item["success"] is True
    assert ok_item["new_state"] == "REINDEXING"
    assert bad_item["success"] is False
