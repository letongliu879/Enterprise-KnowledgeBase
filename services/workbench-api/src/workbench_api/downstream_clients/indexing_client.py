"""Indexing service downstream client."""

from ..config import config
from .base import BaseHttpClient


class IndexingClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(
            base_url=base_url or config.indexing_base_url,
            timeout=config.default_http_timeout,
            service_name="Indexing",
        )

    async def create_parse_preview(self, command: dict) -> dict:
        return await self._request("post", "/internal/parse-previews", json=command)

    async def get_parse_snapshot(self, parse_snapshot_id: str) -> dict:
        return await self._request("get", f"/internal/parse-snapshots/{parse_snapshot_id}")

    async def get_parse_snapshot_chunks(self, parse_snapshot_id: str, page: int = 1, page_size: int = 50) -> dict:
        return await self._request("get", f"/internal/parse-snapshots/{parse_snapshot_id}/chunks", params={"page": page, "page_size": page_size})

    async def query_chunks(self, tenant_id: str, principal_id: str, collection_id: str | None = None) -> list[dict]:
        params: dict = {"tenant_id": tenant_id, "principal_id": principal_id}
        if collection_id:
            params["collection_id"] = collection_id
        return await self._request("get", "/internal/chunks", params=params)

    async def get_indexed_documents(self, collection_id: str | None = None, final_doc_id: str | None = None) -> list[dict]:
        params: dict = {}
        if collection_id:
            params["collection_id"] = collection_id
        if final_doc_id:
            params["final_doc_id"] = final_doc_id
        return await self._request("get", "/internal/indexed-documents", params=params)

    async def create_chunk_revision(self, evidence_id: str, command: dict) -> dict:
        return await self._request("post", f"/internal/chunks/{evidence_id}/revisions", json=command)

    async def validate_parser_profile(self, parser_config: dict) -> dict:
        return await self._request("post", "/internal/parser-profiles/validate", json=parser_config)
