"""Tests for API key registry routes."""

from fastapi.testclient import TestClient


class TestApiKeys:
    def test_create_key(self, client: TestClient, admin_token):
        resp = client.post("/admin/api-keys", json={
            "api_key_id": "key-1",
            "tenant_id": "tenant-1",
            "display_name": "Test Key",
            "token_budget_limit": 8192,
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["entry"]["api_key_id"] == "key-1"
        assert data["entry"]["token_budget_limit"] == 8192
        assert data["entry"]["state"] == "active"
        assert data["plaintext_key"].startswith("rrag_")

    def test_create_key_unauthorized(self, client: TestClient, viewer_token):
        resp = client.post("/admin/api-keys", json={
            "api_key_id": "key-unauth",
            "tenant_id": "tenant-1",
        }, headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 403

    def test_get_key(self, client: TestClient, admin_token):
        client.post("/admin/api-keys", json={
            "api_key_id": "key-get",
            "tenant_id": "tenant-1",
            "display_name": "Get Key",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/api-keys/key-get", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["api_key_id"] == "key-get"
        assert resp.json()["key_hash"] != ""  # Hash stored, not plaintext

    def test_update_key(self, client: TestClient, admin_token):
        client.post("/admin/api-keys", json={
            "api_key_id": "key-upd",
            "tenant_id": "tenant-1",
            "display_name": "Original",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.patch("/admin/api-keys/key-upd", json={
            "display_name": "Updated",
            "token_budget_limit": 2048,
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated"
        assert resp.json()["token_budget_limit"] == 2048

    def test_rotate_key(self, client: TestClient, admin_token):
        create_resp = client.post("/admin/api-keys", json={
            "api_key_id": "key-rot",
            "tenant_id": "tenant-1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        old_hash = create_resp.json()["entry"]["key_hash"]
        resp = client.post("/admin/api-keys/key-rot/rotate", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["plaintext_key"].startswith("rrag_")
        assert data["entry"]["key_hash"] != old_hash
        assert data["entry"]["last_rotated_at"] is not None

    def test_disable_key(self, client: TestClient, admin_token):
        client.post("/admin/api-keys", json={
            "api_key_id": "key-dis",
            "tenant_id": "tenant-1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.post("/admin/api-keys/key-dis/disable", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["state"] == "disabled"

    def test_revoke_key(self, client: TestClient, admin_token):
        client.post("/admin/api-keys", json={
            "api_key_id": "key-rev",
            "tenant_id": "tenant-1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.post("/admin/api-keys/key-rev/revoke", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["state"] == "revoked"

    def test_list_keys(self, client: TestClient, admin_token):
        client.post("/admin/api-keys", json={
            "api_key_id": "key-list",
            "tenant_id": "tenant-1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/api-keys", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_list_keys_by_state(self, client: TestClient, admin_token):
        client.post("/admin/api-keys", json={
            "api_key_id": "key-state",
            "tenant_id": "tenant-1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        client.post("/admin/api-keys/key-state/disable", headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/api-keys?state=disabled", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert any(item["api_key_id"] == "key-state" for item in resp.json()["items"])

    def test_no_plaintext_storage(self, client: TestClient, admin_token):
        client.post("/admin/api-keys", json={
            "api_key_id": "key-no-plain",
            "tenant_id": "tenant-1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/api-keys/key-no-plain", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["key_hash"] != ""
        # Ensure the key_hash is a hex string (SHA-256 = 64 hex chars)
        assert len(data["key_hash"]) == 64
