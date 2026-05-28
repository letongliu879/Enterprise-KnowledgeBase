"""Tests for downstream client gates."""

import pytest
from fastapi.testclient import TestClient
import httpx

from admin_service.downstream_clients.indexing_client import IndexingClient
from admin_service.downstream_clients.retrieval_client import RetrievalClient
from admin_service.downstream_clients.access_client import AccessClient
from admin_service.downstream_clients.errors import DownstreamError


class TestIndexingClient:
    @pytest.mark.asyncio
    async def test_validate_parser_profile_not_implemented(self, respx_mock):
        client = IndexingClient(base_url="http://indexing-test")
        respx_mock.post("http://indexing-test/internal/parser-profiles/validate").respond(404)
        with pytest.raises(DownstreamError) as exc_info:
            await client.validate_parser_profile({"parser_id": "naive"})
        assert exc_info.value.code == "DOWNSTREAM_NOT_IMPLEMENTED"
        assert exc_info.value.status_code == 501

    @pytest.mark.asyncio
    async def test_validate_parser_profile_unavailable(self, respx_mock):
        client = IndexingClient(base_url="http://indexing-test")
        respx_mock.post("http://indexing-test/internal/parser-profiles/validate").mock(side_effect=httpx.ConnectError("Connection refused"))
        with pytest.raises(DownstreamError) as exc_info:
            await client.validate_parser_profile({"parser_id": "naive"})
        assert exc_info.value.code == "DOWNSTREAM_UNAVAILABLE"
        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_validate_parser_profile_success(self, respx_mock):
        client = IndexingClient(base_url="http://indexing-test")
        respx_mock.post("http://indexing-test/internal/parser-profiles/validate").respond(200, json={"canonical": "config"})
        result = await client.validate_parser_profile({"parser_id": "naive"})
        assert result == {"canonical": "config"}

    @pytest.mark.asyncio
    async def test_validate_parser_profile_conflict(self, respx_mock):
        client = IndexingClient(base_url="http://indexing-test")
        respx_mock.post("http://indexing-test/internal/parser-profiles/validate").respond(409, text="Invalid config")
        with pytest.raises(DownstreamError) as exc_info:
            await client.validate_parser_profile({"parser_id": "naive"})
        assert exc_info.value.code == "CONFLICT"
        assert exc_info.value.status_code == 409


class TestRetrievalClient:
    @pytest.mark.asyncio
    async def test_validate_retrieval_profile_not_implemented(self, respx_mock):
        client = RetrievalClient(base_url="http://retrieval-test")
        respx_mock.post("http://retrieval-test/internal/retrieval-profiles/validate").respond(501)
        with pytest.raises(DownstreamError) as exc_info:
            await client.validate_retrieval_profile({"bm25_weight": 0.5})
        assert exc_info.value.code == "DOWNSTREAM_NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_validate_retrieval_profile_unavailable(self, respx_mock):
        client = RetrievalClient(base_url="http://retrieval-test")
        respx_mock.post("http://retrieval-test/internal/retrieval-profiles/validate").mock(side_effect=httpx.TimeoutException("Timeout"))
        with pytest.raises(DownstreamError) as exc_info:
            await client.validate_retrieval_profile({"bm25_weight": 0.5})
        assert exc_info.value.code == "DOWNSTREAM_UNAVAILABLE"


class TestAccessClient:
    @pytest.mark.asyncio
    async def test_sync_api_key_not_implemented(self, respx_mock):
        client = AccessClient(base_url="http://access-test")
        respx_mock.post("http://access-test/internal/api-key-projections/sync").respond(404)
        with pytest.raises(DownstreamError) as exc_info:
            await client.sync_api_key_projection({"api_key_id": "key-1"})
        assert exc_info.value.code == "DOWNSTREAM_NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_sync_api_key_unavailable(self, respx_mock):
        client = AccessClient(base_url="http://access-test")
        respx_mock.post("http://access-test/internal/api-key-projections/sync").mock(side_effect=httpx.ConnectError("Connection refused"))
        with pytest.raises(DownstreamError) as exc_info:
            await client.sync_api_key_projection({"api_key_id": "key-1"})
        assert exc_info.value.code == "DOWNSTREAM_UNAVAILABLE"
