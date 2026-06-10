from datetime import datetime, timezone
from unittest.mock import MagicMock

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from reality_rag_persistence.models import WorkbenchChunkEditModel
from workbench_api.projections.projector import ProjectionProjector
from workbench_api.workspace.routes import (
    _approval_client,
    _indexing_client,
    _intake_client,
    close_workspace_clients,
    init_workspace_clients,
)


def _ticket_event(
    *,
    ticket_id: str,
    tenant_id: str = "tenant_acme",
    collection_id: str = "col_default",
    doc_id: str = "doc_123",
    source_file_id: str | None = None,
    parse_snapshot_id: str | None = None,
    filename: str | None = None,
) -> dict:
    return {
        "event_id": f"ev_ticket_{ticket_id}",
        "event_type": "TicketCreated",
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "aggregate_type": "ticket",
        "aggregate_id": ticket_id,
        "aggregate_version": 1,
        "occurred_at": datetime(2026, 6, 9, 10, 0, 0, tzinfo=timezone.utc),
        "payload": {
            "ticket_id": ticket_id,
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "doc_id": doc_id,
            "source_file_id": source_file_id,
            "parse_snapshot_id": parse_snapshot_id,
            "filename": filename,
            "state": "pending",
            "agent_finding_count": 1,
            "agent_blocking_finding_count": 1,
        },
        "trace_id": "test",
    }


def _document_event(
    *,
    doc_id: str,
    tenant_id: str = "tenant_acme",
    collection_id: str = "col_default",
    source_file_id: str | None = None,
    parse_snapshot_id: str | None = None,
    filename: str | None = None,
) -> dict:
    return {
        "event_id": f"ev_doc_{doc_id}",
        "event_type": "DocumentLinked",
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "aggregate_type": "document",
        "aggregate_id": doc_id,
        "aggregate_version": 10,
        "occurred_at": datetime(2026, 6, 9, 10, 5, 0, tzinfo=timezone.utc),
        "payload": {
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "source_file_id": source_file_id,
            "parse_snapshot_id": parse_snapshot_id,
            "filename": filename,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "document_state": "ACTIVE",
            "publish_state": "published",
            "chunk_count": 2,
            "page_count": 8,
        },
        "trace_id": "test",
    }


def _agent_review_event(
    *,
    ticket_id: str,
    finding_id: str = "finding_001",
    tenant_id: str = "tenant_acme",
    collection_id: str = "col_default",
    doc_id: str = "doc_123",
    source_file_id: str | None = None,
    parse_snapshot_id: str | None = None,
) -> dict:
    return {
        "event_id": f"ev_agent_{finding_id}",
        "event_type": "AgentReviewCompleted",
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "aggregate_type": "agent_review",
        "aggregate_id": finding_id,
        "aggregate_version": 1,
        "occurred_at": datetime(2026, 6, 9, 10, 10, 0, tzinfo=timezone.utc),
        "payload": {
            "finding_id": finding_id,
            "tenant_id": tenant_id,
            "collection_id": collection_id,
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
            "confidence": 0.9,
        },
        "trace_id": "test",
    }


