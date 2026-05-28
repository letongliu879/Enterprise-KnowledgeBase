"""Tests for collection catalog routes."""

from fastapi.testclient import TestClient


class TestCollections:
    def test_create_collection(self, client: TestClient, admin_token):
        resp = client.post("/admin/collections", json={
            "collection_id": "coll-1",
            "tenant_id": "tenant-1",
            "name": "Test Collection",
            "description": "A test collection",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["collection_id"] == "coll-1"
        assert data["name"] == "Test Collection"
        assert data["lifecycle_state"] == "active"

    def test_create_collection_unauthorized(self, client: TestClient, viewer_token):
        resp = client.post("/admin/collections", json={
            "collection_id": "coll-1",
            "tenant_id": "tenant-1",
            "name": "Test Collection",
        }, headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 403

    def test_get_collection(self, client: TestClient, admin_token):
        client.post("/admin/collections", json={
            "collection_id": "coll-get",
            "tenant_id": "tenant-1",
            "name": "Get Collection",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/collections/coll-get", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["collection_id"] == "coll-get"

    def test_get_collection_not_found(self, client: TestClient, admin_token):
        resp = client.get("/admin/collections/no-such-coll", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404

    def test_list_collections(self, client: TestClient, admin_token):
        client.post("/admin/collections", json={
            "collection_id": "coll-a",
            "tenant_id": "tenant-1",
            "name": "Collection A",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        client.post("/admin/collections", json={
            "collection_id": "coll-b",
            "tenant_id": "tenant-2",
            "name": "Collection B",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/collections", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

    def test_list_collections_by_tenant(self, client: TestClient, admin_token):
        client.post("/admin/collections", json={
            "collection_id": "coll-t1",
            "tenant_id": "tenant-filter",
            "name": "Collection T1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/collections?tenant_id=tenant-filter", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_update_collection(self, client: TestClient, admin_token):
        client.post("/admin/collections", json={
            "collection_id": "coll-upd",
            "tenant_id": "tenant-1",
            "name": "Original",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.patch("/admin/collections/coll-upd", json={
            "name": "Updated",
            "description": "Updated desc",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["description"] == "Updated desc"

    def test_lifecycle_transition(self, client: TestClient, admin_token):
        client.post("/admin/collections", json={
            "collection_id": "coll-lifecycle",
            "tenant_id": "tenant-1",
            "name": "Lifecycle Collection",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.post("/admin/collections/coll-lifecycle/lifecycle", json={
            "target_state": "archived",
            "reason": "Test archive",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["lifecycle_state"] == "archived"

    def test_binding_versioning(self, client: TestClient, admin_token):
        client.post("/admin/collections", json={
            "collection_id": "coll-bind",
            "tenant_id": "tenant-1",
            "name": "Binding Collection",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp1 = client.post("/admin/collections/coll-bind/bindings", json={
            "parser_profile_id": "parser-1",
            "retrieval_profile_id": "retrieval-1",
            "approval_policy_id": "policy-1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp1.status_code == 200
        binding1 = resp1.json()["binding"]
        assert binding1["binding_version"] == 1
        assert binding1["config_hash"] != ""

        resp2 = client.post("/admin/collections/coll-bind/bindings", json={
            "parser_profile_id": "parser-2",
            "retrieval_profile_id": "retrieval-1",
            "approval_policy_id": "policy-1",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp2.status_code == 200
        resp2_data = resp2.json()
        binding2 = resp2_data["binding"]
        assert binding2["binding_version"] == 2
        assert resp2_data["previous_binding_id"] == binding1["binding_id"]
        assert binding2["config_hash"] != binding1["config_hash"]

    def test_get_current_binding(self, client: TestClient, admin_token):
        client.post("/admin/collections", json={
            "collection_id": "coll-current",
            "tenant_id": "tenant-1",
            "name": "Current Binding",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        client.post("/admin/collections/coll-current/bindings", json={
            "parser_profile_id": "parser-x",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/collections/coll-current/bindings/current", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["parser_profile_id"] == "parser-x"
