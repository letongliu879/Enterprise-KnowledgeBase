"""Tests for workbench auth."""

from fastapi.testclient import TestClient


class TestAuth:
    def test_me_success(self, client: TestClient, uploader_token: str):
        resp = client.get("/workbench/auth/me", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-001"
        assert "uploader" in data["roles"]
        assert data["tenant_id"] == "tenant_acme"
        assert "col_default" in data["allowed_collections"]

    def test_me_no_auth(self, client: TestClient):
        resp = client.get("/workbench/auth/me")
        assert resp.status_code == 401
        assert resp.json()["detail"]["error_code"] == "UNAUTHORIZED"

    def test_me_invalid_token(self, client: TestClient):
        resp = client.get("/workbench/auth/me", headers={"Authorization": "Bearer invalid-token"})
        assert resp.status_code == 401

    def test_health_no_auth(self, client: TestClient):
        resp = client.get("/workbench/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "workbench"
