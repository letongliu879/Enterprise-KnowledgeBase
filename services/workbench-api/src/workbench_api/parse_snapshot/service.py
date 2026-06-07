"""Parse snapshot service."""

import mimetypes
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from reality_rag_persistence.models import (
    ChunkRegistryModel,
    IntakeJobModel,
    ParseSnapshotModel,
)

from ..config import config
from ..deps import CurrentUser
from ..downstream_clients import IndexingClient, IntakeClient
from ..downstream_clients.errors import DownstreamError
from ..errors import (
    downstream_not_implemented,
    downstream_unavailable,
    forbidden,
    not_found,
)
from ..upload_sessions.repository import UploadSessionRepository


class ParseSnapshotService:
    def __init__(
        self,
        indexing_client: IndexingClient,
        intake_client: IntakeClient,
        session: Session,
        upload_repository: UploadSessionRepository | None = None,
    ):
        self._indexing_client = indexing_client
        self._intake_client = intake_client
        self._session = session
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
        result = await self._get_snapshot_with_fallback(parse_snapshot_id)
        self._check_snapshot_acl(result, parse_snapshot_id, user)
        return result

    async def get_snapshot_chunks(self, parse_snapshot_id: str, page: int, page_size: int, user: CurrentUser) -> dict:
        snapshot = await self._get_snapshot_with_fallback(parse_snapshot_id)
        self._check_snapshot_acl(snapshot, parse_snapshot_id, user)
        final_doc_id = self._resolve_final_doc_id(snapshot)
        source_file_id = str(snapshot.get("source_file_id") or "")
        try:
            result = await self._indexing_client.get_parse_snapshot_chunks(parse_snapshot_id, page, page_size)
            items = result if isinstance(result, list) else result.get("items", [])
            return {
                "items": [
                    self._canonicalize_snapshot_chunk(item, final_doc_id, source_file_id)
                    for item in items
                ],
                "total": len(result) if isinstance(result, list) else result.get("total", 0),
            }
        except DownstreamError as e:
            if e.code in {"DOWNSTREAM_NOT_IMPLEMENTED", "DOWNSTREAM_UNAVAILABLE"}:
                return self._get_local_snapshot_chunks(snapshot, page, page_size)
            raise

    async def get_snapshot_source(
        self,
        parse_snapshot_id: str,
        user: CurrentUser,
    ) -> tuple[str, str, bytes]:
        snapshot = await self._get_snapshot_with_fallback(parse_snapshot_id)
        self._check_snapshot_acl(snapshot, parse_snapshot_id, user)

        source_file_id = str(snapshot.get("source_file_id") or "")
        if not source_file_id:
            raise not_found("Parse snapshot does not reference a source file")

        try:
            source_file = await self._intake_client.get_source_file(source_file_id)
        except DownstreamError as e:
            if e.code in {"DOWNSTREAM_NOT_IMPLEMENTED", "DOWNSTREAM_UNAVAILABLE"}:
                return self._get_local_snapshot_source(snapshot)
            raise

        download_url = (
            source_file.get("download_url")
            or source_file.get("storage_url")
            or source_file.get("preview_url")
        )
        if not download_url:
            return self._get_local_snapshot_source(snapshot)

        filename = str(
            source_file.get("original_name")
            or source_file.get("filename")
            or f"{source_file_id}.bin"
        )
        content_type = str(source_file.get("mime_type") or "application/octet-stream")

        try:
            async with httpx.AsyncClient(timeout=config.default_http_timeout) as client:
                response = await client.get(download_url)
                response.raise_for_status()
        except httpx.HTTPError:
            return self._get_local_snapshot_source(snapshot)

        return filename, content_type, response.content

    async def _get_snapshot_with_fallback(self, parse_snapshot_id: str) -> dict:
        try:
            return await self._fetch_snapshot(parse_snapshot_id)
        except Exception as exc:
            fallback = self._get_local_snapshot(parse_snapshot_id)
            if fallback is not None:
                return fallback
            raise exc

    def _get_local_snapshot(self, parse_snapshot_id: str) -> dict | None:
        row = (
            self._session.query(ParseSnapshotModel)
            .filter_by(parse_snapshot_id=parse_snapshot_id)
            .first()
        )
        if row is None:
            return None
        return {
            "parse_snapshot_id": row.parse_snapshot_id,
            "source_file_id": row.source_file_id,
            "tenant_id": row.tenant_id,
            "collection_id": row.collection_id,
            "source_binary_ref": row.source_binary_ref,
            "source_filename": row.source_filename,
            "source_suffix": row.source_suffix,
            "parser_id": row.parser_id,
            "parser_backend": row.parser_backend,
            "preview_text": row.preview_text,
            "outline": row.outline or [],
            "document_metadata": row.document_metadata or {},
            "chunk_preview": row.chunk_preview or [],
            "warnings": row.warnings or [],
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _get_local_snapshot_chunks(
        self,
        snapshot: dict,
        page: int,
        page_size: int,
    ) -> dict:
        source_file_id = str(snapshot.get("source_file_id") or "")
        job = (
            self._session.query(IntakeJobModel)
            .filter_by(source_file_id=source_file_id)
            .order_by(IntakeJobModel.updated_at.desc())
            .first()
        )
        if job is None or not job.final_doc_id:
            return {"items": [], "total": 0}

        rows = (
            self._session.query(ChunkRegistryModel)
            .filter_by(final_doc_id=job.final_doc_id, available_int=1)
            .order_by(ChunkRegistryModel.chunk_id.asc())
            .all()
        )
        items = [self._canonicalize_local_chunk(row.payload_json or {}) for row in rows]
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        return {"items": items[start:end], "total": len(items)}

    def _resolve_final_doc_id(self, snapshot: dict) -> str:
        source_file_id = str(snapshot.get("source_file_id") or "")
        if not source_file_id:
            return ""
        job = (
            self._session.query(IntakeJobModel)
            .filter_by(source_file_id=source_file_id)
            .order_by(IntakeJobModel.updated_at.desc())
            .first()
        )
        if job is None:
            return ""
        return str(job.final_doc_id or job.preliminary_doc_id or "")

    def _get_local_snapshot_source(self, snapshot: dict) -> tuple[str, str, bytes]:
        binary_ref = str(snapshot.get("source_binary_ref") or "")
        if not binary_ref:
            raise not_found("Source file download is not available")
        path = Path(binary_ref)
        if not path.exists():
            raise not_found("Source file bytes are not available locally")
        filename = str(snapshot.get("source_filename") or path.name or "source.bin")
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return filename, content_type, path.read_bytes()

    @staticmethod
    def _canonicalize_local_chunk(payload: dict) -> dict:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "evidence_id": payload.get("evidence_id") or payload.get("chunk_id", ""),
            "doc_id": payload.get("doc_id") or payload.get("final_doc_id", ""),
            "content": payload.get("content") or payload.get("display_text", ""),
            "vector_text": payload.get("vector_text"),
            "section_path": payload.get("section_path") or [],
            "page_spans": payload.get("page_spans") or [],
            "chunk_type": payload.get("chunk_type"),
            "metadata": metadata,
        }

    @staticmethod
    def _canonicalize_snapshot_chunk(
        chunk: dict,
        final_doc_id: str,
        source_file_id: str,
    ) -> dict:
        if not isinstance(chunk, dict):
            return chunk
        normalized = dict(chunk)
        raw_doc_id = str(normalized.get("doc_id") or normalized.get("final_doc_id") or "")
        if final_doc_id and (
            not raw_doc_id
            or raw_doc_id == source_file_id
            or raw_doc_id.startswith("src_")
        ):
            normalized["doc_id"] = final_doc_id
        return normalized
