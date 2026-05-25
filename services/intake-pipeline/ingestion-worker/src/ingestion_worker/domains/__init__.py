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

from .approval_domain import system_decide, ApprovalService
from .document_domain import DocumentService
from .indexing_domain import (
    IndexBuildInput,
    IndexBuildOutput,
    IndexJobError,
    IndexingService,
    PerDocumentIndexResult,
)
from .publishing_domain import persist_document_and_policy

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
