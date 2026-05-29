"""Document Service downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class DocumentServiceClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.document_service_base_url).rstrip("/")
        self._timeout = config.default_http_timeout

    async def upload_file(self, collection_id: str, visibility: str, filename: str, content_bytes: bytes, mime_type: str) -> dict:
        url = f"{self._base_url}/upload"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    data={"collection_id": collection_id, "visibility": visibility},
                    files={"file": (filename, content_bytes, mime_type)},
                )
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Document service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Document service timeout: {e}")
        return self._handle_response(response, url)

    def _handle_response(self, response: httpx.Response, url: str) -> dict:
        if response.status_code == 404:
            raise DownstreamError.not_implemented(f"Document service endpoint not implemented: {url}")
        if response.status_code == 501:
            raise DownstreamError.not_implemented(f"Document service endpoint not implemented: {url}")
        if response.status_code >= 400:
            raise DownstreamError(
                "DOWNSTREAM_ERROR",
                f"Document service returned {response.status_code}: {response.text}",
                response.status_code,
            )
        return response.json()
