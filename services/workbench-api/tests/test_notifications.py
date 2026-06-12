"""Tests for notification endpoints."""

from fastapi.testclient import TestClient


class TestNotifications:
    def test_list_notifications_empty(self, client: TestClient, uploader_token: str):
        resp = client.get(
            "/workbench/notifications",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["unread_count"] == 0

    def test_mark_read(self, client: TestClient, uploader_token: str):
        resp = client.patch(
            "/workbench/notifications/non-existent/read",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 404

    def test_read_all(self, client: TestClient, uploader_token: str):
        resp = client.post(
            "/workbench/notifications/read-all",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_unread_count(self, client: TestClient, uploader_token: str):
        resp = client.get(
            "/workbench/notifications/unread-count",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_list_notifications_no_auth(self, client: TestClient):
        resp = client.get("/workbench/notifications")
        assert resp.status_code == 401
