"""Tests for tickets."""

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from conftest import _make_token


class TestTickets:
    def test_list_tickets(self, client: TestClient, reviewer_token: str):
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets").respond(
                200, json=[
                    {
                        "ticket_id": "ticket_123",
                        "collection_id": "col_default",
                        "status": "PENDING",
                        "doc_id": "doc_123",
                        "source_file_id": "sf_123",
                        "created_at": "2026-05-27T10:00:00Z",
                    }
                ]
            )
            resp = client.get(
                "/workbench/tickets",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["items"][0]["ticket_id"] == "ticket_123"

    def test_list_tickets_filters_inaccessible_collections(self, client: TestClient):
        restricted_token = _make_token(
            "user-003",
            "reviewer@example.com",
            ["reviewer"],
            allowed_collections=["col_default"],
        )
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets").respond(
                200, json=[
                    {
                        "ticket_id": "ticket_123",
                        "collection_id": "col_default",
                        "status": "PENDING",
                        "doc_id": "doc_123",
                        "source_file_id": "sf_123",
                        "created_at": "2026-05-27T10:00:00Z",
                    },
                    {
                        "ticket_id": "ticket_999",
                        "collection_id": "col_secret",
                        "status": "PENDING",
                        "doc_id": "doc_999",
                        "source_file_id": "sf_999",
                        "created_at": "2026-05-27T10:00:00Z",
                    },
                ]
            )
            resp = client.get(
                "/workbench/tickets",
                headers={"Authorization": f"Bearer {restricted_token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert [item["ticket_id"] for item in data["items"]] == ["ticket_123"]

    def test_list_tickets_downstream_not_implemented(self, client: TestClient, reviewer_token: str):
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets").respond(404)
            resp = client.get(
                "/workbench/tickets",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert resp.status_code == 501
            assert resp.json()["detail"]["error_code"] == "DOWNSTREAM_NOT_IMPLEMENTED"

    def test_list_tickets_unauthorized(self, client: TestClient):
        resp = client.get("/workbench/tickets")
        assert resp.status_code == 401

    def test_get_ticket(self, client: TestClient, reviewer_token: str):
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "collection_id": "col_default",
                    "status": "PENDING",
                    "doc_id": "doc_123",
                    "source_file_id": "sf_123",
                    "created_at": "2026-05-27T10:00:00Z",
                }
            )
            resp = client.get(
                "/workbench/tickets/ticket_123",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert resp.status_code == 200
            assert resp.json()["ticket_id"] == "ticket_123"

    def test_decide_ticket_requires_reviewer(self, client: TestClient, uploader_token: str):
        resp = client.post(
            "/workbench/tickets/ticket_123/decide",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "decision_request_id": "dec_123",
                "action": "APPROVE",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error_code"] == "FORBIDDEN"

    def test_decide_ticket(self, client: TestClient, reviewer_token: str):
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "collection_id": "col_default",
                    "tenant_id": "tenant_acme",
                    "status": "PENDING",
                }
            )
            decide_route = respx.post("http://localhost:8004/internal/tickets/ticket_123/decide").mock(
                return_value=Response(200, json={"status": "APPROVED", "ticket_id": "ticket_123"})
            )
            resp = client.post(
                "/workbench/tickets/ticket_123/decide",
                headers={"Authorization": f"Bearer {reviewer_token}"},
                json={
                    "decision_request_id": "dec_123",
                    "action": "APPROVE",
                    "actor": "user-003",
                    "tenant_id": "tenant_wrong",
                    "collection_id": "col_wrong",
                },
            )
            assert resp.status_code == 200
            assert resp.json()["decision"] == "APPROVE"
            sent = decide_route.calls[0].request.read().decode("utf-8")
            assert '"tenant_id":"tenant_acme"' in sent
            assert '"collection_id":"col_default"' in sent
            assert '"actor":"user-003"' in sent
