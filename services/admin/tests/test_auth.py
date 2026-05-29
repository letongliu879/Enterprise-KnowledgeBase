"""Tests for admin identity/auth routes."""

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from admin_service.config import config


class TestAuth:
    def test_login_success(self, client: TestClient, admin_user):
        resp = client.post("/admin/auth/login", json={
            "email": "admin@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        payload = jwt.decode(data["access_token"], config.jwt_secret, algorithms=[config.jwt_algorithm], options={"verify_aud": False})
        assert payload["tenant_id"] == "tenant_admin"
        assert payload["allowed_collections"] == ["col_default", "col_ops"]

    def test_login_wrong_password(self, client: TestClient, admin_user):
        resp = client.post("/admin/auth/login", json={
            "email": "admin@example.com",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_unknown_user(self, client: TestClient):
        resp = client.post("/admin/auth/login", json={
            "email": "nobody@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 401

    def test_me(self, client: TestClient, admin_token):
        resp = client.get("/admin/auth/me", headers={
            "Authorization": f"Bearer {admin_token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@example.com"
        assert "platform_admin" in data["roles"]

    def test_me_no_auth(self, client: TestClient):
        resp = client.get("/admin/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client: TestClient):
        resp = client.get("/admin/auth/me", headers={
            "Authorization": "Bearer invalid-token",
        })
        assert resp.status_code == 401

    def test_logout(self, client: TestClient, admin_token):
        resp = client.post("/admin/auth/logout", headers={
            "Authorization": f"Bearer {admin_token}",
        })
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out"

    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
