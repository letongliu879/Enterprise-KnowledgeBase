"""Tests for profile registry routes."""

import pytest
from fastapi.testclient import TestClient
import respx
import httpx


class TestParserProfiles:
    def test_create_parser_profile(self, client: TestClient, admin_token):
        resp = client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-1",
            "name": "Test Parser",
            "parser_id": "naive",
            "parser_config": {"chunk_size": 512},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parser_profile_id"] == "pp-1"
        assert data["state"] == "draft"
        assert data["version"] == 1

    def test_update_draft_parser(self, client: TestClient, admin_token):
        client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-upd",
            "name": "Original",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.patch("/admin/parser-profiles/pp-upd", json={
            "name": "Updated",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    def test_update_published_parser_fails(self, client: TestClient, admin_token):
        client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-pub",
            "name": "Published",
            "parser_id": "naive",
            "parser_config": {},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18082/internal/parser-profiles/validate").respond(200, json={
                "valid": True,
                "canonical_config": {"chunk_token_num": 512},
                "profile_hash": "sha256:abc",
                "warnings": [],
                "errors": [],
                "runtime_owner": "indexing",
                "validator_version": "indexing-v0.1.0",
            })
            client.post("/admin/parser-profiles/pp-pub/publish", headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.patch("/admin/parser-profiles/pp-pub", json={
            "name": "Should Fail",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 409

    def test_publish_parser_with_validation(self, client: TestClient, admin_token):
        client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-pub2",
            "name": "To Publish",
            "parser_id": "naive",
            "parser_config": {"chunk_token_num": 256},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18082/internal/parser-profiles/validate").respond(200, json={
                "valid": True,
                "canonical_config": {"chunk_token_num": 256, "delimiter": "\\n"},
                "profile_hash": "sha256:abc123",
                "warnings": [],
                "errors": [],
                "runtime_owner": "indexing",
                "validator_version": "indexing-v0.1.0",
            })
            resp = client.post("/admin/parser-profiles/pp-pub2/publish", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "published"
        assert data["profile_hash"] == "sha256:abc123"
        assert data["validator_version"] == "indexing-v0.1.0"

    def test_publish_parser_validation_failure(self, client: TestClient, admin_token):
        client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-invalid",
            "name": "Invalid Parser",
            "parser_id": "naive",
            "parser_config": {"chunk_token_num": -1},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18082/internal/parser-profiles/validate").respond(200, json={
                "valid": False,
                "profile_hash": "sha256:000000",
                "warnings": [],
                "errors": [{"code": "INVALID_CHUNK_TOKEN_NUM", "message": "must be positive"}],
                "runtime_owner": "indexing",
                "validator_version": "indexing-v0.1.0",
            })
            resp = client.post("/admin/parser-profiles/pp-invalid/publish", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 409
        assert "INVALID_CHUNK_TOKEN_NUM" in resp.text

    def test_publish_parser_downstream_unavailable(self, client: TestClient, admin_token):
        client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-down",
            "name": "Downstream Unavailable",
            "parser_id": "naive",
            "parser_config": {},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18082/internal/parser-profiles/validate").mock(side_effect=httpx.ConnectError("Connection refused"))
            resp = client.post("/admin/parser-profiles/pp-down/publish", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 409
        assert "DOWNSTREAM_UNAVAILABLE" in resp.text

    def test_publish_creates_new_version(self, client: TestClient, admin_token):
        client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-version",
            "name": "Versioned",
            "parser_id": "naive",
            "parser_config": {},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18082/internal/parser-profiles/validate").respond(200, json={
                "valid": True,
                "canonical_config": {},
                "profile_hash": "sha256:v1",
                "warnings": [],
                "errors": [],
                "runtime_owner": "indexing",
                "validator_version": "indexing-v0.1.0",
            })
            client.post("/admin/parser-profiles/pp-version/publish", headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18082/internal/parser-profiles/validate").respond(200, json={
                "valid": True,
                "canonical_config": {},
                "profile_hash": "sha256:v2",
                "warnings": [],
                "errors": [],
                "runtime_owner": "indexing",
                "validator_version": "indexing-v0.1.0",
            })
            resp = client.post("/admin/parser-profiles/pp-version/publish", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "published"
        assert data["version"] == 2
        assert "pp-version_v2" in data["parser_profile_id"]

    def test_list_parser_profiles(self, client: TestClient, admin_token):
        client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-list",
            "name": "Listable",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/admin/parser-profiles", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_transition_parser_state(self, client: TestClient, admin_token):
        client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-trans",
            "name": "Transition",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.post("/admin/parser-profiles/pp-trans/transition", json={
            "target_state": "retired",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["state"] == "retired"


class TestRetrievalProfiles:
    def test_create_retrieval_profile(self, client: TestClient, admin_token):
        resp = client.post("/admin/retrieval-profiles", json={
            "retrieval_profile_id": "rp-1",
            "name": "Test Retrieval",
            "profile_config": {"bm25_weight": 0.7},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_profile_id"] == "rp-1"
        assert data["state"] == "draft"

    def test_update_draft_retrieval(self, client: TestClient, admin_token):
        client.post("/admin/retrieval-profiles", json={
            "retrieval_profile_id": "rp-upd",
            "name": "Original",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.patch("/admin/retrieval-profiles/rp-upd", json={
            "name": "Updated",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    def test_update_published_retrieval_fails(self, client: TestClient, admin_token):
        client.post("/admin/retrieval-profiles", json={
            "retrieval_profile_id": "rp-pub",
            "name": "Published",
            "profile_config": {"bm25_weight": 0.3, "vector_weight": 0.7, "candidate_top_k": 20,
                               "similarity_threshold": 0.75, "rerank_enabled": True,
                               "rerank_model": "bge-reranker-v2-m3", "fail_policy": "fail_closed",
                               "expansion_policy": {}, "pack_budget": 1200},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18083/internal/retrieval-profiles/validate").respond(200, json={
                "valid": True,
                "canonical_config": {"bm25_weight": 0.3},
                "profile_hash": "sha256:abc",
                "warnings": [],
                "errors": [],
                "runtime_owner": "retrieval",
                "validator_version": "retrieval-v0.1.0",
            })
            respx.post("http://localhost:18083/internal/retrieval-profile-projections/sync").respond(200, json={
                "status": "accepted",
            })
            client.post("/admin/retrieval-profiles/rp-pub/publish", headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.patch("/admin/retrieval-profiles/rp-pub", json={
            "name": "Should Fail",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 409

    def test_publish_retrieval_with_validation(self, client: TestClient, admin_token):
        client.post("/admin/retrieval-profiles", json={
            "retrieval_profile_id": "rp-pub2",
            "name": "To Publish",
            "profile_config": {"bm25_weight": 0.3, "vector_weight": 0.7, "candidate_top_k": 20,
                               "similarity_threshold": 0.75, "rerank_enabled": True,
                               "rerank_model": "bge-reranker-v2-m3", "fail_policy": "fail_closed",
                               "expansion_policy": {}, "pack_budget": 1200},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18083/internal/retrieval-profiles/validate").respond(200, json={
                "valid": True,
                "canonical_config": {"bm25_weight": 0.3, "vector_weight": 0.7},
                "profile_hash": "sha256:ret123",
                "warnings": [],
                "errors": [],
                "runtime_owner": "retrieval",
                "validator_version": "retrieval-v0.1.0",
            })
            respx.post("http://localhost:18083/internal/retrieval-profile-projections/sync").respond(200, json={
                "status": "accepted",
            })
            resp = client.post("/admin/retrieval-profiles/rp-pub2/publish", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "published"
        assert data["profile_hash"] == "sha256:ret123"
        assert data["validator_version"] == "retrieval-v0.1.0"

    def test_publish_retrieval_validation_failure(self, client: TestClient, admin_token):
        client.post("/admin/retrieval-profiles", json={
            "retrieval_profile_id": "rp-invalid",
            "name": "Invalid Retrieval",
            "profile_config": {"bm25_weight": 0.8, "vector_weight": 0.5},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18083/internal/retrieval-profiles/validate").respond(200, json={
                "valid": False,
                "profile_hash": "sha256:000000",
                "warnings": [],
                "errors": [{"code": "BM25_VECTOR_WEIGHT_SUM", "message": "sum must equal 1.0"}],
                "runtime_owner": "retrieval",
                "validator_version": "retrieval-v0.1.0",
            })
            resp = client.post("/admin/retrieval-profiles/rp-invalid/publish", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 409
        assert "BM25_VECTOR_WEIGHT_SUM" in resp.text

    def test_publish_retrieval_downstream_unavailable(self, client: TestClient, admin_token):
        client.post("/admin/retrieval-profiles", json={
            "retrieval_profile_id": "rp-down",
            "name": "Downstream Unavailable",
            "profile_config": {"bm25_weight": 0.3, "vector_weight": 0.7, "candidate_top_k": 20,
                               "similarity_threshold": 0.75, "rerank_enabled": True,
                               "rerank_model": "bge-reranker-v2-m3", "fail_policy": "fail_closed",
                               "expansion_policy": {}, "pack_budget": 1200},
        }, headers={"Authorization": f"Bearer {admin_token}"})
        with respx.mock:
            respx.post("http://localhost:18083/internal/retrieval-profiles/validate").mock(side_effect=httpx.ConnectError("Connection refused"))
            resp = client.post("/admin/retrieval-profiles/rp-down/publish", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 409
        assert "DOWNSTREAM_UNAVAILABLE" in resp.text

    def test_unauthorized_create(self, client: TestClient, viewer_token):
        resp = client.post("/admin/parser-profiles", json={
            "parser_profile_id": "pp-unauth",
            "name": "Unauthorized",
        }, headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 403
