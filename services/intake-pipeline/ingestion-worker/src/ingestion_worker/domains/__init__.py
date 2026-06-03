"""Owner domains for ingestion-worker.

Each domain enforces a single owner boundary.
Domain modules may NOT write tables owned by other domains.

| Domain           | Owns                                           |
|------------------|------------------------------------------------|
| approval_domain  | publish_status decision (system decide)        |
| publishing_domain| asset write, document persist, policy persist  |
| indexing_domain  | index build, activate, rollback                |
| orchestrator_domain | intake_job, stage_task, stage_attempt, stage_result (via orchestrator.py) |
| conversion_domain| conversion, dedup, version, quality (via pure_stages) |
| review_domain    | agent review, review cache (via pure_stages)   |
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .approval_domain import system_decide, ApprovalService
from .publishing_domain import persist_document_and_policy

if TYPE_CHECKING:
    from reality_rag_documents import DocumentService
    from ..indexing_service import (
        IndexBuildInput,
        IndexBuildOutput,
        IndexJobError,
        IndexingService,
        PerDocumentIndexResult,
    )

__all__ = [
    "system_decide",
    "ApprovalService",
    "DocumentService",
    "persist_document_and_policy",
    "IndexBuildInput",
    "IndexBuildOutput",
    "IndexJobError",
    "IndexingService",
    "PerDocumentIndexResult",
]


def __getattr__(name: str) -> Any:
    if name == "DocumentService":
        return getattr(import_module("reality_rag_documents"), name)
    if name in {
        "IndexBuildInput",
        "IndexBuildOutput",
        "IndexJobError",
        "IndexingService",
        "PerDocumentIndexResult",
    }:
        module = import_module("ingestion_worker.indexing_service")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
