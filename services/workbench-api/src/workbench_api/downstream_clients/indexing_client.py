"""Indexing service downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class IndexingClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.indexing_base_url).rstrip("/")
        self._timeout = config.default_http_timeout

    async def create_parse_preview(self, command: dict) -> dict:
        url = f"{self._base_url}/internal/parse-previews"
        return await self._post(url, command)

    async def get_parse_snapshot(self, parse_snapshot_id: str) -> dict:
        url = f"{self._base_url}/internal/parse-snapshots/{parse_snapshot_id}"
        return await self._get(url)

    async def get_parse_snapshot_chunks(self, parse_snapshot_id: str, page: int = 1, page_size: int = 50) -> dict:
        url = f"{self._base_url}/internal/parse-snapshots/{parse_snapshot_id}/chunks"
        return await self._get(url, params={"page": page, "page_size": page_size})

    async def query_chunks(self, tenant_id: str, principal_id: str, collection_id: str | None = None) -> list[dict]:
        url = f"{self._base_url}/internal/chunks"
        params: dict = {"tenant_id": tenant_id, "principal_id": principal_id}
        if collection_id:
            params["collection_id"] = collection_id
        return await self._get(url, params=params)

    async def get_indexed_documents(self, collection_id: str | None = None, final_doc_id: str | None = None) -> list[dict]:
        url = f"{self._base_url}/internal/indexed-documents"
        params: dict = {}
        if collection_id:
            params["collection_id"] = collection_id
        if final_doc_id:
            params["final_doc_id"] = final_doc_id
        return await self._get(url, params=params)

    async def create_chunk_revision(self, evidence_id: str, command: dict) -> dict:
        url = f"{self._base_url}/internal/chunks/{evidence_id}/revisions"
        return await self._post(url, command)

    async def validate_parser_profile(self, parser_config: dict) -> dict:
        url = f"{self._base_url}/internal/parser-profiles/validate"
        return await self._post(url, parser_config)

    async def _get(self, url: str, params: dict | None = None) -> dict | list:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Indexing service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Indexing service timeout: {e}")
        return self._handle_response(response, url)

    async def _post(self, url: str, json: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=json)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Indexing service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Indexing service timeout: {e}")
        return self._handle_response(response, url)

    def _handle_response(self, response: httpx.Response, url: str) -> dict | list:
        if response.status_code == 404:
            raise DownstreamError.not_implemented(f"Indexing endpoint not implemented: {url}")
        if response.status_code == 501:
            raise DownstreamError.not_implemented(f"Indexing endpoint not implemented: {url}")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"Indexing conflict: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Indexing service returned {response.status_code}: {response.text}", response.status_code)
        return response.json()
