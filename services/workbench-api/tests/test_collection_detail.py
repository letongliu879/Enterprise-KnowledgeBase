"""Tests for collection detail, edit, and delete proxy endpoints."""

import respx
from fastapi.testclient import TestClient
from jose import jwt

from workbench_api.config import config


def _knowledge_admin_token() -> str:
    payload = {
        "sub": "admin-002",
        "email": "knowledge-admin@example.com",
        "roles": ["knowledge_admin"],
        "tenant_id": "tenant_acme",
        "allowed_collections": ["*"],
    }
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)


class TestCollectionDetail:
    """GET /workbench/collections/{collection_id}"""

    def test_get_collection_detail(self, client: TestClient, uploader_token: str):
        collection_id = "col_default"
        mock_response = {
            "collection_id": collection_id,
            "name": "Default Collection",
            "description": "A test collection",
            "tenant_id": "tenant_acme",
            "lifecycle_state": "active",
        }
        with respx.mock:
            respx.get(f"http://localhost:8005/admin/collections/{collection_id}").respond(
                200, json=mock_response,
            )

            resp = client.get(
                f"/workbench/collections/{collection_id}",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["collection_id"] == collection_id
        assert data["name"] == "Default Collection"

    def test_get_collection_detail_not_found(self, client: TestClient, uploader_token: str):
        collection_id = "nonexistent"
        with respx.mock:
            respx.get(f"http://localhost:8005/admin/collections/{collection_id}").respond(
                404, json={"detail": "Not found"},
            )

            resp = client.get(
                f"/workbench/collections/{collection_id}",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )

        assert resp.status_code == 404


class TestPatchCollection:
    """PATCH /workbench/collections/{collection_id}"""

    def test_patch_collection(self, client: TestClient):
        token = _knowledge_admin_token()
        collection_id = "col_default"
        update = {"name": "Updated Collection", "description": "Updated desc"}
        mock_response = {
            "collection_id": collection_id,
            "name": "Updated Collection",
            "description": "Updated desc",
            "tenant_id": "tenant_acme",
            "lifecycle_state": "active",
        }
        with respx.mock:
            respx.patch(f"http://localhost:8005/admin/collections/{collection_id}").respond(
                200, json=mock_response,
            )

            resp = client.patch(
                f"/workbench/collections/{collection_id}",
                headers={"Authorization": f"Bearer {token}"},
                json=update,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Collection"

    def test_patch_collection_forbidden_for_uploader(self, client: TestClient, uploader_token: str):
        """Only knowledge_admin role should be allowed."""
        collection_id = "col_default"
        resp = client.patch(
            f"/workbench/collections/{collection_id}",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403

    def test_patch_collection_unauthorized(self, client: TestClient):
        collection_id = "col_default"
        resp = client.patch(
            f"/workbench/collections/{collection_id}",
            json={"name": "Hacked"},
        )
        assert resp.status_code == 401


class TestDeleteCollection:
    """DELETE /workbench/collections/{collection_id}"""

    def test_delete_collection(self, client: TestClient):
        token = _knowledge_admin_token()
        collection_id = "col_default"
        with respx.mock:
            respx.delete(f"http://localhost:8005/admin/collections/{collection_id}").respond(
                200, json={"success": True},
            )

            resp = client.delete(
                f"/workbench/collections/{collection_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_delete_collection_forbidden_for_uploader(self, client: TestClient, uploader_token: str):
        collection_id = "col_default"
        resp = client.delete(
            f"/workbench/collections/{collection_id}",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 403

    def test_delete_collection_not_found(self, client: TestClient):
        token = _knowledge_admin_token()
        collection_id = "nonexistent"
        with respx.mock:
            respx.delete(f"http://localhost:8005/admin/collections/{collection_id}").respond(
                404, json={"detail": "Not found"},
            )

            resp = client.delete(
                f"/workbench/collections/{collection_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 404
