"""Downstream HTTP clients for workbench service."""

import httpx

from ..config import config
from .errors import DownstreamError


class BaseHttpClient:
    """Base HTTP client with unified error handling and connection pooling."""

    def __init__(self, base_url: str, timeout: float, service_name: str, *, api_key: str = ""):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._service_name = service_name
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    @property
    def _http_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, path_or_url: str, **kwargs) -> dict | list:
        """Make HTTP request with unified error handling."""
        if path_or_url.startswith("http"):
            url = path_or_url
        else:
            url = f"{self._base_url}{path_or_url}"

        headers = kwargs.pop("headers", {})
        if self._api_key:
            headers["X-API-Key"] = self._api_key
            headers["X-Agent-Instance-Id"] = "workbench-internal"

        try:
            response = await getattr(self._http_client, method)(url, headers=headers, **kwargs)
        except httpx.ConnectError as e:
            raise DownstreamError.unavailable(f"{self._service_name} service unreachable: {e}")
        except httpx.TimeoutException as e:
            raise DownstreamError.unavailable(f"{self._service_name} service timeout: {e}")

        if response.status_code in (404, 501):
            raise DownstreamError.not_implemented(f"{self._service_name} endpoint not implemented: {url}")
        if response.status_code == 409:
            raise DownstreamError.conflict(f"{self._service_name} conflict: {response.text}")
        if response.status_code >= 400:
            raise DownstreamError(
                "DOWNSTREAM_ERROR",
                f"{self._service_name} service returned {response.status_code}: {response.text}",
                response.status_code,
            )
        return response.json()


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


class AdminClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(
            base_url=base_url or config.admin_base_url,
            timeout=config.default_http_timeout,
            service_name="Admin",
        )

    async def get_collection(self, collection_id: str, *, headers: dict | None = None) -> dict:
        return await self._request("get", f"/admin/collections/{collection_id}", headers=headers)

    async def list_collections(self, tenant_id: str | None = None, *, headers: dict | None = None) -> dict:
        params = {"tenant_id": tenant_id} if tenant_id else {}
        return await self._request("get", "/admin/collections", params=params, headers=headers)

    async def create_collection(self, payload: dict, *, headers: dict | None = None) -> dict:
        return await self._request("post", "/admin/collections", json=payload, headers=headers)

    async def list_parser_profiles(self, *, headers: dict | None = None) -> list[dict]:
        return await self._request("get", "/admin/parser-profiles", headers=headers)

    async def list_retrieval_profiles(self, state: str | None = None, *, headers: dict | None = None) -> dict:
        params = {"state": state} if state else {}
        return await self._request("get", "/admin/retrieval-profiles", params=params, headers=headers)


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


class IndexingClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(
            base_url=base_url or config.indexing_base_url,
            timeout=config.default_http_timeout,
            service_name="Indexing",
        )

    async def create_parse_preview(self, command: dict) -> dict:
        return await self._request("post", "/internal/parse-previews", json=command)

    async def get_parse_snapshot(self, parse_snapshot_id: str) -> dict:
        return await self._request("get", f"/internal/parse-snapshots/{parse_snapshot_id}")

    async def get_parse_snapshot_chunks(self, parse_snapshot_id: str, page: int = 1, page_size: int = 50) -> dict:
        return await self._request("get", f"/internal/parse-snapshots/{parse_snapshot_id}/chunks", params={"page": page, "page_size": page_size})

    async def query_chunks(self, tenant_id: str, principal_id: str, collection_id: str | None = None) -> list[dict]:
        params: dict = {"tenant_id": tenant_id, "principal_id": principal_id}
        if collection_id:
            params["collection_id"] = collection_id
        return await self._request("get", "/internal/chunks", params=params)

    async def get_indexed_documents(self, collection_id: str | None = None, final_doc_id: str | None = None) -> list[dict]:
        params: dict = {}
        if collection_id:
            params["collection_id"] = collection_id
        if final_doc_id:
            params["final_doc_id"] = final_doc_id
        return await self._request("get", "/internal/indexed-documents", params=params)

    async def create_chunk_revision(self, evidence_id: str, command: dict) -> dict:
        return await self._request("post", f"/internal/chunks/{evidence_id}/revisions", json=command)

    async def validate_parser_profile(self, parser_config: dict) -> dict:
        return await self._request("post", "/internal/parser-profiles/validate", json=parser_config)


class ApprovalClient(BaseHttpClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(
            base_url=base_url or config.approval_base_url,
            timeout=config.default_http_timeout,
            service_name="Approval",
        )

    async def list_tickets(self, tenant_id: str, collection_id: str | None = None, status: str | None = None) -> list[dict]:
        params: dict = {"tenant_id": tenant_id}
        if collection_id:
            params["collection_id"] = collection_id
        if status:
            params["state"] = status
        result = await self._request("get", "/internal/tickets", params=params)
        if isinstance(result, dict):
            items = result.get("items", [])
            return items if isinstance(items, list) else []
        return result if isinstance(result, list) else []

    async def get_ticket(self, ticket_id: str) -> dict:
        return await self._request("get", f"/internal/tickets/{ticket_id}")

    async def decide_ticket(self, ticket_id: str, command: dict) -> dict:
        return await self._request("post", f"/internal/tickets/{ticket_id}/decide", json=command)

    async def get_agent_review(self, ticket_id: str) -> dict:
        return await self._request("get", f"/internal/tickets/{ticket_id}/agent-review")


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

    async def get_source_file_preview(self, source_file_id: str) -> dict:
        return await self._request("get", f"/internal/source-files/{source_file_id}/preview")

    async def get_intake_job(self, intake_job_id: str) -> dict:
        return await self._request("get", f"{self._ingestion_worker_url}/internal/intake-jobs/{intake_job_id}")

    async def get_published_document(self, published_document_id: str) -> dict:
        return await self._request("get", f"{self._publishing_url}/internal/published-documents/{published_document_id}")
