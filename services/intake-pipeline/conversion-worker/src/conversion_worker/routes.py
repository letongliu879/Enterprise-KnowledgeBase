"""FastAPI routes for the Conversion Worker.

This module defines all HTTP endpoints. The router is created and populated
before being included in the FastAPI app, avoiding the module-level ordering
bug where app.include_router() was called before routes were registered.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from reality_rag_contracts import HealthResponse

from intake_runtime.stages.schemas import ConversionStageInput
from intake_runtime.stages.pure_stages import run_conversion_stage
from intake_runtime.converters.ragflow_converter import RAGFlowConverter

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
