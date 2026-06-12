"""In-process smoke tests for workbench-api endpoints.

Tests exercise every route category at least once. No external dependencies.
Uses combined FastAPI app from conftest.py.
Does NOT use respx — in-process routes handle everything through ASGITransport.
"""

import pytest
from fastapi.testclient import TestClient


class TestAuthSmoke:
    """Auth endpoints basic response."""

    def test_auth_me_unauthorized(self, client: TestClient):
        """GET /workbench/auth/me without token returns 401"""
        resp = client.get("/workbench/auth/me")
        assert resp.status_code == 401

    def test_auth_me_with_token(self, client: TestClient, admin_headers: dict):
        """GET /workbench/auth/me returns user info"""
        resp = client.get("/workbench/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert "email" in data
        assert "roles" in data
        assert "tenant_id" in data
        assert "allowed_collections" in data
        assert "display_name" in data

    def test_health(self, client: TestClient):
        """GET /workbench/health"""
        resp = client.get("/workbench/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_all(self, client: TestClient, admin_headers: dict):
        """GET /workbench/health/all"""
        resp = client.get("/workbench/health/all", headers=admin_headers)
        assert resp.status_code in (200, 503)


class TestUploadTaskSmoke:
    """Upload and task endpoints."""

    def test_list_uploads(self, client: TestClient, uploader_headers: dict):
        resp = client.get("/workbench/uploads", headers=uploader_headers)
        assert resp.status_code in (200, 501)

    def test_list_tasks(self, client: TestClient, uploader_headers: dict):
        resp = client.get("/workbench/tasks", headers=uploader_headers)
        assert resp.status_code in (200, 501)


class TestTicketSmoke:
    """Ticket endpoints."""

    def test_list_tickets(self, client: TestClient, reviewer_headers: dict):
        resp = client.get("/workbench/tickets", headers=reviewer_headers)
        assert resp.status_code in (200, 501)

    def test_ticket_comments_empty(self, client: TestClient, reviewer_headers: dict):
        """Existing comment endpoint returns empty for nonexistent ticket."""
        resp = client.get(
            "/workbench/tickets/nonexistent/comments",
            headers=reviewer_headers,
        )
        assert resp.status_code in (200, 404, 501)

    def test_notifications(self, client: TestClient, uploader_headers: dict):
        resp = client.get("/workbench/notifications", headers=uploader_headers)
        assert resp.status_code in (200, 501)

    def test_notifications_unread_count(self, client: TestClient, uploader_headers: dict):
        resp = client.get("/workbench/notifications/unread-count", headers=uploader_headers)
        assert resp.status_code in (200, 501)
        if resp.status_code == 200:
            assert "count" in resp.json()

    def test_read_all_notifications(self, client: TestClient, uploader_headers: dict):
        resp = client.post("/workbench/notifications/read-all", headers=uploader_headers)
        assert resp.status_code in (200, 501)
        if resp.status_code == 200:
            assert "count" in resp.json()


class TestDocumentSmoke:
    """Document endpoints."""

    def test_list_documents(self, client: TestClient, uploader_headers: dict):
        resp = client.get("/workbench/documents", headers=uploader_headers)
        assert resp.status_code in (200, 501)

    def test_trash_list(self, client: TestClient, uploader_headers: dict):
        resp = client.get("/workbench/trash", headers=uploader_headers)
        assert resp.status_code in (200, 501)


class TestDashboardSmoke:
    """Dashboard endpoint."""

    def test_dashboard(self, client: TestClient, uploader_headers: dict):
        resp = client.get("/workbench/dashboard", headers=uploader_headers)
        assert resp.status_code in (200, 501)
        if resp.status_code == 200:
            data = resp.json()
            assert "stats" in data
            assert "recent_tickets" in data


class TestCollectionSmoke:
    """Collection endpoints (accept 501 when admin downstream not available)."""

    def test_list_collections(self, client: TestClient, admin_headers: dict):
        resp = client.get("/workbench/collections", headers=admin_headers)
        assert resp.status_code in (200, 501)

    def test_get_collection(self, client: TestClient, admin_headers: dict):
        resp = client.get("/workbench/collections/col_smoke", headers=admin_headers)
        assert resp.status_code in (200, 404, 501)


class TestAdminProxySmoke:
    """Admin proxy endpoints (accept 501 when admin downstream not available)."""

    def test_audit_logs(self, client: TestClient, admin_headers: dict):
        resp = client.get("/workbench/audit-logs", headers=admin_headers)
        assert resp.status_code in (200, 501)

    def test_api_keys_list(self, client: TestClient, admin_headers: dict):
        resp = client.get("/workbench/api-keys", headers=admin_headers)
        assert resp.status_code in (200, 501)

    def test_retrieval_profiles_list(self, client: TestClient, admin_headers: dict):
        resp = client.get("/workbench/retrieval-profiles", headers=admin_headers)
        assert resp.status_code in (200, 501)
