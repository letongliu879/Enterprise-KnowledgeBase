"""Fake converter for tests — replaces the real converter.

Does not parse files locally; returns a canned ConversionResult so that
IngestionPipeline and run_conversion_stage can be tested without:
- a running indexing-service (RAGFlow converter)
"""

from __future__ import annotations

from pathlib import Path

from reality_rag_contracts import ConversionRequest, ConversionResult, ConversionStatus

from ingestion_worker.converters.base import BaseConverter


class FakeConverter(BaseConverter):
    """Test-only converter that returns pre-configured text."""

    def __init__(self, canonical_md: str = "", *, metadata: dict[str, object] | None = None) -> None:
        self._canonical_md = canonical_md
        self._metadata = metadata or {}

    def supported_extensions(self) -> list[str]:
        return [".txt", ".md", ".pdf", ".docx", ".pptx", ".xlsx"]

    def convert(self, request: ConversionRequest) -> ConversionResult:
        source_path = Path(request.source_file_path)
        ext = source_path.suffix.lower()

        if ext not in self.supported_extensions():
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

        canonical = self._canonical_md or (source_path.read_text(encoding="utf-8") if source_path.exists() else "")
        return ConversionResult(
            source_file_path=request.source_file_path,
            conversion_status=ConversionStatus.SUCCESS,
            canonical_md=canonical,
            metadata={
                "file_size": source_path.stat().st_size if source_path.exists() else 0,
                "extension": ext,
                "converter": "fake_converter",
                **self._metadata,
            },
        )
