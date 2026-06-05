"""Admin service downstream client."""

from ..config import config
from .base import BaseHttpClient


class AdminClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(
            base_url=base_url or config.admin_base_url,
            timeout=config.default_http_timeout,
            service_name="Admin",
        )

    async def get_collection(self, collection_id: str) -> dict:
        return await self._request("get", f"/admin/collections/{collection_id}")

    async def list_parser_profiles(self) -> list[dict]:
        return await self._request("get", "/admin/parser-profiles")
