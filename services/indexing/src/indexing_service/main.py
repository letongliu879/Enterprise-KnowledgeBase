from __future__ import annotations

from fastapi import FastAPI
from fastapi import Query

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
        chunk.model_dump(mode="json")
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
        "failure_reason": record.failure_reason,
        "completed_at": record.completed_at,
    }


@app.get("/internal/indexed-documents")
def list_indexed_documents(
    collection_id: str | None = None,
    index_version: str | None = None,
) -> list[dict[str, object]]:
    records = repository.list_indexed_documents()
    filtered = [
        record
        for record in records
        if (collection_id is None or record.collection_id == collection_id)
        and (index_version is None or record.index_version == index_version)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "indexing", "status": "ok"}
