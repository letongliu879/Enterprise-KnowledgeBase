"""Tests for retrieval and parser profile CRUD endpoints."""

import pytest
import respx
from fastapi.testclient import TestClient


class TestProfilesCrud:
    @pytest.fixture(autouse=True)
    def _setup_respx(self):
        with respx.mock(base_url="http://localhost:8005") as respx_mock:
            yield respx_mock

    def test_create_retrieval_profile(self, client: TestClient, admin_token: str, _setup_respx):
        route = _setup_respx.post("/admin/retrieval-profiles").respond(
            200,
            json={
                "retrieval_profile_id": "rp-001",
                "name": "My Profile",
                "state": "draft",
            },
        )
        resp = client.post(
            "/workbench/retrieval-profiles",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "My Profile", "profile_config": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_profile_id"] == "rp-001"
        assert route.called

    def test_get_retrieval_profile_detail(self, client: TestClient, admin_token: str, _setup_respx):
        route = _setup_respx.get("/admin/retrieval-profiles/rp-001").respond(
            200,
            json={
                "retrieval_profile_id": "rp-001",
                "name": "My Profile",
                "state": "draft",
            },
        )
        resp = client.get(
            "/workbench/retrieval-profiles/rp-001",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["retrieval_profile_id"] == "rp-001"
        assert route.called

    def test_publish_retrieval_profile(self, client: TestClient, admin_token: str, _setup_respx):
        route = _setup_respx.post("/admin/retrieval-profiles/rp-001/publish").respond(
            200,
            json={
                "retrieval_profile_id": "rp-001",
                "state": "published",
            },
        )
        resp = client.post(
            "/workbench/retrieval-profiles/rp-001/publish",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "published"
        assert route.called

    def test_create_parser_profile(self, client: TestClient, admin_token: str, _setup_respx):
        route = _setup_respx.post("/admin/parser-profiles").respond(
            200,
            json={
                "parser_profile_id": "pp-001",
                "name": "My Parser",
                "state": "draft",
            },
        )
        resp = client.post(
            "/workbench/parser-profiles",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "My Parser", "parser_config": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["parser_profile_id"] == "pp-001"
        assert route.called
