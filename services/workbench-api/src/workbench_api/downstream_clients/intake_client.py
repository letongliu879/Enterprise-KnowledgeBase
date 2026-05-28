"""Intake-pipeline downstream client."""

import httpx

from ..config import config
from .errors import DownstreamError


class IntakeClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or config.intake_base_url).rstrip("/")
        self._timeout = config.default_http_timeout

    async def create_source_file(self, command: dict) -> dict:
        url = f"{self._base_url}/internal/source-files"
        # Unwrap command envelope to flat RegisterSourceFileRequest format
        payload = command.get("payload", {})
        flat_request = {
            "command_id": command.get("command_id", ""),
            "trace_id": command.get("trace_id", ""),
            "idempotency_key": command.get("idempotency_key", ""),
            "actor": command.get("actor", ""),
            "tenant_id": command.get("tenant_id", ""),
            "collection_id": command.get("collection_id", ""),
            "filename": payload.get("filename", ""),
            "mime_type": payload.get("mime_type", ""),
            "size_bytes": payload.get("size_bytes", 0),
            "selected_parser_profile_id": payload.get("selected_parser_profile_id"),
            "parser_override_json": payload.get("parser_override_json"),
        }
        return await self._post(url, flat_request)

    async def get_source_file(self, source_file_id: str) -> dict:
        url = f"{self._base_url}/internal/source-files/{source_file_id}"
        return await self._get(url)

    async def get_intake_job(self, intake_job_id: str) -> dict:
        url = f"{self._base_url}/internal/intake-jobs/{intake_job_id}"
        return await self._get(url)

    async def get_published_document(self, published_document_id: str) -> dict:
        url = f"{self._base_url}/internal/published-documents/{published_document_id}"
        return await self._get(url)

    async def _get(self, url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Intake service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Intake service timeout: {e}")
        return self._handle_response(response, url)

    async def _post(self, url: str, json: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=json)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"Intake service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"Intake service timeout: {e}")
        return self._handle_response(response, url)

    def _handle_response(self, response: httpx.Response, url: str) -> dict:
        if response.status_code == 404:
            raise DownstreamError.not_implemented(f"Intake endpoint not implemented: {url}")
        if response.status_code == 501:
            raise DownstreamError.not_implemented(f"Intake endpoint not implemented: {url}")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"Intake conflict: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError("DOWNSTREAM_ERROR", f"Intake service returned {response.status_code}: {response.text}", response.status_code)
        return response.json()
