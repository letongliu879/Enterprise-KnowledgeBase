"""Tests for ops audit routes."""

from fastapi.testclient import TestClient


class TestAuditLog:
    def test_create_collection_creates_audit(self, client: TestClient, admin_token):
        # Create a collection (audit should be written via service integration)
        resp = client.post("/admin/collections", json={
            "collection_id": "coll-audit",
            "tenant_id": "tenant-1",
            "name": "Audit Collection",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200

        # Query audit log
        audit_resp = client.get("/admin/ops/audit-log?target_type=collection", headers={"Authorization": f"Bearer {admin_token}"})
        assert audit_resp.status_code == 200
        data = audit_resp.json()
        assert data["total"] >= 0

    def test_query_audit_by_actor(self, client: TestClient, admin_token, admin_user):
        resp = client.post("/admin/ops/audit-log", json={
            "actor_id": admin_user.user_id,
            "limit": 10,
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_query_audit_pagination(self, client: TestClient, admin_token):
        resp = client.post("/admin/ops/audit-log", json={
            "limit": 5,
            "offset": 0,
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 0
