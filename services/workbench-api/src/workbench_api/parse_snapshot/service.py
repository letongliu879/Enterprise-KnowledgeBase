"""Parse snapshot service."""

from ..deps import CurrentUser
from ..downstream_clients import IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable, forbidden
from ..upload_sessions.repository import UploadSessionRepository


class ParseSnapshotService:
    def __init__(self, indexing_client: IndexingClient, upload_repository: UploadSessionRepository | None = None):
        self._indexing_client = indexing_client
        self._upload_repository = upload_repository

    def _check_snapshot_acl(self, snapshot: dict, parse_snapshot_id: str, user: CurrentUser) -> None:
        collection_id = str(snapshot.get("collection_id") or "")
        if not collection_id and self._upload_repository is not None:
            upload = self._upload_repository.get_by_parse_snapshot_id(parse_snapshot_id)
            if upload is not None:
                collection_id = upload.collection_id
        if not collection_id:
            raise forbidden("Collection access denied")
        if not user.can_access_collection(collection_id):
            raise forbidden("Collection access denied")

    async def _fetch_snapshot(self, parse_snapshot_id: str) -> dict:
        try:
            return await self._indexing_client.get_parse_snapshot(parse_snapshot_id)
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Parse snapshot API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Indexing service unavailable")
            raise

    async def get_snapshot(self, parse_snapshot_id: str, user: CurrentUser) -> dict:
        result = await self._fetch_snapshot(parse_snapshot_id)
        self._check_snapshot_acl(result, parse_snapshot_id, user)
        return result

    async def get_snapshot_chunks(self, parse_snapshot_id: str, page: int, page_size: int, user: CurrentUser) -> dict:
        snapshot = await self._fetch_snapshot(parse_snapshot_id)
        self._check_snapshot_acl(snapshot, parse_snapshot_id, user)
        try:
            result = await self._indexing_client.get_parse_snapshot_chunks(parse_snapshot_id, page, page_size)
            return {"items": result if isinstance(result, list) else result.get("items", []), "total": len(result) if isinstance(result, list) else result.get("total", 0)}
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                raise downstream_not_implemented("Parse snapshot chunks API not yet implemented")
            if e.code == "DOWNSTREAM_UNAVAILABLE":
                raise downstream_unavailable("Indexing service unavailable")
            raise
