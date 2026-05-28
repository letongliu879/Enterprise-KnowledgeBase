"""Tests for parser profile selection."""

import pytest
from fastapi.testclient import TestClient


class TestParserProfiles:
    def test_list_parser_profiles(self, client: TestClient, uploader_token: str):
        resp = client.get(
            "/workbench/parser-profiles?collection_id=col_default",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        # Returns 501 because admin internal API is not implemented
        assert resp.status_code == 501
        assert resp.json()["detail"]["error_code"] == "DOWNSTREAM_NOT_IMPLEMENTED"

    def test_list_parser_profiles_no_auth(self, client: TestClient):
        resp = client.get("/workbench/parser-profiles?collection_id=col_default")
        assert resp.status_code == 401
