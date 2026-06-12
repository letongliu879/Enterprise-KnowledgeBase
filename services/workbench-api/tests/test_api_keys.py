"""Tests for API key proxy endpoints."""

import pytest
import respx
from fastapi.testclient import TestClient


class TestApiKeys:
    @pytest.fixture(autouse=True)
    def _setup_respx(self):
        with respx.mock(base_url="http://localhost:8005") as respx_mock:
            yield respx_mock

    def test_list_api_keys(self, client: TestClient, admin_token: str, _setup_respx):
        route = _setup_respx.get("/admin/api-keys").respond(
            200,
            json={
                "items": [
                    {
                        "api_key_id": "key-001",
                        "display_name": "My Key",
                        "state": "active",
                    }
                ],
                "total": 1,
            },
        )

        resp = client.get(
            "/workbench/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["api_key_id"] == "key-001"
        assert route.called

    def test_create_api_key(self, client: TestClient, admin_token: str, _setup_respx):
        route = _setup_respx.post("/admin/api-keys").respond(
            200,
            json={
                "api_key_id": "key-002",
                "full_key": "sk-abc123",
                "display_name": "New Key",
            },
        )

        resp = client.post(
            "/workbench/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"display_name": "New Key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_key"] == "sk-abc123"
        assert route.called

    def test_get_api_key_detail(self, client: TestClient, admin_token: str, _setup_respx):
        route = _setup_respx.get("/admin/api-keys/key-001").respond(
            200,
            json={
                "api_key_id": "key-001",
                "display_name": "My Key",
                "state": "active",
            },
        )

        resp = client.get(
            "/workbench/api-keys/key-001",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["api_key_id"] == "key-001"
        assert route.called

    def test_list_api_keys_no_auth(self, client: TestClient):
        resp = client.get("/workbench/api-keys")
        assert resp.status_code == 401
