"""Parse snapshot service."""

from ..deps import CurrentUser
from ..downstream_clients import IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, not_found


class ParseSnapshotService:
    def __init__(self, indexing_client: IndexingClient):
        self._indexing_client = indexing_client

    async def get_snapshot(self, parse_snapshot_id: str, user: CurrentUser) -> dict:
        try:
            result = await self._indexing_client.get_parse_snapshot(parse_snapshot_id)
            return result
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Parse snapshot API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Indexing service unavailable")
            raise

    async def get_snapshot_chunks(self, parse_snapshot_id: str, page: int, page_size: int, user: CurrentUser) -> dict:
        try:
            result = await self._indexing_client.get_parse_snapshot_chunks(parse_snapshot_id, page, page_size)
            return {"items": result if isinstance(result, list) else result.get("items", []), "total": len(result) if isinstance(result, list) else result.get("total", 0)}
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Parse snapshot chunks API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Indexing service unavailable")
            raise