def test_workspace_prefers_document_projection_linkage(
    client: TestClient,
    reviewer_token: str,
    db_session: Session,
):
    projector = ProjectionProjector(db_session)
    projector.record_and_apply(
        _ticket_event(
            ticket_id="ticket_123",
            doc_id="doc_123",
            source_file_id="sf_ticket",
            parse_snapshot_id="ps_ticket",
            filename="ticket-version.docx",
        )
    )
    projector.record_and_apply(
        _document_event(
            doc_id="doc_123",
            source_file_id="sf_document",
            parse_snapshot_id="ps_document",
            filename="document-version.docx",
        )
    )
    projector.record_and_apply(
        _agent_review_event(
            ticket_id="ticket_123",
            doc_id="doc_123",
            source_file_id="sf_document",
            parse_snapshot_id="ps_document",
        )
    )
    db_session.add(
        WorkbenchChunkEditModel(
            chunk_edit_id="ce_001",
            tenant_id="tenant_acme",
            collection_id="col_default",
            source_file_id="sf_document",
            parse_snapshot_id="ps_document",
            base_evidence_id="ev_001",
            edit_scope="pre_publish",
            operation="update",
            content="updated",
            edited_by="user-003",
            status="draft",
        )
    )
    db_session.commit()

    with respx.mock:
        respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
            200,
            json={
                "ticket_id": "ticket_123",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "status": "pending",
                "doc_id": "doc_123",
                "decision": None,
                "created_at": "2026-06-09T10:00:00Z",
            },
        )
        respx.get("http://localhost:8006/internal/source-files/sf_document").respond(
            200,
            json={
                "source_file_id": "sf_document",
                "upload_id": "upload_123",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "original_name": "document-version.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size_bytes": 1024,
                "state": "ready",
            },
        )
        respx.get("http://localhost:8002/internal/parse-snapshots/ps_document").respond(
            200,
            json={
                "parse_snapshot_id": "ps_document",
                "source_file_id": "sf_document",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "source_filename": "document-version.docx",
                "source_suffix": "docx",
                "parser_id": "docling",
                "parser_backend": "ragflow_app",
                "preview_text": "hello world",
                "warnings": [],
            },
        )
        respx.get("http://localhost:8002/internal/parse-snapshots/ps_document/chunks").respond(
            200,
            json={
                "items": [
                    {
                        "evidence_id": "ev_001",
                        "doc_id": "doc_123",
                        "content": "hello world",
                        "section_path": ["sec1"],
                        "page_spans": [{"page_from": 1, "page_to": 1}],
                    }
                ],
                "total": 1,
            },
        )

        resp = client.get(
            "/workbench/tickets/ticket_123/workspace",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["linkage_source"] == "document_projection"
    assert data["document"]["source_file_id"] == "sf_document"
    assert data["document"]["parse_snapshot_id"] == "ps_document"
    assert data["source_file"]["source_file_id"] == "sf_document"
    assert data["parse_snapshot"]["parse_snapshot_id"] == "ps_document"
    assert data["chunks"]["total"] == 1
    assert data["chunk_edits"]["total"] == 1
    assert data["agent_review"]["source"] == "projection"
    assert data["capabilities"]["can_view_parsed_text"] is True
    assert data["capabilities"]["can_search_in_document"] is True


def test_workspace_degrades_to_ticket_projection_when_document_projection_missing(
    client: TestClient,
    reviewer_token: str,
    db_session: Session,
):
    projector = ProjectionProjector(db_session)
    projector.record_and_apply(
        _ticket_event(
            ticket_id="ticket_missing_doc",
            doc_id="doc_missing",
            source_file_id="sf_ticket_only",
            parse_snapshot_id="ps_ticket_only",
            filename="ticket-only.docx",
        )
    )
    db_session.commit()

    with respx.mock:
        respx.get("http://localhost:8004/internal/tickets/ticket_missing_doc").respond(
            200,
            json={
                "ticket_id": "ticket_missing_doc",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "status": "pending",
                "doc_id": "doc_missing",
                "created_at": "2026-06-09T10:00:00Z",
            },
        )
        respx.get("http://localhost:8006/internal/source-files/sf_ticket_only").respond(
            200,
            json={
                "source_file_id": "sf_ticket_only",
                "upload_id": "upload_ticket_only",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "original_name": "ticket-only.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size_bytes": 256,
                "state": "ready",
            },
        )
        respx.get("http://localhost:8002/internal/parse-snapshots/ps_ticket_only").respond(
            200,
            json={
                "parse_snapshot_id": "ps_ticket_only",
                "source_file_id": "sf_ticket_only",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "source_filename": "ticket-only.docx",
                "source_suffix": "docx",
                "parser_id": "docling",
                "parser_backend": "ragflow_app",
                "preview_text": "",
                "warnings": [],
            },
        )
        respx.get("http://localhost:8002/internal/parse-snapshots/ps_ticket_only/chunks").respond(
            200,
            json={"items": [], "total": 0},
        )
        respx.get("http://localhost:8004/internal/tickets/ticket_missing_doc/agent-review").respond(
            200,
            json={
                "ticket_id": "ticket_missing_doc",
                "decision": "REVIEW",
                "source_file_id": "sf_ticket_only",
                "parse_snapshot_id": "ps_ticket_only",
                "findings": [],
                "matched_count": 0,
                "unmatched_count": 0,
            },
        )

        resp = client.get(
            "/workbench/tickets/ticket_missing_doc/workspace",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["linkage_source"] == "ticket_projection"
    assert "document_projection" in data["degraded_parts"]
    assert data["agent_review"]["source"] == "approval"


def test_workspace_clients_reused_across_requests(client: TestClient, reviewer_token: str, monkeypatch):
    """Workspace routes should reuse the same httpx.AsyncClient instances across requests."""
    # Force fresh module-level clients so we can spy on construction.
    init_workspace_clients()

    created_clients: list[httpx.AsyncClient] = []
    original_init = httpx.AsyncClient.__init__

    def tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        created_clients.append(self)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", tracking_init)

    with respx.mock:
        respx.get("http://localhost:8004/internal/tickets/reused_1").respond(
            200,
            json={
                "ticket_id": "reused_1",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "status": "pending",
                "doc_id": "doc_reused",
                "created_at": "2026-06-09T10:00:00Z",
            },
        )
        respx.get("http://localhost:8004/internal/tickets/reused_2").respond(
            200,
            json={
                "ticket_id": "reused_2",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "status": "pending",
                "doc_id": "doc_reused",
                "created_at": "2026-06-09T10:00:00Z",
            },
        )
        respx.get("http://localhost:8006/internal/source-files/sf_reused").respond(
            200,
            json={
                "source_file_id": "sf_reused",
                "upload_id": "upload_reused",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "original_name": "reused.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size_bytes": 256,
                "state": "ready",
            },
        )
        respx.get("http://localhost:8002/internal/parse-snapshots/ps_reused").respond(
            200,
            json={
                "parse_snapshot_id": "ps_reused",
                "source_file_id": "sf_reused",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "source_filename": "reused.docx",
                "source_suffix": "docx",
                "parser_id": "docling",
                "parser_backend": "ragflow_app",
                "preview_text": "",
                "warnings": [],
            },
        )
        respx.get("http://localhost:8002/internal/parse-snapshots/ps_reused/chunks").respond(
            200,
            json={"items": [], "total": 0},
        )

        client.get(
            "/workbench/tickets/reused_1/workspace",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        client.get(
            "/workbench/tickets/reused_2/workspace",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )

    # Only one AsyncClient should have been created for each service during lifespan init.
    assert len(created_clients) <= 3


def test_workspace_clients_closed_on_lifespan_shutdown(monkeypatch):
    """Lifespan shutdown must close the shared downstream clients."""
    init_workspace_clients()

    closed_clients: list[str] = []

    async def fake_close(self):
        closed_clients.append(self.__class__.__name__)

    monkeypatch.setattr("workbench_api.downstream_clients.clients.BaseHttpClient.close", fake_close)

    from workbench_api.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()):
        pass

    assert "IntakeClient" in closed_clients
    assert "ApprovalClient" in closed_clients
    assert "IndexingClient" in closed_clients
