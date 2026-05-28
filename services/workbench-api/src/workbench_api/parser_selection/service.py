"""Parser profile selection service."""

from ..deps import CurrentUser
from ..downstream_clients import AdminClient, IndexingClient
from ..downstream_clients.errors import DownstreamError
from ..errors import downstream_not_implemented, downstream_unavailable
from .models import ParserProfileItem, ParserProfileListResponse


class ParserSelectionService:
    def __init__(self, admin_client: AdminClient, indexing_client: IndexingClient):
        self._admin_client = admin_client
        self._indexing_client = indexing_client

    async def list_profiles(self, collection_id: str, user: CurrentUser) -> ParserProfileListResponse:
        if not user.can_access_collection(collection_id):
            raise ValueError("Collection access denied")

        # Try to get collection from admin
        default_parser_profile_id = ""
        try:
            collection = await self._admin_client.get_collection(collection_id)
            default_parser_profile_id = collection.get("default_parser_profile_id", "")
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                return self._not_implemented_response()
            raise

        # List available parser profiles from admin
        try:
            profiles_raw = await self._admin_client.list_parser_profiles()
        except DownstreamError as e:
            if e.code == "DOWNSTREAM_NOT_IMPLEMENTED":
                return self._not_implemented_response()
            raise

        items = []
        for p in profiles_raw:
            profile_id = p.get("parser_profile_id", "")
            items.append(ParserProfileItem(
                parser_profile_id=profile_id,
                name=p.get("name", ""),
                parser_id=p.get("parser_id", ""),
                state=p.get("state", "draft"),
                is_default=(profile_id == default_parser_profile_id),
            ))

        return ParserProfileListResponse(
            items=items,
            default_parser_profile_id=default_parser_profile_id,
        )

    def _not_implemented_response(self) -> ParserProfileListResponse:
        return ParserProfileListResponse(items=[], default_parser_profile_id="")
