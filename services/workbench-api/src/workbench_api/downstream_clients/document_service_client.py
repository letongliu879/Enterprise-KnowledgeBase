"""Document Service downstream client."""

from ..config import config
from .base import BaseHttpClient


class DocumentServiceClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(
            base_url=base_url or config.document_service_base_url,
            timeout=config.default_http_timeout,
            service_name="Document service",
        )

    async def upload_file(self, collection_id: str, visibility: str, filename: str, content_bytes: bytes, mime_type: str, upload_id: str | None = None) -> dict:
        data = {"collection_id": collection_id, "visibility": visibility}
        if upload_id:
            data["upload_id"] = upload_id
        return await self._request("post", "/upload", data=data, files={"file": (filename, content_bytes, mime_type)})
