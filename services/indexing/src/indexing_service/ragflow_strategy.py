from __future__ import annotations

import re
from pathlib import Path


class FileType:
    PDF = "pdf"
    DOC = "doc"
    VISUAL = "visual"
    AURAL = "aural"
    OTHER = "other"


def filename_type(filename: str) -> str:
    normalized = Path(filename).name.lower().strip()
    if not normalized:
        return FileType.OTHER
    if re.match(r".*\.pdf$", normalized):
        return FileType.PDF
    if re.match(
        r".*\.(msg|eml|doc|docx|ppt|pptx|yml|xml|htm|json|jsonl|ldjson|csv|txt|ini|xls|xlsx|wps|rtf|hlp|pages|numbers|key|md|mdx|py|js|java|c|cpp|h|php|go|ts|sh|cs|kt|html|sql|epub)$",
        normalized,
    ):
        return FileType.DOC
    if re.match(r".*\.(wav|flac|ape|alac|wavpack|wv|mp3|aac|ogg|vorbis|opus)$", normalized):
        return FileType.AURAL
    if re.match(
        r".*\.(jpg|jpeg|png|tif|gif|pcx|tga|exif|fpx|svg|psd|cdr|pcd|dxf|ufo|eps|ai|raw|wmf|webp|avif|apng|icon|ico|mpg|mpeg|avi|rm|rmvb|mov|wmv|asf|dat|asx|wvx|mpe|mpa|mp4|mkv)$",
        normalized,
    ):
        return FileType.VISUAL
    return FileType.OTHER


def get_ragflow_parser(
    *,
    filename: str,
    collection_default_parser_id: str | None,
) -> str:
    # Source-anchored to upstream ragflow api/db/services/file_service.py:get_parser.
    # This function must remain a thin host-side port of upstream parser_id selection.
    doc_type = filename_type(filename)
    if doc_type == FileType.VISUAL:
        return "picture"
    if doc_type == FileType.AURAL:
        return "audio"
    if re.search(r"\.(ppt|pptx|pages)$", filename, re.IGNORECASE):
        return "presentation"
    if re.search(r"\.(msg|eml)$", filename, re.IGNORECASE):
        return "email"
    return (collection_default_parser_id or "naive").strip().lower()
