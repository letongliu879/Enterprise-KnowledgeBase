"""Tests for audit log endpoints."""

import pytest
import respx
from fastapi.testclient import TestClient


class TestAuditLogs:
    @pytest.fixture(autouse=True)
    def _setup_respx(self):
        with respx.mock(base_url="http://localhost:8005") as respx_mock:
            yield respx_mock

    def test_list_audit_logs(self, client: TestClient, admin_token: str, _setup_respx):
        route = _setup_respx.post("/admin/ops/audit-log").respond(
            200,
            json={
                "items": [
                    {
                        "audit_id": "audit-001",
                        "action": "retry",
                        "actor_id": "user-001",
                        "created_at": "2026-06-13T00:00:00Z",
                    }
                ],
                "total": 1,
            },
        )

        resp = client.get(
            "/workbench/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["audit_id"] == "audit-001"
        assert route.called

    def test_export_audit_logs(self, client: TestClient, admin_token: str, _setup_respx):
        resp = client.post(
            "/workbench/audit-logs/export",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"format": "csv"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "download_url" in data

    def test_list_audit_logs_no_auth(self, client: TestClient):
        resp = client.get("/workbench/audit-logs")
        assert resp.status_code == 401
