"""Chunk service."""

from ..deps import CurrentUser
from ..downstream_clients import IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, not_found


class ChunkService:
    def __init__(self, indexing_client: IndexingClient):
        self._indexing_client = indexing_client

    async def get_chunk(self, evidence_id: str, user: CurrentUser) -> dict:
        try:
            # Query indexing service for specific chunk
            chunks = await self._indexing_client.query_chunks(
                tenant_id=user.tenant_id,
                principal_id=user.user_id,
            )
            for chunk in chunks:
                if chunk.get("evidence_id") == evidence_id or chunk.get("chunk_id") == evidence_id:
                    return self._canonicalize_chunk(chunk)
            raise not_found("Chunk not found")
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Chunk query API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Indexing service unavailable")
            raise

    async def patch_chunk(self, evidence_id: str, command: dict, user: CurrentUser) -> dict:
        try:
            result = await self._indexing_client.create_chunk_revision(evidence_id, command)
            return {
                "revision_id": result.get("revision_id", ""),
                "status": result.get("status", "accepted"),
            }
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Chunk revision API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Indexing service unavailable")
            raise

    def _canonicalize_chunk(self, chunk: dict) -> dict:
        """Map old wire fields to canonical wire fields."""
        return {
            "evidence_id": chunk.get("evidence_id") or chunk.get("chunk_id", ""),
            "doc_id": chunk.get("doc_id") or chunk.get("final_doc_id", ""),
            "content": chunk.get("content") or chunk.get("display_text", ""),
            "vector_text": chunk.get("vector_text"),
            "section_path": chunk.get("section_path"),
            "page_spans": chunk.get("page_spans"),
            "chunk_type": chunk.get("chunk_type"),
            "metadata": chunk.get("metadata", {}),
        }
