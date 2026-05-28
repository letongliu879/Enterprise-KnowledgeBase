from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from indexing_service.contracts import IndexBuildRequestedCommand
from indexing_service.metrics import InMemoryIndexingMetrics
from indexing_service.jobs.index_job_runner import IndexJobRunner
from indexing_service.jobs.parse_preview_runner import ParsePreviewRunner
from indexing_service.preview_contracts import ParsePreviewRequestedCommand
from indexing_service.repository import create_indexing_repository
from indexing_service.versioning.activation import ActivationService
from indexing_service.versioning.cleanup import CleanupService
from indexing_service.versioning.index_registry import IndexRegistry
from indexing_service.versioning.rollback import RollbackService
from indexing_service.profile_validator import validate_parser_profile
from reality_rag_contracts import (
    ChunkRevisionMaterializeRequest,
    ChunkRevisionRequest,
    ParserProfileValidateRequest,
    ParserProfileValidateResponse,
)


repository = create_indexing_repository()
metrics = InMemoryIndexingMetrics()
job_runner = IndexJobRunner(repository, metrics=metrics)
parse_preview_runner = ParsePreviewRunner(repository=repository, metrics=metrics)
index_registry = IndexRegistry(repository)
activation_service = ActivationService(repository)
rollback_service = RollbackService(repository)
cleanup_service = CleanupService(repository)

app = FastAPI(title="Reality-RAG Indexing", version="0.1.0")


@app.post("/internal/parse-previews", status_code=202)
def create_parse_preview(command: ParsePreviewRequestedCommand) -> dict[str, object]:
    accepted = parse_preview_runner.accept(command)
    return accepted.model_dump()


@app.get("/internal/parse-snapshots/{parse_snapshot_id}")
def get_parse_snapshot(parse_snapshot_id: str) -> dict[str, object]:
    return repository.get_parse_snapshot(parse_snapshot_id).model_dump(mode="json")


@app.get("/internal/chunks")
def query_chunks(
    tenant_id: str,
    principal_id: str,
    collection_id: str | None = None,
    principal_groups: list[str] = Query(default_factory=list),
) -> list[dict[str, object]]:
    return [
        chunk.model_dump(mode="json", by_alias=True)
        for chunk in repository.query_chunks(
            tenant_id=tenant_id,
            principal_id=principal_id,
            principal_groups=tuple(principal_groups),
            collection_id=collection_id,
        )
    ]


@app.get("/internal/metrics")
def get_metrics() -> dict[str, object]:
    return metrics.snapshot()


@app.post("/internal/index-jobs", status_code=202)
def create_index_job(command: IndexBuildRequestedCommand) -> dict[str, str]:
    return job_runner.accept(command)


@app.get("/internal/index-jobs/{job_id}")
def get_index_job(job_id: str) -> dict[str, object]:
    record = repository.get_job(job_id)
    return {
        "build_job_id": record.build_job_id,
        "build_request_id": record.build_request_id,
        "status": record.status,
        "final_doc_id": record.final_doc_id,
        "index_version_id": record.index_version_id,
        "error_message": record.error_message,
        "completed_at": record.completed_at,
    }


@app.get("/internal/indexed-documents")
def list_indexed_documents(
    collection_id: str | None = None,
    index_version: str | None = None,
    final_doc_id: str | None = None,
) -> list[dict[str, object]]:
    records = repository.list_indexed_documents()
    filtered = [
        record
        for record in records
        if (collection_id is None or record.collection_id == collection_id)
        and (index_version is None or record.index_version == index_version)
        and (final_doc_id is None or record.final_doc_id == final_doc_id)
    ]
    return [record.model_dump(mode="json") for record in filtered]


@app.post("/internal/index-versions/{index_version_id}/activate", status_code=202)
def activate_index_version(index_version_id: str) -> dict[str, object]:
    return activation_service.activate(index_version_id).model_dump()


@app.post("/internal/index-versions/{index_version_id}/rollback", status_code=202)
def rollback_index_version(index_version_id: str) -> dict[str, object]:
    return rollback_service.rollback(index_version_id).model_dump()


@app.post("/internal/index-versions/{index_version_id}/cleanup", status_code=202)
def cleanup_index_version(index_version_id: str) -> dict[str, object]:
    return cleanup_service.cleanup(index_version_id).model_dump()


@app.get("/internal/index-versions/{index_version_id}")
def get_index_version(index_version_id: str) -> dict[str, object]:
    return index_registry.get(index_version_id).model_dump(mode="json")


@app.post("/internal/parser-profiles/validate")
def validate_parser_profile_endpoint(request: ParserProfileValidateRequest) -> ParserProfileValidateResponse:
    result = validate_parser_profile(
        parser_profile_id=request.parser_profile_id,
        parser_id=request.parser_id,
        parser_config=request.parser_config,
        chunk_profile_id=request.chunk_profile_id,
        tenant_id=request.tenant_id,
        collection_id=request.collection_id,
        version=request.version,
    )
    return ParserProfileValidateResponse(
        valid=result.valid,
        canonical_config=result.canonical_config,
        profile_hash=result.profile_hash,
        warnings=result.warnings,
        errors=[{"code": e.code, "message": e.message} for e in result.errors],
        runtime_owner=result.runtime_owner,
        validator_version=result.validator_version,
    )


@app.post("/internal/chunks/{evidence_id}/revisions")
def create_chunk_revision(evidence_id: str, command: ChunkRevisionRequest) -> dict[str, object]:
    try:
        revision = repository.create_chunk_revision(
            revision_id=f"crv_{__import__('uuid').uuid4().hex[:12]}",
            base_evidence_id=evidence_id,
            doc_id=command.payload.get("doc_id", ""),
            collection_id=command.collection_id,
            tenant_id=command.tenant_id,
            operation=command.payload.get("operation", "update"),
            content=command.payload.get("content"),
            vector_text=command.payload.get("vector_text"),
            section_path=command.payload.get("section_path"),
            metadata_patch=command.payload.get("metadata_patch"),
            citation_payload=command.payload.get("citation_payload"),
            idempotency_key=command.idempotency_key,
            trace_id=command.trace_id,
        )
        return revision.model_dump(mode="json")
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@app.get("/internal/chunk-revisions/{revision_id}")
def get_chunk_revision(revision_id: str) -> dict[str, object]:
    try:
        revision = repository.get_chunk_revision(revision_id)
        return revision.model_dump(mode="json")
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/internal/chunk-revisions/{revision_id}/materialize")
def materialize_chunk_revision(revision_id: str, command: ChunkRevisionMaterializeRequest) -> dict[str, object]:
    try:
        result = repository.materialize_chunk_revision(revision_id)
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "indexing", "status": "ok"}
