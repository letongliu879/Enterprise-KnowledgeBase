from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

import httpx

from reality_rag_contracts import ConversionRequest, ConversionResult, ConversionStatus

from .base import BaseConverter

_RAGFLOW_EXTENSIONS: set[str] = {
    ".txt", ".md", ".markdown",
    ".csv", ".json", ".xml", ".html", ".htm",
    ".pdf",
    ".docx", ".doc",
    ".pptx", ".ppt",
    ".xlsx", ".xls",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".mp3", ".wav", ".ogg", ".flac",
    ".zip",
    ".epub",
    ".eml", ".msg",
    ".ipynb",
}


def _indexing_base_url() -> str | None:
    return os.environ.get("INDEXING_SERVICE_URL", "").rstrip("/") or None


class RAGFlowConverter(BaseConverter):
    """Delegate document parsing to the indexing owner and return canonical text."""

    def supported_extensions(self) -> list[str]:
        return sorted(_RAGFLOW_EXTENSIONS)

    def convert(self, request: ConversionRequest) -> ConversionResult:
        source_path = Path(request.source_file_path)
        ext = source_path.suffix.lower()

        if ext not in _RAGFLOW_EXTENSIONS:
            return ConversionResult(
                source_file_path=request.source_file_path,
                conversion_status=ConversionStatus.UNSUPPORTED,
                error_message=f"Unsupported file extension: {ext}",
            )

        if not source_path.exists():
            return ConversionResult(
                source_file_path=request.source_file_path,
                conversion_status=ConversionStatus.FAILED,
                error_message=f"File not found: {request.source_file_path}",
            )

        try:
            options = dict(request.options or {})
            metadata = {
                key: str(value)
                for key, value in dict(options.get("metadata", {})).items()
                if str(key).strip()
            }
            source_file_id = str(options.get("source_file_id") or request.collection_id).strip() or request.collection_id
            tenant_id = str(options.get("tenant_id") or "default").strip() or "default"
            trace_id = str(options.get("trace_id") or f"trace_{source_file_id}").strip()
            mime_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"

            command = {
                "request_id": f"req_{source_file_id}",
                "tenant_id": tenant_id,
                "collection_id": request.collection_id,
                "source_file_id": source_file_id,
                "source_binary_ref": str(source_path),
                "filename": source_path.name,
                "mime_type": mime_type,
                "source_system": "intake-conversion",
                "metadata": metadata,
                "trace_id": trace_id,
            }
            accepted, snapshot = self._parse_via_indexing(command)
            canonical_md = str(snapshot.get("preview_text") or "").strip()
            if not canonical_md:
                canonical_md = "\n\n".join(
                    str(chunk.get("content_with_weight", "")).strip()
                    for chunk in snapshot.get("upstream_chunks", [])
                    if str(chunk.get("content_with_weight", "")).strip()
                ).strip()
            if not canonical_md:
                return ConversionResult(
                    source_file_path=request.source_file_path,
                    conversion_status=ConversionStatus.FAILED,
                    error_message="indexing parse returned no canonical preview text",
                    warnings=[str(item) for item in snapshot.get("warnings", []) if str(item).strip()],
                    metadata={
                        "file_size": source_path.stat().st_size,
                        "extension": ext,
                        "converter": "indexing_parse",
                        "parse_snapshot_id": str(accepted.get("parse_snapshot_id") or ""),
                    },
                )

            return ConversionResult(
                source_file_path=request.source_file_path,
                conversion_status=ConversionStatus.SUCCESS,
                canonical_md=canonical_md,
                warnings=[str(item) for item in snapshot.get("warnings", []) if str(item).strip()],
                metadata={
                    "file_size": source_path.stat().st_size,
                    "extension": ext,
                    "converter": "indexing_parse",
                    "parse_snapshot_id": str(accepted.get("parse_snapshot_id") or ""),
                    "parser_id": str(accepted.get("parser_id") or snapshot.get("parser_id") or ""),
                    "parser_profile_id": str(snapshot.get("parser_profile_id") or accepted.get("parser_id") or ""),
                    "chunk_profile_id": str(snapshot.get("chunk_profile_id") or snapshot.get("parser_id") or ""),
                    "document_family": str(snapshot.get("document_family") or ""),
                    "effective_policy": str(snapshot.get("effective_policy") or snapshot.get("decision_reason") or ""),
                    "parser_backend": str(snapshot.get("parser_backend") or ""),
                    "source_suffix": str(snapshot.get("source_suffix") or ext.lstrip(".")),
                    "decision_reason": str(accepted.get("decision_reason") or snapshot.get("decision_reason") or ""),
                    "upstream_chunk_count": len(snapshot.get("upstream_chunks", [])),
                    "chunk_preview_count": len(snapshot.get("chunk_preview", [])),
                    "outline": list(snapshot.get("outline", [])),
                    "document_metadata": dict(snapshot.get("document_metadata", {})),
                    "parser_config": dict(snapshot.get("parser_config", {})),
                    "trace_id": trace_id,
                    "source_file_id": source_file_id,
                },
            )
        except Exception as exc:
            return ConversionResult(
                source_file_path=request.source_file_path,
                conversion_status=ConversionStatus.FAILED,
                error_message=str(exc),
                metadata={
                    "file_size": source_path.stat().st_size if source_path.exists() else 0,
                    "extension": ext,
                    "converter": "indexing_parse",
                },
            )

    def _parse_via_indexing(self, command: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        base_url = _indexing_base_url()
        if not base_url:
            raise RuntimeError(
                "INDEXING_SERVICE_URL is not configured; "
                "intake-pipeline cannot parse documents without the indexing owner"
            )

        with httpx.Client(timeout=180.0) as client:
            accepted = client.post(f"{base_url}/internal/parse-previews", json=command)
            accepted.raise_for_status()
            accepted_payload = accepted.json()
            snapshot = client.get(
                f"{base_url}/internal/parse-snapshots/{accepted_payload['parse_snapshot_id']}"
            )
            snapshot.raise_for_status()
            return accepted_payload, snapshot.json()
