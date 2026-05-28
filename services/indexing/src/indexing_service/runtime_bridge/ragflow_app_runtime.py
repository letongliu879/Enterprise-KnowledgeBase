from __future__ import annotations

import base64
import logging
from importlib import import_module
from io import BytesIO
from pathlib import Path
import asyncio

from PIL import Image

from indexing_service.runtime_bridge.asset_resolver import LocalAssetResolver
from indexing_service.runtime_bridge.progress_sink import IndexingProgressCollector
from indexing_service.upstream_parser_config import deep_merge, get_parser_config
from indexing_service.upstream_chunk_orchestrator import UpstreamChunkOrchestrator

_logger = logging.getLogger(__name__)


def _pil_to_base64(img: Image.Image) -> str:
    """Convert a PIL Image to base64 JPEG string. Closes the image on success."""
    try:
        converted = img
        if converted.mode in ("RGBA", "P"):
            converted = converted.convert("RGB")
        buf = BytesIO()
        converted.save(buf, format="JPEG")
        result = base64.b64encode(buf.getvalue()).decode("ascii")
        _logger.debug("converted PIL Image to base64 (%d bytes)", buf.tell())
        return result
    finally:
        try:
            img.close()
        except Exception:
            pass


def _sanitize_for_json(obj):
    """Recursively replace PIL Image objects with base64-encoded JPEG strings.
    Upstream RAGFlow uses image2id() with MinIO upload; we use inline base64
    for JSON-safe serialization.
    """
    if isinstance(obj, Image.Image):
        return _pil_to_base64(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def _strip_images(chunks: list[dict]) -> list[dict]:
    """Apply recursive PIL Image sanitization to all chunks."""
    return [_sanitize_for_json(chunk) for chunk in chunks]


def _default_callback(progress_collector: IndexingProgressCollector):
    def callback(prog=None, msg=""):
        if prog is None:
            progress_collector.emit(None, msg)
            return
        try:
            progress_collector.emit(float(prog), msg)
        except (TypeError, ValueError):
            progress_collector.emit(None, msg)

    return callback


class RAGFlowAppRuntime:
    def __init__(self) -> None:
        self._assets = LocalAssetResolver()
        self._orchestrator = UpstreamChunkOrchestrator()

    def build_preview(
        self,
        *,
        asset_ref: str,
        parser_id: str,
        parser_config: dict[str, object] | None,
        fallback_title: str,
        tenant_id: str,
        source_file_id: str | None = None,
    ) -> dict[str, object]:
        resolved = self._assets.resolve(asset_ref)
        progress = IndexingProgressCollector()
        chunker = self._load_chunker(parser_id)
        callback = _default_callback(progress)
        effective_parser_config = _merge_upstream_parser_config(
            parser_id=parser_id,
            parser_config=parser_config or {},
        )
        kb_id = source_file_id or resolved.asset_ref or resolved.filename
        chunks = chunker(
            resolved.filename,
            binary=resolved.bytes_data,
            from_page=0,
            to_page=100000,
            lang="Chinese",
            callback=callback,
            parser_config=effective_parser_config,
            tenant_id=tenant_id,
            kb_id=kb_id,
        ) or []
        persisted_parser_config = _load_kb_parser_config(kb_id)
        if persisted_parser_config:
            effective_parser_config = deep_merge(effective_parser_config, persisted_parser_config)
        raw_chunks = [dict(chunk) for chunk in chunks if isinstance(chunk, dict)]
        normalized_chunks = _strip_images(raw_chunks)
        postprocessed = asyncio.run(
            self._orchestrator.process(
                parser_id=parser_id,
                parser_config=effective_parser_config,
                chunks=normalized_chunks,
                tenant_id=tenant_id,
                language="Chinese",
            )
        )
        normalized_chunks = postprocessed.chunks
        preview_text = "\n\n".join(
            str(chunk.get("content_with_weight", "")).strip()
            for chunk in normalized_chunks
            if str(chunk.get("content_with_weight", "")).strip()
        )[:8000]
        outline = list(postprocessed.outline)
        if not outline:
            outline = [fallback_title]
        return {
            "preview_text": preview_text,
            "upstream_chunks": normalized_chunks,
            "outline": outline,
            "progress_events": [*progress.events, *postprocessed.progress_events],
            "document_metadata": dict(postprocessed.document_metadata),
            "warnings": list(postprocessed.warnings),
            "parser_config": effective_parser_config,
            "source_filename": resolved.filename,
            "source_suffix": resolved.suffix or Path(resolved.filename).suffix.lower().lstrip("."),
        }

    @staticmethod
    def _load_chunker(parser_id: str):
        module = import_module(f"ragflow_runtime.rag_app.{parser_id}")
        return getattr(module, "chunk")


def _load_kb_parser_config(kb_id: str) -> dict[str, object]:
    from api.db.services.knowledgebase_service import KnowledgebaseService

    ok, kb = KnowledgebaseService.get_by_id(kb_id)
    if not ok or kb is None:
        return {}
    parser_config = getattr(kb, "parser_config", None)
    return dict(parser_config or {})


def _merge_upstream_parser_config(*, parser_id: str, parser_config: dict[str, object]) -> dict[str, object]:
    return dict(get_parser_config(parser_id, parser_config) or {})
