"""MarkItDown converter using the PyPI `markitdown` package."""

import os
from pathlib import Path

from markitdown import MarkItDown
from reality_rag_contracts import ConversionRequest, ConversionResult, ConversionStatus

from .base import BaseConverter

_MARKITDOWN_EXTENSIONS: set[str] = {
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


class MarkItDownConverter(BaseConverter):
    """Convert files to canonical markdown using the PyPI `markitdown` package."""

    def __init__(self) -> None:
        self._markitdown = MarkItDown()

    def supported_extensions(self) -> list[str]:
        return sorted(_MARKITDOWN_EXTENSIONS)

    def convert(self, request: ConversionRequest) -> ConversionResult:
        source_path = Path(request.source_file_path)
        ext = source_path.suffix.lower()

        if ext not in _MARKITDOWN_EXTENSIONS:
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
            result = self._markitdown.convert(str(source_path))
            canonical_md = getattr(result, "text_content", "")
            if not isinstance(canonical_md, str):
                # markitdown version changed the attribute name; fall back safely
                canonical_md = ""
            return ConversionResult(
                source_file_path=request.source_file_path,
                conversion_status=ConversionStatus.SUCCESS,
                canonical_md=canonical_md,
                metadata={
                    "file_size": source_path.stat().st_size,
                    "extension": ext,
                    "converter": "markitdown",
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
                    "converter": "markitdown",
                },
            )
