"""FastAPI routes for the Conversion Worker.

This module defines all HTTP endpoints. The router is created and populated
before being included in the FastAPI app, avoiding the module-level ordering
bug where app.include_router() was called before routes were registered.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from reality_rag_contracts import HealthResponse

from intake_runtime.stages.schemas import ConversionStageInput
from intake_runtime.stages.pure_stages import run_conversion_stage
from intake_runtime.converters.ragflow_converter import RAGFlowConverter
from conversion_worker.source_preview import render_source_preview, resolve_preview_asset

router = APIRouter()

# Service-local converter instance — owned by this module so routes can use it.
_converter = RAGFlowConverter()


class ConversionRunRequest(BaseModel):
    intake_job_id: str = ""
    collection_id: str = ""
    source_file_path: str = ""
    tenant_id: str = "default"
    collection_authority_level: int = 0
    index_version: str = "v1"
    existing_published_doc_id_by_source_hash: str | None = None
    latest_version_by_logical_id: int | None = None


class SourcePreviewRenderRequest(BaseModel):
    source_file_id: str
    collection_id: str = ""
    source_file_path: str
    filename: str = ""
    mime_type: str = "application/octet-stream"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="conversion-worker",
        version="0.1.0",
    )


@router.post("/internal/conversion/run")
async def run_conversion(request: ConversionRunRequest) -> dict:
    try:
        inp = ConversionStageInput(
            schema_version="v1",
            intake_job_id=request.intake_job_id,
            collection_id=request.collection_id,
            source_file_path=request.source_file_path,
            tenant_id=request.tenant_id,
            collection_authority_level=request.collection_authority_level,
            index_version=request.index_version,
            existing_published_doc_id_by_source_hash=request.existing_published_doc_id_by_source_hash,
            latest_version_by_logical_id=request.latest_version_by_logical_id,
        )
        out = run_conversion_stage(inp, [_converter])
        return {
            "schema_version": out.schema_version,
            "input_hash": out.input_hash,
            "result_hash": out.result_hash,
            "conversion_status": out.conversion_result.conversion_status.value if out.conversion_result else None,
            "preliminary_doc_id": out.preliminary_doc_id,
            "logical_document_id": out.logical_document_id,
            "version": out.version,
            "dedup_skipped": out.dedup_skipped,
            "skip_reason": out.skip_reason,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/internal/source-previews/render")
async def render_preview(request: SourcePreviewRenderRequest) -> dict:
    descriptor = render_source_preview(
        source_file_id=request.source_file_id,
        collection_id=request.collection_id,
        source_file_path=request.source_file_path,
        filename=request.filename,
        mime_type=request.mime_type,
    )
    return descriptor.to_payload()


@router.get("/internal/source-previews/{source_file_id}/content")
async def get_preview_content(source_file_id: str):
    descriptor, preview_path = resolve_preview_asset(source_file_id)
    if descriptor is None or preview_path is None:
        raise HTTPException(status_code=404, detail="Source preview asset not found")
    filename = Path(descriptor.filename or "preview").stem + ".pdf"
    return FileResponse(
        path=preview_path,
        media_type=descriptor.preview_mime_type or "application/pdf",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )
