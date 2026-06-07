from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_WORD_EXTENSIONS = {"doc", "docx", "docm", "rtf"}
_POWERPOINT_EXTENSIONS = {"ppt", "pptx", "pptm"}
_EXCEL_EXTENSIONS = {"xls", "xlsx", "xlsm"}


@dataclass(frozen=True)
class PreviewDescriptor:
    source_file_id: str
    filename: str
    mime_type: str
    preview_available: bool
    preview_status: str
    preview_kind: str
    preview_mime_type: str | None
    preview_url: str | None
    thumbnail_url: str | None = None
    page_count: int | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "source_file_id": self.source_file_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "preview_available": self.preview_available,
            "preview_status": self.preview_status,
            "preview_kind": self.preview_kind,
            "preview_mime_type": self.preview_mime_type,
            "preview_url": self.preview_url,
            "thumbnail_url": self.thumbnail_url,
            "page_count": self.page_count,
        }


def _runtime_dir() -> Path:
    configured = os.environ.get("REALITY_RAG_INTAKE_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[5] / ".verify" / "runtime" / "intake"


def _preview_dir(source_file_id: str) -> Path:
    return _runtime_dir() / "source-preview" / source_file_id


def _manifest_path(source_file_id: str) -> Path:
    return _preview_dir(source_file_id) / "manifest.json"


def _preview_pdf_path(source_file_id: str) -> Path:
    return _preview_dir(source_file_id) / "preview.pdf"


def _guess_mime_type(filename: str, source_file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename or source_file_path)
    return mime_type or "application/octet-stream"


def _build_descriptor(
    *,
    source_file_id: str,
    filename: str,
    mime_type: str,
    preview_available: bool,
    preview_status: str,
    preview_kind: str,
    preview_mime_type: str | None,
    preview_url: str | None,
    thumbnail_url: str | None = None,
    page_count: int | None = None,
) -> PreviewDescriptor:
    return PreviewDescriptor(
        source_file_id=source_file_id,
        filename=filename,
        mime_type=mime_type,
        preview_available=preview_available,
        preview_status=preview_status,
        preview_kind=preview_kind,
        preview_mime_type=preview_mime_type,
        preview_url=preview_url,
        thumbnail_url=thumbnail_url,
        page_count=page_count,
    )


def _unsupported_descriptor(source_file_id: str, filename: str, mime_type: str) -> PreviewDescriptor:
    return _build_descriptor(
        source_file_id=source_file_id,
        filename=filename,
        mime_type=mime_type,
        preview_available=False,
        preview_status="unsupported",
        preview_kind="unsupported",
        preview_mime_type=None,
        preview_url=None,
    )


def _failed_descriptor(source_file_id: str, filename: str, mime_type: str) -> PreviewDescriptor:
    return _build_descriptor(
        source_file_id=source_file_id,
        filename=filename,
        mime_type=mime_type,
        preview_available=False,
        preview_status="failed",
        preview_kind="pdf",
        preview_mime_type="application/pdf",
        preview_url=None,
    )


def _ready_descriptor(source_file_id: str, filename: str, mime_type: str) -> PreviewDescriptor:
    return _build_descriptor(
        source_file_id=source_file_id,
        filename=filename,
        mime_type=mime_type,
        preview_available=True,
        preview_status="ready",
        preview_kind="pdf",
        preview_mime_type="application/pdf",
        preview_url=f"/internal/source-previews/{source_file_id}/content",
    )


def _load_cached_descriptor(source_file_id: str) -> PreviewDescriptor | None:
    manifest_path = _manifest_path(source_file_id)
    preview_path = _preview_pdf_path(source_file_id)
    if not manifest_path.exists() or not preview_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("failed to read source preview manifest for %s", source_file_id)
        return None
    if payload.get("preview_status") != "ready":
        return None
    return _build_descriptor(
        source_file_id=str(payload.get("source_file_id") or source_file_id),
        filename=str(payload.get("filename") or ""),
        mime_type=str(payload.get("mime_type") or "application/octet-stream"),
        preview_available=bool(payload.get("preview_available")),
        preview_status=str(payload.get("preview_status") or "ready"),
        preview_kind=str(payload.get("preview_kind") or "pdf"),
        preview_mime_type=(
            str(payload.get("preview_mime_type"))
            if payload.get("preview_mime_type")
            else "application/pdf"
        ),
        preview_url=f"/internal/source-previews/{source_file_id}/content",
        thumbnail_url=str(payload.get("thumbnail_url")) if payload.get("thumbnail_url") else None,
        page_count=int(payload["page_count"]) if payload.get("page_count") is not None else None,
    )


def _write_manifest(source_file_id: str, descriptor: PreviewDescriptor) -> None:
    manifest_path = _manifest_path(source_file_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(descriptor.to_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _preview_family(filename: str, mime_type: str) -> str | None:
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext in _WORD_EXTENSIONS:
        return "word"
    if ext in _POWERPOINT_EXTENSIONS:
        return "powerpoint"
    if ext in _EXCEL_EXTENSIONS:
        return "excel"
    office_mime = mime_type.lower()
    if "word" in office_mime:
        return "word"
    if "presentation" in office_mime or "powerpoint" in office_mime:
        return "powerpoint"
    if "excel" in office_mime or "spreadsheet" in office_mime:
        return "excel"
    return None


def _powershell_script(family: str, source_path: str, preview_path: str) -> str:
    source_b64 = base64.b64encode(source_path.encode("utf-8")).decode("ascii")
    preview_b64 = base64.b64encode(preview_path.encode("utf-8")).decode("ascii")
    if family == "word":
        return f"""
$ErrorActionPreference = 'Stop'
$sourcePath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{source_b64}'))
$previewPath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{preview_b64}'))
$word = $null
$document = $null
try {{
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($sourcePath, $false, $true)
    $document.ExportAsFixedFormat($previewPath, 17)
}} finally {{
    if ($document -ne $null) {{ $document.Close($false) }}
    if ($word -ne $null) {{ $word.Quit() }}
}}
"""
    if family == "powerpoint":
        return f"""
$ErrorActionPreference = 'Stop'
$sourcePath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{source_b64}'))
$previewPath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{preview_b64}'))
$powerpoint = $null
$presentation = $null
try {{
    $powerpoint = New-Object -ComObject PowerPoint.Application
    $presentation = $powerpoint.Presentations.Open($sourcePath, $false, $false, $false)
    $presentation.SaveAs($previewPath, 32)
}} finally {{
    if ($presentation -ne $null) {{ $presentation.Close() }}
    if ($powerpoint -ne $null) {{ $powerpoint.Quit() }}
}}
"""
    if family == "excel":
        return f"""
$ErrorActionPreference = 'Stop'
$sourcePath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{source_b64}'))
$previewPath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{preview_b64}'))
$excel = $null
$workbook = $null
try {{
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $workbook = $excel.Workbooks.Open($sourcePath, 0, $true)
    $workbook.ExportAsFixedFormat(0, $previewPath)
}} finally {{
    if ($workbook -ne $null) {{ $workbook.Close($false) }}
    if ($excel -ne $null) {{ $excel.Quit() }}
}}
"""
    raise ValueError(f"unsupported preview family: {family}")


def _run_powershell(script: str, *, timeout_seconds: int = 180) -> None:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    executable = (
        shutil.which("powershell.exe")
        or shutil.which("powershell")
        or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    )
    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or f"powershell exit code {result.returncode}"
        raise RuntimeError(detail)


def render_source_preview(
    *,
    source_file_id: str,
    collection_id: str,
    source_file_path: str,
    filename: str,
    mime_type: str | None = None,
) -> PreviewDescriptor:
    resolved_filename = filename or Path(source_file_path).name
    resolved_mime_type = mime_type or _guess_mime_type(resolved_filename, source_file_path)
    family = _preview_family(resolved_filename, resolved_mime_type)
    if family is None:
        return _unsupported_descriptor(source_file_id, resolved_filename, resolved_mime_type)

    cached = _load_cached_descriptor(source_file_id)
    if cached is not None:
        return cached

    source_path = Path(source_file_path)
    if not source_path.exists():
        logger.error("source preview input missing for %s: %s", source_file_id, source_file_path)
        return _failed_descriptor(source_file_id, resolved_filename, resolved_mime_type)

    preview_path = _preview_pdf_path(source_file_id)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    script = _powershell_script(family, str(source_path.resolve()), str(preview_path.resolve()))

    try:
        _run_powershell(script)
    except Exception:
        logger.exception(
            "failed to render source preview for %s (%s, collection=%s)",
            source_file_id,
            resolved_filename,
            collection_id,
        )
        return _failed_descriptor(source_file_id, resolved_filename, resolved_mime_type)

    if not preview_path.exists():
        logger.error("preview renderer returned success but no preview file was produced for %s", source_file_id)
        return _failed_descriptor(source_file_id, resolved_filename, resolved_mime_type)

    descriptor = _ready_descriptor(source_file_id, resolved_filename, resolved_mime_type)
    _write_manifest(source_file_id, descriptor)
    return descriptor


def resolve_preview_asset(source_file_id: str) -> tuple[PreviewDescriptor | None, Path | None]:
    descriptor = _load_cached_descriptor(source_file_id)
    if descriptor is None:
        return None, None
    preview_path = _preview_pdf_path(source_file_id)
    if not preview_path.exists():
        return None, None
    return descriptor, preview_path
