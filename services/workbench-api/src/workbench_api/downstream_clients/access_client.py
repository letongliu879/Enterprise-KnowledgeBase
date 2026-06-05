"""Access service downstream client for workbench retrieval verification."""

from ..config import config
from .base import BaseHttpClient


class AccessClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(
            base_url=base_url or config.access_base_url,
            timeout=config.default_http_timeout,
            service_name="Access",
            api_key=getattr(config, "access_internal_api_key", ""),
        )

    async def retrieve(self, payload: dict) -> dict:
        return await self._request("post", "/v1/retrieve", json=payload)
