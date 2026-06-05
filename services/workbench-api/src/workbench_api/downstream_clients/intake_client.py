"""Intake-pipeline downstream client."""

from ..config import config
from .base import BaseHttpClient


class IntakeClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        self._document_service_url = config.document_service_base_url.rstrip("/")
        self._ingestion_worker_url = (base_url or config.ingestion_worker_url).rstrip("/")
        self._publishing_url = config.publishing_base_url.rstrip("/")
        super().__init__(
            base_url=self._document_service_url,
            timeout=config.default_http_timeout,
            service_name="Intake",
        )

    async def create_source_file(self, command: dict) -> dict:
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
        return await self._request("post", "/internal/source-files", json=flat_request)

    async def get_source_file(self, source_file_id: str) -> dict:
        return await self._request("get", f"/internal/source-files/{source_file_id}")

    async def get_intake_job(self, intake_job_id: str) -> dict:
        return await self._request("get", f"{self._ingestion_worker_url}/internal/intake-jobs/{intake_job_id}")

    async def get_published_document(self, published_document_id: str) -> dict:
        return await self._request("get", f"{self._publishing_url}/internal/published-documents/{published_document_id}")
